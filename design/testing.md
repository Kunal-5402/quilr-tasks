# Testing

## Test strategy

| Level | Tool | Scope |
| --- | --- | --- |
| Unit | `pytest` | The redactor, the limiter, the policy, and the patterns. |
| Integration, in-process | `httpx.ASGITransport` | Each FastAPI application with a mock upstream. |
| Integration, subprocess | `subprocess` and pipes | The tool server only. The stdout purity test needs a real process. |
| Property | `pytest` parameters | The stream guard. Split the same text at every offset. |
| Concurrency | `asyncio.gather` | The router. 50 parallel reserve calls against one file. |

Every test names its requirement identifier in a marker, for example
`@pytest.mark.req("T3-R4")`. A short script then prints the coverage of the
requirements. This proves that each requirement has a test.

## Commands

```
make install    # uv sync
make test       # pytest -q
make lint       # ruff check && ruff format --check
make check      # lint + test + the requirement coverage report
make demo       # runs the 4 demo scripts in order
```

## Demo scripts

Each script starts the processes it needs, runs the calls, prints the output,
and stops the processes. Each script runs for under 30 seconds.

| Script | What it shows |
| --- | --- |
| `demo_tool_server.sh` | Sends `initialize`, `tools/list`, a valid call, and 3 invalid calls. Prints stdout and stderr in separate blocks. |
| `demo_gateway.sh` | Sends `tools/list`, an allowed call, and an `admin_` call with each role. Prints the downstream hit counter. |
| `demo_stream_guard.sh` | Streams an answer that holds PII split across chunks. Prints the time to first token. |
| `demo_router.sh` | Shows a normal call, a failover on 429, a failover on a timeout, and a burst against the token window. |

## Where to start reading

1. [README.md](../README.md), for the run commands.
2. [decisions.md](decisions.md), for the reason behind each choice.
3. `src/gateways/llm_stream_guard/redactor.py`, the hardest algorithm.
4. `src/gateways/llm_router/limiter.py`, the atomic reserve step.
5. The test files, which name the requirement each one covers.

## Known limits

The repository [README](../README.md) lists them, and each limit names the
single function that a real deployment replaces.
