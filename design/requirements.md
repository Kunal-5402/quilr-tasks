# Requirement register

Every rule that a service must follow, with an identifier. A test names the
identifier that it covers, and `tests/core/test_requirement_coverage.py` fails
if a rule here has no test.

The identifiers keep the form `T<n>-R<n>`, where `T1` to `T4` are the 4
services in the order below. The identifiers are stable, so a test marker never
needs to change when a document moves.

| Prefix | Service |
| --- | --- |
| `T1` | MCP tool server, `gateways.mcp_tool_server` |
| `T2` | MCP security gateway, `gateways.mcp_gateway` |
| `T3` | LLM stream guard, `gateways.llm_stream_guard` |
| `T4` | LLM model router, `gateways.llm_router` |

## T1 — MCP tool server

| ID | Requirement |
| --- | --- |
| T1-R1 | Expose the tool `get_customer_record`. Input: `customer_id`, format `CUST-XXXXX`. |
| T1-R2 | Expose the tool `trigger_refund`. Inputs: `customer_id`, `amount` (positive float), `reason` (minimum length 10). |
| T1-R3 | Use the official SDK (`mcp`). |
| T1-R4 | Enforce strict input schema validation with Pydantic. |
| T1-R5 | Reject invalid input with a standard JSON-RPC error code. |
| T1-R6 | Use the stdio transport. |
| T1-R7 | Reserve stdout for JSON-RPC messages only. |
| T1-R8 | Write all logs and debug output to stderr. |

Focus: stdio isolation, protocol compliance, validation edge cases.

## T2 — MCP security gateway

| ID | Requirement |
| --- | --- |
| T2-R1 | Act as an HTTP JSON-RPC reverse proxy between the agent client and a downstream MCP server. |
| T2-R2 | Read the `Authorization: Bearer <token>` header. Extract the role, `admin` or `viewer`. |
| T2-R3 | Forward the method `tools/list` transparently. |
| T2-R4 | For the method `tools/call`, read `params.name`. |
| T2-R5 | If `params.name` starts with `admin_`, the role must be `admin`. |
| T2-R6 | If the role is not `admin`, return JSON-RPC error `-32001 Unauthorized Tool Call`. |
| T2-R7 | Do not call the downstream server when the gateway rejects the request. |

Focus: wire format parsing, proxy middleware, method-level authorization.

## T3 — LLM stream guard

| ID | Requirement |
| --- | --- |
| T3-R1 | Provide a proxy endpoint that routes a text generation request to a provider. |
| T3-R2 | Stream the response back to the client. |
| T3-R3 | Intercept the response chunks in real time. |
| T3-R4 | Detect and redact emails, social security numbers, and credit card numbers. |
| T3-R5 | Replace a match with the literal text `[REDACTED]`. |
| T3-R6 | Do not accumulate the full response in memory. |
| T3-R7 | Keep the Time To First Token (TTFT) low. |

Focus: async chunking, buffer state, partial match handling, memory use.

## T4 — LLM model router

| ID | Requirement |
| --- | --- |
| T4-R1 | Accept completion requests and route them to a model provider. |
| T4-R2 | Apply a token-aware sliding window rate limiter. |
| T4-R3 | Use a limit of 50000 tokens each minute for each tenant API key. |
| T4-R4 | Fail over to a secondary provider if the primary returns HTTP 429. |
| T4-R5 | Fail over to a secondary provider if the primary exceeds a 3000 ms timeout. |
| T4-R6 | Return a standardized gateway error payload. |
| T4-R7 | Do not leak upstream stack traces or internal details to the client. |
| T4-R8 | Use on-disk SQLite as the database. |

Focus: async concurrency, timeout races, window eviction, error sanitization.
