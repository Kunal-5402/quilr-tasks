import pytest

from gateways.core.errors import GatewayError, RateLimitExceeded, to_client_payload


@pytest.mark.req("T4-R7")
def test_the_payload_holds_no_internal_detail():
    error = GatewayError(detail="postgres://user:secret@db/internal")
    payload = to_client_payload(error, "req-1")

    assert payload == {
        "error": {
            "type": "internal_error",
            "message": GatewayError.message,
            "request_id": "req-1",
            "status": 500,
        }
    }


@pytest.mark.req("T4-R6")
def test_a_rate_limit_error_carries_a_retry_header():
    error = RateLimitExceeded(retry_after_seconds=42)
    assert error.headers == {"Retry-After": "42"}
