# Roadmap

## Delivered

| Capability | Service | State |
| --- | --- | --- |
| Customer tools over MCP, with strict input validation | `gateways.mcp_tool_server` | Done |
| Protocol level error codes for a malformed tool input | `gateways.mcp_tool_server` | Done |
| A stdout that stays pure JSON-RPC | `gateways.mcp_tool_server` | Done |
| Bearer token to role, for each HTTP request | `gateways.mcp_gateway` | Done |
| Tool level authorization, with a deny before the connection | `gateways.mcp_gateway` | Done |
| Batch and notification support | `gateways.mcp_gateway` | Done |
| PII redaction inside a live token stream | `gateways.llm_stream_guard` | Done |
| A bounded hold-back buffer, for a low time to first token | `gateways.llm_stream_guard` | Done |
| A token aware sliding window, for each tenant | `gateways.llm_router` | Done |
| Failover on 429, on 5xx, and on a timeout | `gateways.llm_router` | Done |
| One sanitized error envelope for every gateway | `gateways.core` | Done |

93 tests cover these. Every requirement in [requirements.md](requirements.md)
maps to at least one test.

## Next, in order of value

1. **Replace the static token maps.** `resolve_role` and `_resolve_tenant` are
   each one function. A real identity provider replaces one call. See
   [decisions.md](decisions.md) ADR-005.
2. **Use the provider tokenizer.** `estimate_tokens` divides the character
   count by 4. The settle step already corrects the window total, so this
   change only improves the reservation accuracy.
3. **Move the rate limiter state to Redis.** The SQLite limiter covers one
   host. The limiter interface does not change. See ADR-009.
4. **Add a circuit breaker in front of the primary provider.** Today every
   request pays the 3000 ms timeout while the primary is down.
5. **Make the PII pattern set configurable.** Today the 3 patterns are code.
   A deployment needs its own set, such as a national identity number.
6. **Add metrics.** A counter for a denied tool call, a histogram for the time
   to first token, and a gauge for the tenant window use.

## Known limits

See the `Known limits` section of the repository [README](../README.md). Each
limit names the single function that a real deployment replaces.
