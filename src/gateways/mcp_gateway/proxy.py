"""MCP gateway.

Authentication happens once for the whole HTTP request. Authorization happens
once for each JSON-RPC member. A denied member never reaches the downstream
server, so the gateway forwards only what it approved.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, NamedTuple

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from gateways.core import jsonrpc
from gateways.core.logging import get_logger
from gateways.mcp_gateway.auth import Role, resolve_role
from gateways.mcp_gateway.policy import is_allowed
from gateways.mcp_gateway.settings import settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.client.aclose()


app = FastAPI(title="MCP security gateway", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _tool_name(member: dict[str, Any]) -> str | None:
    params = member.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    return name if isinstance(name, str) else None


def _rejection(member: Any, role: Role | None) -> dict | None:
    """Return the error response for a rejected member, or None to forward it."""
    if not isinstance(member, dict) or not isinstance(member.get("method"), str):
        return jsonrpc.error_response(None, jsonrpc.INVALID_REQUEST, "Invalid Request")

    request_id = member.get("id")

    if role is None:
        return jsonrpc.error_response(
            request_id,
            jsonrpc.UNAUTHORIZED_TOOL_CALL,
            "Unauthorized Tool Call",
            {"reason": "missing or unknown bearer token"},
        )

    if member["method"] != "tools/call":
        return None

    name = _tool_name(member)
    if name is None:
        return jsonrpc.error_response(
            request_id,
            jsonrpc.INVALID_PARAMS,
            "Invalid params",
            {"reason": "params.name is missing"},
        )

    if not is_allowed(member["method"], name, role):
        log.warning("denied tool=%s role=%s", name, role)
        return jsonrpc.error_response(
            request_id,
            jsonrpc.UNAUTHORIZED_TOOL_CALL,
            "Unauthorized Tool Call",
            {"tool": name, "required_role": Role.ADMIN.value},
        )

    return None


class Screened(NamedTuple):
    approved: list[Any]
    rejected: dict[int, dict]  # the member index, and the error to answer with


def _screen(members: list[Any], role: Role | None) -> Screened:
    approved, rejected = [], {}
    for index, member in enumerate(members):
        error = _rejection(member, role)
        if error is None:
            approved.append(member)
        else:
            rejected[index] = error
    return Screened(approved, rejected)


async def _forward(client: httpx.AsyncClient, payload: Any, authorization: str | None) -> list[Any]:
    """Send the approved members downstream and return the answers as a list."""
    headers = {"Content-Type": "application/json"}
    if settings.forward_authorization and authorization:
        # The gateway is the trust boundary, so the token stops here by default.
        headers["Authorization"] = authorization

    response = await client.post(settings.downstream_url, json=payload, headers=headers)
    response.raise_for_status()
    if not response.content:
        return []

    answer = response.json()
    return answer if isinstance(answer, list) else [answer]


def _merge(members: list[Any], screened: Screened, downstream: list[Any]) -> list[dict]:
    """Rebuild the batch answer in the original order. A notification gets nothing."""
    by_id = {str(item.get("id")): item for item in downstream if isinstance(item, dict)}

    merged = []
    for index, member in enumerate(members):
        if index in screened.rejected:
            if isinstance(member, dict) and member.get("id") is not None:
                merged.append(screened.rejected[index])
        elif isinstance(member, dict) and (answer := by_id.get(str(member.get("id")))):
            merged.append(answer)
    return merged


@app.post("/mcp")
async def handle(
    request: Request, authorization: str | None = Header(default=None)
) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc.error_response(None, jsonrpc.PARSE_ERROR, "Parse error"))

    is_batch = isinstance(body, list)
    members = body if is_batch else [body]
    if is_batch and not members:
        invalid = jsonrpc.error_response(None, jsonrpc.INVALID_REQUEST, "Invalid Request")
        return JSONResponse(invalid)

    screened = _screen(members, resolve_role(authorization))

    downstream: list[Any] = []
    if screened.approved:
        payload = screened.approved if is_batch else screened.approved[0]
        downstream = await _forward(request.app.state.client, payload, authorization)

    if is_batch:
        merged = _merge(members, screened, downstream)
        return JSONResponse(merged, status_code=202 if not merged else 200)

    single = next(iter(screened.rejected.values()), None) or (downstream[0] if downstream else None)
    return JSONResponse(single, status_code=202 if single is None else 200)
