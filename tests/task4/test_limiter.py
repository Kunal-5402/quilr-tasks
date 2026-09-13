import asyncio

import pytest

from fde.core.errors import RateLimitExceeded
from fde.task4_router.limiter import TokenRateLimiter, estimate_tokens


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def limiter(tmp_path, clock):
    limiter = TokenRateLimiter.open(str(tmp_path / "router.sqlite3"), limit=1000, clock=clock)
    yield limiter
    limiter.close()


@pytest.mark.req("T4-R8")
def test_the_database_file_is_on_disk(tmp_path, clock):
    path = tmp_path / "nested" / "router.sqlite3"
    limiter = TokenRateLimiter.open(str(path), clock=clock)
    limiter.close()
    assert path.exists()


@pytest.mark.req("T4-R2")
async def test_a_request_under_the_limit_passes(limiter):
    await limiter.reserve("tenant-a", 400)
    assert await limiter.used("tenant-a") == 400


@pytest.mark.req("T4-R3")
async def test_a_request_over_the_limit_is_rejected(limiter):
    await limiter.reserve("tenant-a", 900)
    with pytest.raises(RateLimitExceeded) as failure:
        await limiter.reserve("tenant-a", 200)
    assert failure.value.retry_after_seconds > 0


@pytest.mark.req("T4-R2")
async def test_the_window_slides(limiter, clock):
    await limiter.reserve("tenant-a", 1000)
    clock.now += 61
    await limiter.reserve("tenant-a", 1000)
    assert await limiter.used("tenant-a") == 1000


@pytest.mark.req("T4-R2")
async def test_a_row_inside_the_window_still_counts(limiter, clock):
    await limiter.reserve("tenant-a", 900)
    clock.now += 30
    with pytest.raises(RateLimitExceeded):
        await limiter.reserve("tenant-a", 200)


@pytest.mark.req("T4-R3")
async def test_two_tenants_do_not_share_a_budget(limiter):
    await limiter.reserve("tenant-a", 1000)
    await limiter.reserve("tenant-b", 1000)
    assert await limiter.used("tenant-b") == 1000


@pytest.mark.req("T4-R2")
async def test_settle_replaces_the_estimate(limiter):
    reservation = await limiter.reserve("tenant-a", 800)
    await limiter.settle(reservation, 120)
    assert await limiter.used("tenant-a") == 120


@pytest.mark.req("T4-R2")
async def test_release_frees_the_budget(limiter):
    reservation = await limiter.reserve("tenant-a", 900)
    await limiter.release(reservation)
    assert await limiter.used("tenant-a") == 0


@pytest.mark.req("T4-R2")
async def test_parallel_reservations_never_exceed_the_limit(limiter):
    async def attempt() -> bool:
        try:
            await limiter.reserve("tenant-a", 100)
            return True
        except RateLimitExceeded:
            return False

    outcomes = await asyncio.gather(*[attempt() for _ in range(50)])

    assert sum(outcomes) == 10
    assert await limiter.used("tenant-a") == 1000


@pytest.mark.req("T4-R2")
def test_estimate_tokens_is_never_zero():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a" * 400) == 100
