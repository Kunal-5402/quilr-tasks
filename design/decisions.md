# Decision records

One record for one decision. Each record holds the decision, the reason, and
the option that lost. Status is `accepted` unless stated.

A record may also hold a `Refinement after implementation` note. That note
marks a place where the code taught us something the design did not predict.
Read those first: they carry the most information for each line.

| Area | Records |
| --- | --- |
| Project wide | ADR-001, ADR-002, ADR-012, ADR-013, ADR-014, ADR-017 |
| MCP tool server | ADR-003, ADR-004 |
| MCP security gateway | ADR-005, ADR-006, ADR-015 |
| LLM stream guard | ADR-007, ADR-008 |
| LLM model router | ADR-009, ADR-010, ADR-011, ADR-016 |

---

## ADR-001 — Python 3.13 with `uv`

**Decision.** Use Python 3.13 and `uv` for the environment and the lock file.

**Why.** The user chose Python. `uv` is on the machine already. `uv` gives a
lock file, so the reviewer gets the same versions.

**Effect.** The reviewer runs `uv sync` and then `make test`.

---

## ADR-002 — One repository with a shared `core` package

**Decision.** Hold the 4 tasks in one package tree with one shared subpackage.

**Why.** The tasks repeat the same 3 concerns: a stderr logger, a JSON-RPC
model, and a safe error envelope. Duplication of these 3 concerns hides the
real work.

**Rejected option.** Four separate projects. This needs 4 installs and 4 test
runs. The reviewer spends time on setup, not on the code.

---

## ADR-003 — The tool server uses the low-level `mcp.server.Server`, not `FastMCP`

**Decision.** Build the MCP server with the low-level `Server` class. Register
the `CallToolRequest` handler directly in `server.request_handlers`. Validate
the input with Pydantic. Raise `McpError` with the code `INVALID_PARAMS`
(-32602).

**Refinement after implementation.** The `@server.call_tool()` decorator wraps
the handler in a `try/except Exception` that returns a tool result with
`isError=True`. A raised `McpError` never reaches the wire through it. Only a
raw entry in `server.request_handlers` lets the dispatcher convert the
`McpError` into a JSON-RPC error object.

**Why.** T1-R5 asks for a standard JSON-RPC error code. `FastMCP` reports a
tool failure as a normal result with `isError: true`. That is a tool-level
error, not a protocol-level error. The low-level API lets the server return a
real JSON-RPC error object.

**Effect.** More code than `FastMCP`, but the wire output matches the
requirement. The tests assert on the `error.code` field of the raw response.

---

## ADR-004 — Protect stdout with an explicit guard

**Decision.** At start, keep a reference to the real stdout for the transport.
Then replace `sys.stdout` with a writer that sends every write to stderr with
the prefix `[stdout-leak]`.

**Why.** T1-R7 is a score point. A print statement in a dependency breaks the
protocol silently. A guard turns a silent break into a visible warning.

**Rejected option.** Trust code review. A dependency can print at any time.

**Test.** Run the server as a subprocess. Send an `initialize` request and 2
tool calls. Assert that every line on stdout parses as JSON and holds the key
`jsonrpc`.

---

## ADR-005 — The gateway maps a token to a role with a static store

**Decision.** Use a dictionary from a token to a role, loaded from the
settings. Add an optional JSON Web Token (JWT) path behind a setting, off by
default.

**Why.** The task asks the gateway to "extract the user's role". A real
identity provider is out of scope. A static store keeps the demo runnable and
keeps the policy code in focus.

**Effect.** The README states this limit clearly. The `auth.py` module has one
function, `resolve_role(token) -> Role | None`, so a JWT backend replaces it
without a change to the policy.

---

## ADR-006 — The gateway denies a request before it opens a downstream connection

**Decision.** Run the policy check on the parsed body. Return the error from
the gateway process. Open no HTTP connection to the downstream server.

**Why.** T2-R7. A test asserts that the mock downstream request counter does
not increase on a denied call.

**Edge cases to handle.**

- A batch request (a JSON array). Check each member. Deny only the members that fail.
- A notification (no `id`). Return no error body for it, per JSON-RPC 2.0.
- A missing or malformed `Authorization` header. Return -32001 as well, with a clear message.
- A body that is not valid JSON. Return -32700 Parse error.
- A `tools/call` without `params.name`. Return -32602 Invalid params.

---

## ADR-007 — The stream guard uses a hold-back buffer, not full accumulation

**Decision.** The `StreamRedactor` keeps a small tail of the text. It emits
everything before the tail at once. The tail length is the longest text that
could still become a match.

**Why.** T3-R6 forbids full accumulation. A pattern can split across 2 chunks.
For example, chunk 1 ends with `a@b.c` and chunk 2 starts with `om`. If the
redactor emits chunk 1 at once, the email escapes.

**How the cut works.** The redactor cuts the buffer after the last separator
character inside a window of `MAX_HOLD` characters. No pattern contains a
separator, so a match can never cross that cut. `MAX_HOLD` is 153, the longest
text an email pattern can match.

**Refinement after implementation.** A run longer than `MAX_HOLD` with no
separator forces a cut at a fixed distance from the end. A match can cross that
position. The redactor therefore checks for a match that spans the fallback cut
and moves the cut to the start of that match. The buffer stays under
`2 * MAX_HOLD`, so it is still bounded.

**Refinement after implementation.** The held tail stays raw. The redactor
redacts only the text that it emits. If it redacted the buffer in place, a
complete but still growing match, such as `a@b.co` before `m` arrives, would
turn into `[REDACTED]m`.

**Rejected option.** Emit each chunk at once and redact each chunk alone. This
misses every split pattern. It fails T3-R4.

**Rejected option.** Collect the full text and redact at the end. This fails
T3-R6 and destroys the TTFT.

---

## ADR-008 — The stream guard rewrites the SSE frames, it does not pass them through

**Decision.** Parse each SSE frame. Take the delta text. Feed it to the
redactor. Build a new SSE frame from the safe output. Keep the original event
type and the original index fields.

**Why.** The redacted text has a different length from the source text. A
passthrough of the raw bytes cannot change the payload. The client needs valid
JSON in each `data:` line.

**Effect.** The gateway holds one frame at a time, not the whole stream.

---

## ADR-009 — The router stores the sliding window in SQLite with WAL mode

**Decision.** Create the database file on disk. Set `journal_mode=WAL` and
`busy_timeout=5000`. Store one row for each reservation.

Schema:

```sql
CREATE TABLE usage (
  id           TEXT PRIMARY KEY,      -- reservation id
  tenant       TEXT NOT NULL,
  tokens       INTEGER NOT NULL,      -- estimate first, actual after settle
  created_at   REAL NOT NULL,         -- unix seconds, float
  settled      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX usage_window ON usage (tenant, created_at);
```

**Why.** T4-R8 asks for on-disk SQLite. WAL mode lets a reader work while a
writer holds the write lock. `busy_timeout` handles a short lock conflict
without an application-level retry loop.

**Eviction.** Delete rows with `created_at < now - 60` before each check. This
is the sliding window. It is a true sliding window, not a fixed bucket,
because the check sums only the rows inside the last 60 seconds.

---

## ADR-010 — The router reserves tokens atomically

**Decision.** Do the evict, the sum, and the insert inside one
`BEGIN IMMEDIATE` transaction.

**Why.** T4-R2 and the concurrency score point. A check and then a separate
insert lets 2 parallel requests both pass the check. `BEGIN IMMEDIATE` takes
the write lock at the start of the transaction, so the second request waits.

**Two-phase counting.** The limiter reserves an estimate of the prompt tokens
plus the requested maximum output tokens. After the provider answers, the
router calls `settle` with the real total. The row updates to the real value.
This prevents an overshoot inside the window.

**Blocking call inside async code.** SQLite is synchronous. Run every database
call through `asyncio.to_thread`, so the event loop stays free.

---

## ADR-011 — The router races the timeout, it does not wait for the full call

**Decision.** Wrap the primary call in `asyncio.wait_for(..., timeout=3.0)`.
Catch `TimeoutError` and `httpx.HTTPStatusError` with the status 429. Then
call the secondary.

**Why.** T4-R4 and T4-R5. `wait_for` cancels the primary task, so the gateway
does not hold a dead connection.

**Detail.** The 3000 ms budget covers the primary only. The secondary gets its
own timeout from the settings. The total wall time is therefore bounded and
stated in the README.

---

## ADR-012 — One error envelope for every client-facing failure

**Decision.** Every gateway returns the envelope in `core/errors.py`. The
`request_id` is the only handle for support. The stack trace goes to stderr.

**Why.** T4-R6 and T4-R7.

**Test.** Force the primary provider to raise an exception with a secret string
in its message. Assert that the secret string is absent from the response body.

---

## ADR-013 — Mock providers, with a real adapter behind a setting

**Decision.** Ship a mock SSE provider for the stream guard, and 2 mock
providers for the router. Add an adapter for the real Anthropic API. The adapter is off by
default and needs `ANTHROPIC_API_KEY`.

**Why.** The tests must be deterministic. A 429 and a timeout are hard to
produce against a real endpoint. The adapter shows that the design fits a real
provider.

**Effect.** The mock providers take control parameters, such as
`?fail=429` and `?delay_ms=5000`, so the demo scripts show the failover.

---

## ADR-014 — `pytest` with `pytest-asyncio` and `httpx.ASGITransport`

**Decision.** Test the FastAPI applications in-process through
`httpx.ASGITransport`. Test the MCP server as a real subprocess.

**Why.** In-process tests are fast and need no port. The tool server needs a real
subprocess, because the stdout purity test is about the process boundary.


---

## ADR-015 — The gateway needs a valid token for every method

**Decision.** A request with no token, a wrong scheme, or an unknown token gets
-32001 for every method, `tools/list` included.

**Why.** The task names the roles `admin` and `viewer`. An unauthenticated
caller has no role at all. A gateway that forwards an anonymous request is not
a trust boundary. Authentication happens once for the HTTP request.
Authorization happens once for each JSON-RPC member.

---

## ADR-016 — The router opens SQLite with `check_same_thread=False`

**Decision.** Open the connection with `check_same_thread=False`. Guard every
database call with one `asyncio.Lock` inside the limiter.

**Why.** ADR-010 runs the blocking calls through `asyncio.to_thread`, which
uses a worker pool. SQLite refuses a connection used from a second thread. The
lock keeps the access to one caller at a time, so the flag is safe.

---

## ADR-017 — The requirement identifiers live in the tests

**Decision.** Mark each test with `@pytest.mark.req("T3-R4")`. Add a test that
fails when a requirement in `design/requirements.md` has no test.

**Why.** The trace stays true as the code changes. A reviewer can map a score
point to a test without reading every file.
