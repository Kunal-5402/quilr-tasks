# Architecture

## Shape

One repository. One Python package named `fde`. One subpackage for each task.
One shared subpackage named `core`. One test package that mirrors the source tree.

```
fde-assessment/
  pyproject.toml           # one project, one lock file, one tool config
  Makefile                 # make install | test | lint | demo
  README.md                # how to run each task
  design/                  # this folder
  src/fde/
    core/
      logging.py           # stderr-only logger factory
      errors.py            # GatewayError, error envelope, sanitizer
      settings.py          # pydantic-settings, one Settings class
      jsonrpc.py           # JSON-RPC 2.0 request and error models
    task1_mcp_server/
      __main__.py          # entry point: python -m fde.task1_mcp_server
      schemas.py           # Pydantic input models
      store.py             # in-memory customer and refund data
      server.py            # MCP Server, list_tools, call_tool
      stdout_guard.py      # blocks accidental writes to stdout
    task2_mcp_gateway/
      __main__.py
      auth.py              # token to role
      policy.py            # tool name rules
      proxy.py             # FastAPI app, JSON-RPC parse, forward
      mock_downstream.py   # the mock MCP server behind the gateway
    task3_stream_guardrail/
      __main__.py
      patterns.py          # email, SSN, credit card patterns
      redactor.py          # StreamRedactor, hold-back buffer
      sse.py               # SSE frame parse and build
      proxy.py             # FastAPI app, streaming endpoint
      mock_provider.py     # SSE provider for the demo
    task4_router/
      __main__.py
      db.py                # SQLite connection, schema, WAL setup
      limiter.py           # sliding window token limiter
      providers.py         # primary and secondary provider clients
      router.py            # timeout race, 429 rule, failover
      app.py               # FastAPI app
  tests/
    task1/ task2/ task3/ task4/ core/
  scripts/
    demo_task1.sh ... demo_task4.sh
    bench_ttft.py
```

## Why one repository

The 4 tasks share the error envelope, the logger, and the JSON-RPC models.
One install and one test command make review fast.
Each task still runs alone with its own `__main__.py`.

## Shared core

### `core/logging.py`

One function, `get_logger(name)`. The handler writes to `sys.stderr` only.
Task 1 depends on this rule. The other tasks use the same function for
consistency.

### `core/errors.py`

One exception class, `GatewayError`, with a `code`, a `message`, and an
optional `detail`. One function, `to_client_payload(exc, request_id)`, that
returns the safe envelope. The `detail` field never reaches the client. The
logger writes the `detail` and the traceback to stderr.

Client envelope:

```json
{
  "error": {
    "type": "upstream_unavailable",
    "message": "The upstream model provider did not answer in time.",
    "request_id": "01J...",
    "status": 503
  }
}
```

### `core/jsonrpc.py`

Pydantic models for a JSON-RPC 2.0 request, a response, and an error.
Task 1 and Task 2 both use them. The models keep `id` as `str | int | None`.

## Data flow

### Task 2

```
agent client --HTTP POST /mcp--> gateway
   1. read Authorization header -> role
   2. parse JSON-RPC body
   3. method == tools/list  -> forward
   4. method == tools/call  -> check params.name against the role
        allowed  -> forward
        denied   -> return -32001, do not forward
   5. return the downstream answer unchanged
```

### Task 3

```
client --POST /v1/messages (stream=true)--> gateway --> mock provider (SSE)
provider chunk -> sse.parse -> delta text -> StreamRedactor.feed(text)
StreamRedactor returns the safe prefix now and holds an unsafe tail
gateway re-encodes the safe prefix as an SSE frame and yields it at once
end of stream -> StreamRedactor.flush() -> final frame
```

### Task 4

```
POST /v1/completions
   1. resolve the tenant from the API key
   2. estimate the prompt tokens
   3. limiter.reserve(tenant, estimate)  -> SQLite, atomic
        over the limit -> 429 with the standard envelope
   4. call the primary with a 3000 ms timeout
        429 or timeout -> call the secondary
        both fail      -> 503 with the standard envelope
   5. limiter.settle(tenant, reservation_id, actual_tokens)
```

## Cross-cutting rules

- Every module writes logs to stderr.
- Every HTTP client is `httpx.AsyncClient`. One client for each application, opened on startup.
- Every application is a FastAPI application, run with `uvicorn`.
- No task needs a network or an API key to run its tests.
- Type hints on every public function. `ruff` enforces the style.
