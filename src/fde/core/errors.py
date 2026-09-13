"""One error envelope for every HTTP gateway.

The client sees a type, a message, and a request id. The cause stays in the
stderr log, so no stack trace or upstream detail leaks.
"""

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from fde.core.logging import get_logger

log = get_logger(__name__)


class GatewayError(Exception):
    """A failure that the client is allowed to know about."""

    type = "internal_error"
    status = 500
    message = "The gateway could not complete the request."

    def __init__(self, detail: str = "", headers: dict[str, str] | None = None) -> None:
        super().__init__(detail or self.message)
        self.detail = detail
        self.headers = headers or {}


class InvalidRequest(GatewayError):
    type = "invalid_request"
    status = 400
    message = "The request body is not valid."


class RateLimitExceeded(GatewayError):
    type = "rate_limit_exceeded"
    status = 429
    message = "The tenant token budget for this minute is used up."

    def __init__(self, retry_after_seconds: int, detail: str = "") -> None:
        super().__init__(detail, headers={"Retry-After": str(retry_after_seconds)})
        self.retry_after_seconds = retry_after_seconds


class UpstreamUnavailable(GatewayError):
    type = "upstream_unavailable"
    status = 503
    message = "No model provider answered the request."


class ErrorBody(BaseModel):
    type: str
    message: str
    request_id: str
    status: int


def new_request_id() -> str:
    return uuid.uuid4().hex


def to_client_payload(exc: GatewayError, request_id: str) -> dict[str, Any]:
    body = ErrorBody(type=exc.type, message=exc.message, request_id=request_id, status=exc.status)
    return {"error": body.model_dump()}


def install_handlers(app: Any) -> None:
    """Map every exception to the safe envelope."""

    @app.exception_handler(GatewayError)
    async def _handle_known(request: Request, exc: GatewayError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", new_request_id())
        log.warning("%s request_id=%s detail=%s", exc.type, request_id, exc.detail)
        return JSONResponse(
            status_code=exc.status,
            content=to_client_payload(exc, request_id),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", new_request_id())
        log.exception("unhandled error request_id=%s", request_id)
        return JSONResponse(status_code=500, content=to_client_payload(GatewayError(), request_id))
