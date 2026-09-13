# 2-day plan

**Status on 2026-09-13: task 1 to task 4 are complete. 93 tests pass.**
The runbook for task 5 is the only open item, and it waits for the missing text.

Start: 2026-09-12. Deliver: 2026-09-14.
Each block is approximately 3 hours. Each block ends with green tests and a commit.

## Day 0 — now (1 hour)

1. Read the design folder.
2. Create the repository skeleton. See `03-architecture.md`.
3. Add `pyproject.toml`, `uv.lock`, `pytest`, `ruff`, and the `Makefile`.
4. Add `src/fde/core/` with the error envelope, the logging setup, and the settings.
5. Commit: `chore: scaffold monorepo and shared core`.

Exit check: `make test` runs and reports 0 tests without an error.

## Day 1 morning — Task 1 (MCP server)

1. Write the Pydantic input models and the regular expression for `CUST-XXXXX`.
2. Write the in-memory customer store and the refund store.
3. Wire the low-level `mcp.server.Server` with `list_tools` and `call_tool`.
4. Add the stdout guard. See `tasks/task-1-mcp-server.md`.
5. Write the tests, including the stdout purity test.

Exit check: T1-R1 to T1-R8 pass.

## Day 1 afternoon — Task 2 (MCP gateway proxy)

1. Write the mock downstream MCP server as a FastAPI application.
2. Write the token store and the role resolver.
3. Write the gateway route, the JSON-RPC parser, and the policy check.
4. Write the tests for `tools/list`, an allowed `tools/call`, and a denied `admin_` call.

Exit check: T2-R1 to T2-R7 pass. The denied path never reaches the downstream server.

## Day 2 morning — Task 3 (streaming guardrail)

1. Write the mock provider that emits Server-Sent Events (SSE).
2. Write the `StreamRedactor` with the hold-back buffer.
3. Write the property tests that split the same text at every offset.
4. Measure the TTFT and the peak memory with the benchmark script.

Exit check: T3-R1 to T3-R7 pass. A pattern that is split across 2 chunks is redacted.

## Day 2 afternoon — Task 4 (rate limiter and fallback)

1. Create the SQLite schema and the migration function.
2. Write the sliding window limiter with an atomic reserve step.
3. Write the router with the timeout race and the 429 rule.
4. Write the error sanitizer.
5. Write the concurrency test with 50 parallel requests.

Exit check: T4-R1 to T4-R8 pass.

## Day 2 evening — wrap up (1.5 hours)

1. Write the top-level `README.md` with the run commands for each task.
2. Write `tasks/task-5-zero-trust.md` as a troubleshooting runbook.
3. Record the final decisions in `04-decisions.md`.
4. Run `make check`. Record the results in the README.

## Definition of done

- Each task runs with one command from the README.
- Each requirement identifier maps to at least one test.
- `ruff check` and `ruff format --check` report no problem.
- No task needs a real API key to run.
- The README states the known limits.

## Risk list

| Risk | Effect | Action |
| --- | --- | --- |
| The `mcp` SDK API changes between versions. | Task 1 fails to start. | Pin the exact version in `pyproject.toml`. |
| A regular expression backtracks on a long stream. | Task 3 becomes slow. | Use bounded patterns. Cap the hold-back buffer. |
| SQLite locks under parallel writes. | Task 4 fails the concurrency test. | Use WAL mode and `BEGIN IMMEDIATE`. Retry on a locked database. |
| Time runs short. | Task 4 is incomplete. | Task 4 is last. Its limiter and its router are separate modules. Ship the limiter first. |
