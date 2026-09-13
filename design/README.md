# Design folder — FDE Assessment (MCP & LLM Gateways)

This folder holds the plan, the architecture, and the recorded decisions.
Write code only after you read `03-architecture.md` and `04-decisions.md`.

| File | Purpose |
| --- | --- |
| `01-requirements.md` | Every requirement from the PDF, with a trace identifier. |
| `02-plan-2-day.md` | The 2-day schedule and the definition of done. |
| `03-architecture.md` | Repository layout, shared core, and data flow. |
| `04-decisions.md` | Decision records (ADR). One record for one decision. |
| `05-testing-and-demo.md` | Test strategy, demo scripts, and review path. |
| `tasks/task-1-mcp-server.md` | Design for Task 1. |
| `tasks/task-2-mcp-gateway.md` | Design for Task 2. |
| `tasks/task-3-streaming-guardrail.md` | Design for Task 3. |
| `tasks/task-4-router-fallback.md` | Design for Task 4. |
| `tasks/task-5-zero-trust.md` | Placeholder. The PDF does not contain Task 5. |

Status: implemented. 93 tests pass. See the repository `README.md` to run it.
Date: 2026-09-13. Deadline: 2026-09-14.

The decision records hold a `Refinement after implementation` note wherever the
code taught us something that the design did not predict.
