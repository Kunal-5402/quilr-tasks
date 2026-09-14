"""MCP server with 2 tools and protocol level error mapping.

The SDK's @server.call_tool() decorator turns any exception into a tool result
with isError=True. A malformed input is a protocol failure, not a tool result,
so this module registers the CallToolRequest handler directly. The request
dispatcher converts a raised McpError into a JSON-RPC error object on the wire.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.shared.exceptions import McpError
from pydantic import BaseModel, ValidationError

from gateways.core.logging import get_logger
from gateways.mcp_tool_server import store
from gateways.mcp_tool_server.schemas import GetCustomerRecordInput, TriggerRefundInput

log = get_logger(__name__)

SERVER_NAME = "fde-customer-tools"
SERVER_VERSION = "0.1.0"

ToolHandler = Callable[[BaseModel], Awaitable[dict[str, Any]]]


class Tool:
    def __init__(
        self, name: str, description: str, model: type[BaseModel], handler: ToolHandler
    ) -> None:
        self.name = name
        self.description = description
        self.model = model
        self.handler = handler

    def to_mcp(self) -> types.Tool:
        # One source of truth: the advertised schema is the enforced schema.
        return types.Tool(
            name=self.name, description=self.description, inputSchema=self.model.model_json_schema()
        )


async def _get_customer_record(args: GetCustomerRecordInput) -> dict[str, Any]:
    customer = store.find_customer(args.customer_id)
    if customer is None:
        # A missing record is a valid answer, not a protocol failure.
        return {"found": False, "customer_id": args.customer_id}
    return {"found": True, **customer.__dict__}


async def _trigger_refund(args: TriggerRefundInput) -> dict[str, Any]:
    if store.find_customer(args.customer_id) is None:
        return {"accepted": False, "reason": "unknown customer", "customer_id": args.customer_id}
    refund = store.create_refund(args.customer_id, args.amount, args.reason)
    log.info("refund created id=%s amount=%s", refund["refund_id"], args.amount)
    return {"accepted": True, **refund}


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "get_customer_record",
            "Read one customer record by its identifier.",
            GetCustomerRecordInput,
            _get_customer_record,  # type: ignore[arg-type]
        ),
        Tool(
            "trigger_refund",
            "Start a refund for one customer.",
            TriggerRefundInput,
            _trigger_refund,  # type: ignore[arg-type]
        ),
    ]
}


def _field_errors(exc: ValidationError) -> list[dict[str, str]]:
    """Report the field and the reason. Never report the value, it may hold customer data."""
    return [
        {"field": ".".join(str(p) for p in err["loc"]) or "(root)", "reason": err["msg"]}
        for err in exc.errors()
    ]


def _fail(code: int, message: str, data: Any = None) -> McpError:
    return McpError(types.ErrorData(code=code, message=message, data=data))


async def _handle_call_tool(request: types.CallToolRequest) -> types.ServerResult:
    name = request.params.name
    tool = TOOLS.get(name)
    if tool is None:
        raise _fail(types.METHOD_NOT_FOUND, f"Unknown tool: {name}")

    arguments = request.params.arguments
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise _fail(types.INVALID_PARAMS, "The arguments field must be an object.")

    try:
        parsed = tool.model.model_validate(arguments)
    except ValidationError as exc:
        raise _fail(
            types.INVALID_PARAMS,
            f"Invalid arguments for {name}",
            {"errors": _field_errors(exc)},
        ) from exc

    try:
        result = await tool.handler(parsed)
    except Exception as exc:
        log.exception("tool %s failed", name)
        raise _fail(types.INTERNAL_ERROR, f"The tool {name} failed.") from exc

    return types.ServerResult(
        types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, indent=2))],
            structuredContent=result,
            isError=False,
        )
    )


def build_server() -> Server:
    server: Server = Server(SERVER_NAME, SERVER_VERSION)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [tool.to_mcp() for tool in TOOLS.values()]

    # Bypass the decorator so that a validation failure stays a JSON-RPC error.
    server.request_handlers[types.CallToolRequest] = _handle_call_tool
    return server
