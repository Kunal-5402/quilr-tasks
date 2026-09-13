"""Token aware sliding window rate limiter.

The window slides: a check sums only the rows inside the last N seconds and
deletes the older rows. The check and the insert run inside one IMMEDIATE
transaction, so 2 parallel requests cannot both pass a full window.
"""

import asyncio
import sqlite3
import time
import uuid
from dataclasses import dataclass

from fde.core.errors import RateLimitExceeded
from fde.task4_router.db import connect
from fde.task4_router.settings import settings


@dataclass(frozen=True)
class Reservation:
    id: str
    tenant: str
    tokens: int


def estimate_tokens(text: str) -> int:
    """A rough count. The router corrects it with the real usage after the call."""
    return max(1, len(text) // 4)


class TokenRateLimiter:
    def __init__(
        self,
        connection: sqlite3.Connection,
        limit: int | None = None,
        window_seconds: int | None = None,
        clock=time.time,
    ) -> None:
        self._connection = connection
        self._limit = limit or settings.token_limit_per_minute
        self._window = window_seconds or settings.window_seconds
        self._now = clock
        self._lock = asyncio.Lock()

    @classmethod
    def open(cls, path: str | None = None, **kwargs) -> "TokenRateLimiter":
        return cls(connect(path or settings.database_path), **kwargs)

    async def _run(self, call, *args):
        """SQLite blocks, so it runs in a worker thread. The lock keeps one caller at a time."""
        async with self._lock:
            return await asyncio.to_thread(call, *args)

    async def reserve(self, tenant: str, tokens: int) -> Reservation:
        # The lock serialises this process. IMMEDIATE serialises other processes.
        return await self._run(self._reserve, tenant, tokens)

    async def settle(self, reservation: Reservation, actual_tokens: int) -> None:
        await self._run(self._settle, reservation.id, actual_tokens)

    async def release(self, reservation: Reservation) -> None:
        await self._run(self._release, reservation.id)

    async def used(self, tenant: str) -> int:
        return await self._run(self._used, tenant)

    def _reserve(self, tenant: str, tokens: int) -> Reservation:
        cursor = self._connection
        cursor.execute("BEGIN IMMEDIATE")
        try:
            now = self._now()
            cursor.execute("DELETE FROM usage WHERE created_at < ?", (now - self._window,))
            used = cursor.execute(
                "SELECT COALESCE(SUM(tokens), 0) FROM usage WHERE tenant = ?", (tenant,)
            ).fetchone()[0]

            if used + tokens > self._limit:
                oldest = cursor.execute(
                    "SELECT MIN(created_at) FROM usage WHERE tenant = ?", (tenant,)
                ).fetchone()[0]
                cursor.execute("ROLLBACK")
                raise RateLimitExceeded(
                    retry_after_seconds=self._retry_after(oldest, now),
                    detail=f"tenant={tenant} used={used} asked={tokens} limit={self._limit}",
                )

            reservation = Reservation(uuid.uuid4().hex, tenant, tokens)
            cursor.execute(
                "INSERT INTO usage (id, tenant, tokens, created_at) VALUES (?, ?, ?, ?)",
                (reservation.id, tenant, tokens, now),
            )
            cursor.execute("COMMIT")
            return reservation
        except RateLimitExceeded:
            raise
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def _retry_after(self, oldest: float | None, now: float) -> int:
        if oldest is None:
            return self._window
        return max(1, int(oldest + self._window - now) + 1)

    def _settle(self, reservation_id: str, actual_tokens: int) -> None:
        self._connection.execute(
            "UPDATE usage SET tokens = ?, settled = 1 WHERE id = ?", (actual_tokens, reservation_id)
        )

    def _release(self, reservation_id: str) -> None:
        self._connection.execute("DELETE FROM usage WHERE id = ?", (reservation_id,))

    def _used(self, tenant: str) -> int:
        return self._connection.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM usage WHERE tenant = ? AND created_at >= ?",
            (tenant, self._now() - self._window),
        ).fetchone()[0]

    def close(self) -> None:
        self._connection.close()
