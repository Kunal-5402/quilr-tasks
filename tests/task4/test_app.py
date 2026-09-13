import asyncio

import pytest

from tests.task4.conftest import TENANT_A

BODY = {"prompt": "write a haiku about gateways", "max_tokens": 32}


@pytest.mark.req("T4-R1")
async def test_a_healthy_request_returns_the_primary_answer(gateway):
    response = await gateway.post("/v1/completions", json=BODY, headers=TENANT_A)

    assert response.status_code == 200
    assert response.headers["X-FDE-Provider"] == "primary"
    assert response.json()["tenant"] == "tenant-a"


@pytest.mark.req("T4-R4")
async def test_the_response_names_the_provider_that_answered(gateway, behaviour):
    behaviour("primary", status=429)
    response = await gateway.post("/v1/completions", json=BODY, headers=TENANT_A)

    assert response.headers["X-FDE-Provider"] == "secondary"


@pytest.mark.req("T4-R3", "T4-R6")
async def test_a_full_window_returns_the_standard_429(gateway):
    """The fixture limit is 1000 tokens, so one large request fills the window."""
    response = await gateway.post(
        "/v1/completions", json={**BODY, "max_tokens": 8192}, headers=TENANT_A
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["error"]["type"] == "rate_limit_exceeded"


@pytest.mark.req("T4-R6", "T4-R7")
async def test_an_upstream_failure_leaks_nothing(gateway, behaviour):
    behaviour("primary", status=429)
    behaviour("secondary", status=500)

    response = await gateway.post("/v1/completions", json=BODY, headers=TENANT_A)
    body = response.text

    assert response.status_code == 503
    assert response.json()["error"] == {
        "type": "upstream_unavailable",
        "message": "No model provider answered the request.",
        "request_id": response.headers["X-Request-Id"],
        "status": 503,
    }
    for leak in ["Traceback", "secondary", "500", "httpx", "mock failure"]:
        assert leak not in body


@pytest.mark.req("T4-R2")
async def test_a_failed_request_does_not_consume_the_budget(gateway, behaviour):
    behaviour("primary", status=500)
    behaviour("secondary", status=500)

    await gateway.post("/v1/completions", json=BODY, headers=TENANT_A)

    assert await gateway._transport.app.state.limiter.used("tenant-a") == 0


@pytest.mark.req("T4-R2")
async def test_settle_corrects_the_estimate(gateway):
    await gateway.post("/v1/completions", json={**BODY, "max_tokens": 512}, headers=TENANT_A)
    used = await gateway._transport.app.state.limiter.used("tenant-a")

    assert 0 < used < 512


@pytest.mark.req("T4-R6")
async def test_an_unknown_api_key_is_rejected(gateway):
    response = await gateway.post(
        "/v1/completions", json=BODY, headers={"Authorization": "Bearer nope"}
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request"


@pytest.mark.req("T4-R6")
async def test_an_invalid_body_is_rejected(gateway):
    response = await gateway.post("/v1/completions", json={"prompt": ""}, headers=TENANT_A)
    assert response.status_code == 422


@pytest.mark.req("T4-R2")
async def test_parallel_requests_share_one_budget(gateway):
    body = {**BODY, "max_tokens": 256}
    responses = await asyncio.gather(
        *[gateway.post("/v1/completions", json=body, headers=TENANT_A) for _ in range(10)]
    )

    codes = [r.status_code for r in responses]
    assert codes.count(200) == 3
    assert codes.count(429) == 7
