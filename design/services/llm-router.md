# LLM model router

Package: `gateways.llm_router`. Port 8004.
Covers T4-R1 to T4-R8. See ADR-009, ADR-010, ADR-011, and ADR-012.

## Module split

| Module | Responsibility |
| --- | --- |
| `db.py` | Open SQLite, set WAL mode, create the schema. |
| `limiter.py` | `reserve`, `settle`, `release`. No knowledge of HTTP. |
| `providers.py` | `call(request) -> ProviderResponse`. Primary and secondary. |
| `router.py` | The timeout race, the 429 rule, the failover order. |
| `app.py` | The FastAPI route. It joins the limiter and the router. |

The limiter and the router are independent. Either one works alone, and each
one is testable without HTTP. `app.py` is the only module that knows both.

## The limiter

```python
async def reserve(tenant: str, tokens: int) -> Reservation
async def settle(reservation: Reservation, actual_tokens: int) -> None
async def release(reservation: Reservation) -> None
async def used(tenant: str) -> int
```

`reserve` raises `RateLimitExceeded` when the window is full. The exception
holds `retry_after_seconds`, computed from the oldest row in the window.

### The transaction

```sql
BEGIN IMMEDIATE;
DELETE FROM usage WHERE created_at < :cutoff;
SELECT COALESCE(SUM(tokens), 0) FROM usage WHERE tenant = :tenant;
-- if the sum plus the new tokens is over the limit -> ROLLBACK and reject
INSERT INTO usage (id, tenant, tokens, created_at) VALUES (...);
COMMIT;
```

`BEGIN IMMEDIATE` takes the write lock at the start. A second parallel
transaction waits. This removes the check-then-act race. See ADR-010.

`release` deletes the row. The router calls it when both providers fail, so a
failed request does not consume the tenant budget.

### The token estimate

`estimate_tokens(text)` uses a simple rule: the character count divided by 4.
The README states that a real deployment uses the provider tokenizer. The
two-phase count in ADR-010 corrects the estimate after the call, so the
estimate accuracy does not change the window total.

## The router

```python
async def route(request: CompletionRequest) -> CompletionResult:
    try:
        return await asyncio.wait_for(primary.call(request), timeout=3.0)
    except (TimeoutError, UpstreamRateLimited):
        log.warning("primary failed, failing over", extra={...})
        return await secondary.call(request)
```

Rules:

1. A timeout after 3000 ms triggers the failover. T4-R5.
2. An HTTP 429 from the primary triggers the failover. T4-R4.
3. An HTTP 5xx from the primary also triggers the failover. This is an
   addition, not a requirement. The README marks it.
4. An HTTP 4xx other than 429 does not trigger the failover. The request is
   wrong, so the secondary fails in the same way.
5. A failure of the secondary returns 503 with the standard envelope.

`asyncio.wait_for` cancels the primary task on a timeout. The router then
closes the response. This frees the connection.

The response carries the header `X-Gateway-Provider` with the name of the provider
that answered. The demo uses this header to show the failover.

## Error sanitization

`core/errors.py` maps every internal failure to one of 4 client types:

| Type | HTTP status | When |
| --- | --- | --- |
| `rate_limit_exceeded` | 429 | The tenant window is full. Adds `Retry-After`. |
| `upstream_unavailable` | 503 | Both providers failed. |
| `invalid_request` | 400 | The body failed validation. |
| `internal_error` | 500 | Anything else. |

The handler logs the exception and the traceback to stderr with the
`request_id`. The client body holds only the 4 fields in ADR-012.
A test asserts that a secret string in an upstream message never appears in
the client body. See T4-R7.

## Test list

| Test | Requirement |
| --- | --- |
| A single request under the limit passes. | T4-R2 |
| A request that exceeds 50000 tokens in the window returns 429 with `Retry-After`. | T4-R3 |
| 50 parallel requests consume the budget exactly one time each. The total never exceeds the limit. | T4-R2 |
| A row older than 60 seconds does not count. The test moves a fake clock. | T4-R2 |
| Two tenant keys do not share a budget. | T4-R3 |
| A primary that returns 429 causes a secondary answer. `X-Gateway-Provider` is `secondary`. | T4-R4 |
| A primary that delays 5000 ms causes a secondary answer within about 3100 ms. | T4-R5 |
| A primary failure at 2900 ms still returns the primary answer. | T4-R5 |
| Both providers fail. The body matches the envelope and holds no stack trace. | T4-R6, T4-R7 |
| The database file exists on disk after a run. | T4-R8 |
| A failed request releases its reservation. | T4-R2 |

## Run it

```
uv run python -m gateways.llm_router --primary     # the mock primary, port 8014
uv run python -m gateways.llm_router --secondary   # the mock secondary, port 8015
uv run python -m gateways.llm_router               # the gateway, port 8004
bash scripts/demo_router.sh                        # all 3, plus the failover cases
```
