"""MCP gateway.

Authentication happens once for the whole HTTP request. Authorization happens
once for each JSON-RPC member. A denied member never reaches the downstream
server, so the gateway forwards only what it approved.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from fde.core import jsonrpc
from fde.core.logging import get_logger
from fde.task2_mcp_gateway.auth import Role, resolve_role
from fde.task2_mcp_gateway.policy import is_allowed
from fde.task2_mcp_gateway.settings import settings

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = httpx.AsyncClient(timeout=30.0)
    yield
    await app.state.client.aclose()


app = FastAPI(title="MCP Security Gateway", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _tool_name(member: dict[str, Any]) -> str | None:
    params = member.get("params")
    if not isinstance(params, dict):
        return None
    name = params.get("name")
    return name if isinstance(name, str) else None


def _screen(member: Any, role: Role | None) -> dict | None:
    """Return an error response for a rejected member, or None to forward it."""
    if not isinstance(member, dict) or not isinstance(member.get("method"), str):
        return jsonrpc.error_response(None, jsonrpc.INVALID_REQUEST, "Invalid Request")

    request_id = member.get("id")
    method = member["method"]

    if role is None:
        return jsonrpc.error_response(
            request_id,
            jsonrpc.UNAUTHORIZED_TOOL_CALL,
            "Unauthorized Tool Call",
            {"reason": "missing or unknown bearer token"},
        )

    if method == "tools/call":
        name = _tool_name(member)
        if name is None:
            return jsonrpc.error_response(
                request_id,
                jsonrpc.INVALID_PARAMS,
                "Invalid params",
                {"reason": "params.name is missing"},
            )
        if not is_allowed(method, name, role):
            log.warning("denied tool=%s role=%s", name, role)
            return jsonrpc.error_response(
                request_id,
                jsonrpc.UNAUTHORIZED_TOOL_CALL,
                "Unauthorized Tool Call",
                {"tool": name, "required_role": Role.ADMIN.value},
            )

    return None


async def _forward(client: httpx.AsyncClient, payload: Any, authorization: str | None) -> Any:
    headers = {"Content-Type": "application/json"}
    if settings.forward_authorization and authorization:
        headers["Authorization"] = authorization

    response = await client.post(settings.downstream_url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json() if response.content else None


@app.post("/mcp")
async def handle(
    request: Request, authorization: str | None = Header(default=None)
) -> JSONResponse:
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(jsonrpc.error_response(None, jsonrpc.PARSE_ERROR, "Parse error"))

    role = resolve_role(authorization)
    is_batch = isinstance(body, list)
    members = body if is_batch else [body]
    if is_batch and not members:
        invalid = jsonrpc.error_response(None, jsonrpc.INVALID_REQUEST, "Invalid Request")
        return JSONResponse(invalid)

    rejected: dict[int, dict] = {}
    approved: list[Any] = []
    for index, member in enumerate(members):
        error = _screen(member, role)
        if error is None:
            approved.append(member)
        else:
            rejected[index] = error

    downstream: list[Any] = []
    if approved:
        payload = approved if is_batch else approved[0]
        answer = await _forward(request.app.state.client, payload, authorization)
        if answer is not None:
            downstream = answer if isinstance(answer, list) else [answer]

    if not is_batch:
        result = next(iter(rejected.values()), None) or (downstream[0] if downstream else None)
        return JSONResponse(result, status_code=202 if result is None else 200)

    # A notification has no id, so it gets no response. Errors keep the batch order.
    by_id = {str(item.get("id")): item for item in downstream if isinstance(item, dict)}
    merged = []
    for index, member in enumerate(members):
        if index in rejected:
            if isinstance(member, dict) and member.get("id") is not None:
                merged.append(rejected[index])
        elif isinstance(member, dict) and (found := by_id.get(str(member.get("id")))):
            merged.append(found)

    return JSONResponse(merged, status_code=202 if not merged else 200)
