# FDE Assessment — MCP & LLM Gateways

Four runnable services in one Python package:

| Task | What it does | Module |
| --- | --- | --- |
| 1 | MCP server with strict validation over stdio | `fde.task1_mcp_server` |
| 2 | MCP security gateway with tool level authorization | `fde.task2_mcp_gateway` |
| 3 | LLM gateway that redacts PII in a live stream | `fde.task3_stream_guardrail` |
| 4 | LLM gateway with a token budget and provider failover | `fde.task4_router` |

PII means personally identifiable information. Every external server is mocked,
so no task needs an API key or a network.

The design, the requirement trace, and the decision records are in
[design/](design/). Read [design/04-decisions.md](design/04-decisions.md) for
the reason behind each choice.

## Setup

```bash
make install     # uv sync
make check       # ruff + 93 tests
```

## Run a demo

Each script starts the processes it needs and stops them at the end.

```bash
bash scripts/demo_task1.sh    # validation errors and a clean stdout
bash scripts/demo_task2.sh    # an admin_ tool denied to a viewer
bash scripts/demo_task3.sh    # PII redacted across chunk boundaries
bash scripts/demo_task4.sh    # failover on 429, on timeout, and the token budget
make demo                     # all 4 in order
```

## Run a service

```bash
uv run python -m fde.task1_mcp_server                  # stdio, no port

uv run python -m fde.task2_mcp_gateway --downstream    # mock MCP server, port 8012
uv run python -m fde.task2_mcp_gateway                 # gateway, port 8002

uv run python -m fde.task3_stream_guardrail --provider # mock provider, port 8013
uv run python -m fde.task3_stream_guardrail            # gateway, port 8003

uv run python -m fde.task4_router --primary            # mock provider, port 8014
uv run python -m fde.task4_router --secondary          # mock provider, port 8015
uv run python -m fde.task4_router                      # gateway, port 8004
```

Demo tokens: `admin-token`, `viewer-token` (task 2) and `tenant-a-key`,
`tenant-b-key` (task 4).

## Task 1 — MCP server

Two tools: `get_customer_record` and `trigger_refund`. Pydantic enforces the
`CUST-XXXXX` format, a positive amount, and a reason of at least 10 characters.

The SDK decorator `@server.call_tool()` turns any exception into a tool result
with `isError=true`. The task asks for JSON-RPC error codes, so the server
registers the `CallToolRequest` handler directly and raises `McpError`:

| Case | Code |
| --- | --- |
| Bad field format, wrong type, or an extra field | -32602 |
| Unknown tool | -32601 |
| A failure inside the tool | -32603 |

`stdout_guard.install()` runs before any other import. It hands the real stdout
to the transport and replaces `sys.stdout`, so a stray `print()` lands on stderr
with the prefix `[stdout-leak]` instead of corrupting the protocol.

## Task 2 — MCP security gateway

The gateway authenticates the HTTP request once, then authorizes each JSON-RPC
member. A denied member never reaches the downstream server: the gateway
forwards only the members it approved.

- `tools/list` passes through unchanged.
- `tools/call` with a name that starts with `admin_` needs the role `admin`.
- A denial returns `-32001 Unauthorized Tool Call` with HTTP 200, because a
  JSON-RPC error is a valid JSON-RPC response.

Batches and notifications work. `/downstream/stats` counts the requests that
reached the mock server, which is how the test proves the gateway blocked them.

## Task 3 — Streaming PII guardrail

A PII pattern can split across 2 chunks, so `StreamRedactor` holds back the
tail that could still grow into a match, and emits everything before it at once.

The cut lands after the last separator character. No pattern contains a
separator, so a match can never cross the cut. If a run has no separator, the
cut falls back to a fixed distance from the end, and the code refuses to cut
through a match in progress. The buffer therefore stays under 306 characters
whatever the response length.

In normal prose the redactor holds one partial word. Measured on the demo:

| Measure | Value |
| --- | --- |
| Provider pace | 26 chunks, 25 ms each |
| Time to first token | about 110 ms, near 2 provider chunks |
| Total stream time | about 720 ms |

Patterns: email, United States social security number, and credit card. A card
candidate must also pass the Luhn check, which cuts false positives on long
digit runs.

## Task 4 — Rate limiter and failover

The limiter stores one row for each reservation in an on-disk SQLite file
(`var/router.sqlite3`, WAL mode). The evict, the sum, and the insert run inside
one `BEGIN IMMEDIATE` transaction, so 2 parallel requests cannot both pass a
full window.

Counting runs in 2 phases. The gateway reserves the prompt estimate plus
`max_tokens`, then settles the row with the real usage after the provider
answers. This prevents an overshoot inside the window.

The router gives the primary 3000 ms. A timeout, a 429, or a 5xx moves the
request to the secondary. `asyncio.wait_for` cancels the primary, so no dead
connection stays open. The answer carries `X-FDE-Provider`.

Every client-facing failure uses one envelope:

```json
{"error": {"type": "upstream_unavailable", "message": "...", "request_id": "...", "status": 503}}
```

The cause, the upstream message, and the traceback go to stderr only.

## Known limits

- The token stores in task 2 and task 4 are static maps. A real deployment
  reads an identity provider or a tenant directory.
- `estimate_tokens` divides the character count by 4. A real deployment uses
  the provider tokenizer. The settle step corrects the window total either way.
- The Luhn check reduces false positives on card numbers but does not remove them.
- The SQLite limiter covers one host. A multi-host deployment needs Redis or a
  shared database.
- The mock providers replace the real model endpoints. The provider clients
  speak plain HTTP JSON, so a real adapter replaces `Provider.complete` alone.
- A 5xx failover in task 4 is an addition, not a stated requirement.

## Test coverage

```bash
uv run pytest -q                       # 93 tests
uv run pytest -q -m "req"              # only the requirement tests
```

Every test names the requirement it covers with `@pytest.mark.req("T3-R4")`.
`tests/core/test_requirement_coverage.py` fails if a requirement listed in
`design/01-requirements.md` has no test.
