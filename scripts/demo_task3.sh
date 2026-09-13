#!/usr/bin/env bash
# Task 3: PII is redacted in flight, with the pattern split across chunks.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Task 3: streaming PII guardrail ==="
uv run python -m fde.task3_stream_guardrail --provider >/dev/null 2>&1 &
PROVIDER=$!
uv run python -m fde.task3_stream_guardrail >/dev/null 2>&1 &
GATEWAY=$!
trap 'kill $PROVIDER $GATEWAY 2>/dev/null || true' EXIT

until curl -sf http://127.0.0.1:8003/healthz >/dev/null; do sleep 0.2; done

uv run python scripts/stream_client.py
