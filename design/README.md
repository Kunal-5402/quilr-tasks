# Design

This folder holds the reasoning behind the code. Read it before you change a
service.

| Document | What it answers |
| --- | --- |
| [requirements.md](requirements.md) | What each service must do, with a trace identifier for every rule. |
| [architecture.md](architecture.md) | How the services fit together, and what they share. |
| [decisions.md](decisions.md) | Why each design choice is what it is. 17 records. |
| [testing.md](testing.md) | How the suite proves the requirements. |
| [roadmap.md](roadmap.md) | What is delivered, and what comes next. |

One document for each service:

| Service | Document |
| --- | --- |
| MCP tool server | [services/mcp-tool-server.md](services/mcp-tool-server.md) |
| MCP security gateway | [services/mcp-gateway.md](services/mcp-gateway.md) |
| LLM stream guard | [services/llm-stream-guard.md](services/llm-stream-guard.md) |
| LLM model router | [services/llm-router.md](services/llm-router.md) |

Operations:

| Document | What it answers |
| --- | --- |
| [operations/zero-trust-runbook.md](operations/zero-trust-runbook.md) | Why a gateway breaks inside a zero-trust network, and what to check. |

## How to read a decision record

Each record in [decisions.md](decisions.md) holds the decision, the reason, and
the option that lost. A record may also hold a `Refinement after
implementation` note. That note marks a place where the code taught us
something the design did not predict. Those notes are the most useful part of
the folder.
