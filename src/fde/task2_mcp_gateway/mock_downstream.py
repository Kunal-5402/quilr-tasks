"""Mock MCP server behind the gateway.

It counts the requests it receives, so a test can prove that a denied call
never reaches it.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from fde.core import jsonrpc

app = FastAPI(title="Mock downstream MCP server")

TOOLS = [
    {"name": "get_customer_record", "description": "Read one customer record."},
    {"name": "admin_reset_key", "description": "Reset the tenant API key."},
]

STATS = {"requests": 0, "tool_calls": 0}


@app.get("/stats")
async def stats() -> dict[str, int]:
    return STATS


@app.post("/stats/reset")
async def reset_stats() -> dict[str, int]:
    STATS.update(requests=0, tool_calls=0)
    return STATS


def _answer(member: dict[str, Any]) -> dict | None:
    request_id = member.get("id")
    method = member.get("method")

    if request_id is None:
        return None  # a notification gets no response

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        STATS["tool_calls"] += 1
        name = member.get("params", {}).get("name")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": f"{name} ran downstream"}]},
        }

    return jsonrpc.error_response(request_id, jsonrpc.METHOD_NOT_FOUND, "Method not found")


@app.post("/mcp")
async def mcp(request: Request) -> JSONResponse:
    body = await request.json()
    STATS["requests"] += 1

    if isinstance(body, list):
        answers = [a for member in body if (a := _answer(member)) is not None]
        return JSONResponse(answers)

    answer = _answer(body)
    return JSONResponse(answer, status_code=202 if answer is None else 200)
