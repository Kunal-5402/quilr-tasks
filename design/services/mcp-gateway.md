# MCP security gateway

Package: `gateways.mcp_gateway`. Port 8002.
Covers T2-R1 to T2-R7. See ADR-005, ADR-006, and ADR-015.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /mcp` | The gateway. The agent client sends JSON-RPC here. |
| `GET /healthz` | A liveness check. |
| `POST /downstream/mcp` | The mock MCP server. It runs as a separate process in the demo. |

## Authentication

`auth.py` holds one function:

```python
def resolve_role(authorization: str | None) -> Role | None
```

It reads `Authorization: Bearer <token>`. It looks the token up in the token
store. The store comes from the setting `MCP_GATEWAY_TOKENS_JSON`, a JSON map from a token
to a role. The default map holds 2 entries for the demo:
`admin-token -> admin` and `viewer-token -> viewer`.

The function returns `None` for a missing header, a wrong scheme, or an
unknown token.

## Policy

`policy.py` holds one function:

```python
def is_allowed(method: str, tool_name: str | None, role: Role | None) -> bool
```

Rules:

1. The method `tools/list` is always allowed. The gateway forwards it.
2. The method `tools/call` with a tool name that starts with `admin_` needs the role `admin`.
3. Every other method and every other tool name is allowed.

The prefix is a setting, so the rule is data, not a hard-coded string.

## Request handling steps

1. Read the raw body. Parse it as JSON. On a failure, return -32700.
2. Accept a single object or a batch array.
3. For each member, read `method`, `id`, and `params`.
4. If the method is `tools/call`, read `params.name`. If `params` is not an
   object, or `name` is missing, return -32602 for that member.
5. Run `is_allowed`. On a failure, build the -32001 error for that member.
6. Collect the members that pass. If the list is empty, answer at once and
   open no downstream connection.
7. Forward the passing members as one downstream request.
8. Merge the downstream responses with the locally built errors. Keep the
   order of the original batch. Drop the notifications, which have no `id`.

## The error object

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "error": {
    "code": -32001,
    "message": "Unauthorized Tool Call",
    "data": {"tool": "admin_reset_key", "required_role": "admin"}
  }
}
```

The HTTP status stays 200, because a JSON-RPC error is a valid JSON-RPC
response. The README states this choice.

## Forwarding

One `httpx.AsyncClient`, opened in the FastAPI lifespan. The gateway copies
the `Content-Type` header. It does not copy the `Authorization` header to the
downstream server by default, because the gateway is the trust boundary. A
setting turns the pass-through on.

## Test list

| Test | Requirement |
| --- | --- |
| `tools/list` with a viewer token reaches the downstream server unchanged. | T2-R3 |
| `tools/call` with `get_customer_record` and a viewer token is forwarded. | T2-R4 |
| `tools/call` with `admin_reset_key` and a viewer token returns -32001. | T2-R5, T2-R6 |
| The same denied call does not increase the downstream request counter. | T2-R7 |
| `tools/call` with `admin_reset_key` and an admin token is forwarded. | T2-R5 |
| A missing header returns -32001. | T2-R2 |
| A body that is not JSON returns -32700. | T2-R1 |
| A batch with 1 allowed and 1 denied member returns 1 result and 1 error. | T2-R1 |
| The response `id` always matches the request `id`. | T2-R1 |

## Run it

```
uv run python -m gateways.mcp_gateway --downstream   # the mock MCP server, port 8012
uv run python -m gateways.mcp_gateway                # the gateway, port 8002
bash scripts/demo_gateway.sh                         # both, plus the calls
```
