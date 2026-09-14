#!/usr/bin/env bash
# PII is redacted in flight, with the pattern split across chunks.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== LLM stream guard ==="
uv run python -m gateways.llm_stream_guard --provider >/dev/null 2>&1 &
PROVIDER=$!
uv run python -m gateways.llm_stream_guard >/dev/null 2>&1 &
GATEWAY=$!
trap 'kill $PROVIDER $GATEWAY 2>/dev/null || true' EXIT

until curl -sf http://127.0.0.1:8003/healthz >/dev/null; do sleep 0.2; done

uv run python scripts/stream_client.py
