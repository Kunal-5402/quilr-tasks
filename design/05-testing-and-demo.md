# Testing and demo

## Test strategy

| Level | Tool | Scope |
| --- | --- | --- |
| Unit | `pytest` | The redactor, the limiter, the policy, and the patterns. |
| Integration, in-process | `httpx.ASGITransport` | Each FastAPI application with a mock upstream. |
| Integration, subprocess | `subprocess` and pipes | Task 1 only. The stdout purity test needs a real process. |
| Property | `pytest` parameters | Task 3. Split the same text at every offset. |
| Concurrency | `asyncio.gather` | Task 4. 50 parallel reserve calls against one file. |

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
| `demo_task1.sh` | Sends `initialize`, `tools/list`, a valid call, and 3 invalid calls. Prints stdout and stderr in separate blocks. |
| `demo_task2.sh` | Sends `tools/list`, an allowed call, and an `admin_` call with each role. Prints the downstream hit counter. |
| `demo_task3.sh` | Streams a response that holds an email split across chunks. Prints the arrival time of each frame. |
| `demo_task4.sh` | Shows a normal call, a failover on 429, a failover on a timeout, and a 429 from the limiter. |

## What the reviewer reads first

1. `README.md`, the run commands.
2. `design/04-decisions.md`, the reason for each choice.
3. `src/fde/task3_stream_guardrail/redactor.py`, the hardest algorithm.
4. `src/fde/task4_router/limiter.py`, the atomic reserve step.
5. The test files.

## Known limits to state in the README

- The token store in Task 2 is static. A real deployment uses an identity provider.
- The token estimate in Task 4 is a character count divided by 4.
- The Luhn check reduces false positives but does not remove them.
- The mock providers replace the real model endpoints by default.
- The SQLite limiter fits one process or one host. A multi-host deployment needs Redis.
