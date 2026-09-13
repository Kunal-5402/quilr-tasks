"""Failover between a primary and a secondary model provider.

The primary gets a hard time budget. A timeout cancels it, so the gateway does
not hold a dead connection while the secondary runs.
"""

import asyncio

from fde.core.errors import UpstreamUnavailable
from fde.core.logging import get_logger
from fde.task4_router.providers import (
    Provider,
    ProviderResult,
    UpstreamFailed,
    UpstreamRateLimited,
)
from fde.task4_router.settings import settings

log = get_logger(__name__)

FAILOVER_CAUSES = (TimeoutError, UpstreamRateLimited, UpstreamFailed)


class ModelRouter:
    def __init__(
        self,
        primary: Provider,
        secondary: Provider,
        primary_timeout: float | None = None,
        secondary_timeout: float | None = None,
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self._primary_timeout = primary_timeout or settings.primary_timeout_seconds
        self._secondary_timeout = secondary_timeout or settings.secondary_timeout_seconds

    async def complete(self, payload: dict) -> ProviderResult:
        try:
            return await asyncio.wait_for(
                self._primary.complete(payload), timeout=self._primary_timeout
            )
        except FAILOVER_CAUSES as cause:
            log.warning("primary failed, using the secondary: %s", cause)

        try:
            return await asyncio.wait_for(
                self._secondary.complete(payload), timeout=self._secondary_timeout
            )
        except FAILOVER_CAUSES as cause:
            # The client never sees this text. Only the log holds it.
            raise UpstreamUnavailable(detail=f"both providers failed: {cause}") from cause
