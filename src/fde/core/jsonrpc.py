"""JSON-RPC 2.0 wire models shared by the MCP server and the MCP gateway."""

from typing import Any

from pydantic import BaseModel, Field

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
UNAUTHORIZED_TOOL_CALL = -32001

RequestId = str | int | None


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    id: RequestId = None
    params: Any = None

    @property
    def is_notification(self) -> bool:
        """A notification carries no id, so it never gets a response."""
        return self.id is None


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: Any = None


class JsonRpcErrorResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: RequestId = None
    error: JsonRpcError


def error_response(request_id: RequestId, code: int, message: str, data: Any = None) -> dict:
    return JsonRpcErrorResponse(
        id=request_id, error=JsonRpcError(code=code, message=message, data=data)
    ).model_dump(exclude_none=True)


class ToolCallParams(BaseModel):
    """The params of a tools/call request. Extra keys stay untouched for forwarding."""

    name: str = Field(min_length=1)
    arguments: dict[str, Any] | None = None
