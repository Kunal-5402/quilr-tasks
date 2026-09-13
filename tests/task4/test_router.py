import pytest

from fde.core.errors import UpstreamUnavailable

PAYLOAD = {"prompt": "hello", "max_tokens": 16}


@pytest.mark.req("T4-R1")
async def test_the_primary_answers_when_it_is_healthy(router):
    result = await router.complete(PAYLOAD)
    assert result.provider == "primary"


@pytest.mark.req("T4-R4")
async def test_a_429_from_the_primary_triggers_the_failover(router, behaviour):
    behaviour("primary", status=429)
    result = await router.complete(PAYLOAD)
    assert result.provider == "secondary"


@pytest.mark.req("T4-R5")
async def test_a_timeout_on_the_primary_triggers_the_failover(router, behaviour):
    behaviour("primary", delay_ms=1000)  # the primary budget is 200 ms in the fixture
    result = await router.complete(PAYLOAD)
    assert result.provider == "secondary"


@pytest.mark.req("T4-R5")
async def test_a_primary_that_answers_inside_the_budget_is_used(router, behaviour):
    behaviour("primary", delay_ms=50)
    result = await router.complete(PAYLOAD)
    assert result.provider == "primary"


@pytest.mark.req("T4-R4")
async def test_a_5xx_from_the_primary_triggers_the_failover(router, behaviour):
    behaviour("primary", status=503)
    result = await router.complete(PAYLOAD)
    assert result.provider == "secondary"


@pytest.mark.req("T4-R6")
async def test_both_providers_failing_raises_the_gateway_error(router, behaviour):
    behaviour("primary", status=429)
    behaviour("secondary", status=500)

    with pytest.raises(UpstreamUnavailable):
        await router.complete(PAYLOAD)
