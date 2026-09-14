# MCP tool server

Package: `gateways.mcp_tool_server`. Transport: stdio.
Covers T1-R1 to T1-R8. See ADR-003 and ADR-004.

## Tools

### `get_customer_record`

Input: `customer_id`, a string. The pattern is `^CUST-[A-Z0-9]{5}$`.
Output: a JSON object with `customer_id`, `name`, `email`, `tier`, `balance`.
If the customer does not exist, return a tool error, not a protocol error.
A missing record is a valid request with an empty result.

### `trigger_refund`

Inputs:

- `customer_id`, the same pattern as above.
- `amount`, a float, greater than 0. Set an upper bound of 100000.0.
- `reason`, a string, minimum length 10, maximum length 500.

Output: a JSON object with `refund_id`, `status`, `amount`, `customer_id`.

## Validation design

```python
CUSTOMER_ID = Annotated[str, StringConstraints(pattern=r"^CUST-[A-Z0-9]{5}$")]

class GetCustomerRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    customer_id: CUSTOMER_ID

class TriggerRefundInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    customer_id: CUSTOMER_ID
    amount: float = Field(gt=0, le=100_000.0)
    reason: str = Field(min_length=10, max_length=500)
```

`extra="forbid"` rejects an unknown field. `strict=True` rejects the string
`"12.5"` for a float field. Both are score points for edge-case handling.

## Error mapping

| Case | JSON-RPC code | Name |
| --- | --- | --- |
| Unknown tool name | -32601 | Method not found |
| A Pydantic validation failure | -32602 | Invalid params |
| `params` is not an object | -32602 | Invalid params |
| A failure inside the tool body | -32603 | Internal error |
| Malformed JSON on the transport | -32700 | Parse error (the SDK handles it) |

The handler raises `McpError(ErrorData(code=INVALID_PARAMS, message=..., data=...))`.
The `data` field holds a compact list of the field errors. Each entry has the
field path and the reason. The `data` field holds no input value, because an
input value can hold customer data.

## The `inputSchema` that the server advertises

Generate it from the Pydantic model with `model_json_schema()`. The advertised
schema and the enforced schema then never differ. This is a protocol
compliance point.

## The stdout guard

```python
# stdout_guard.py
def install_guard() -> TextIO:
    real_stdout = sys.stdout
    sys.stdout = _StderrTee(prefix="[stdout-leak] ")
    return real_stdout
```

`__main__.py` calls `install_guard()` before it imports the server module.
It gives the real stdout to the stdio transport. Any `print()` elsewhere then
lands on stderr with a visible prefix.

Logging: one `logging.StreamHandler(sys.stderr)`. Set the level from the
environment variable `GATEWAYS_LOG_LEVEL`. Never add a handler for stdout.

## Test list

| Test | Requirement |
| --- | --- |
| `initialize` and `tools/list` return the 2 tools with a correct schema. | T1-R1, T1-R2, T1-R3 |
| `CUST-ABC12` is accepted. | T1-R1 |
| `cust-abc12`, `CUST-ABC1`, `CUST-ABC123`, and `""` return -32602. | T1-R5 |
| `amount = 0`, `amount = -5`, and `amount = "10"` return -32602. | T1-R4 |
| A `reason` with 9 characters returns -32602. | T1-R4 |
| An extra field returns -32602. | T1-R4 |
| An unknown tool returns -32601. | T1-R5 |
| Every stdout line of the subprocess parses as JSON with the key `jsonrpc`. | T1-R7 |
| A forced `print()` inside a tool appears on stderr, not on stdout. | T1-R8 |

## Run it

```
uv run python -m gateways.mcp_tool_server     # stdio, no port
bash scripts/demo_tool_server.sh              # a scripted session, stdout and stderr apart
```
