#!/usr/bin/env bash
# Task 2: the gateway denies an admin_ tool to a viewer before it calls downstream.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Task 2: MCP security gateway ==="
uv run python -m fde.task2_mcp_gateway --downstream >/dev/null 2>&1 &
DOWNSTREAM=$!
uv run python -m fde.task2_mcp_gateway >/dev/null 2>&1 &
GATEWAY=$!
trap 'kill $DOWNSTREAM $GATEWAY 2>/dev/null || true' EXIT

until curl -sf http://127.0.0.1:8002/healthz >/dev/null; do sleep 0.2; done

call() {  # role tool
  printf '  %-8s %-20s -> ' "$1" "$2"
  curl -s -X POST http://127.0.0.1:8002/mcp \
    -H "Authorization: Bearer $1-token" -H 'Content-Type: application/json' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"$2\"}}"
  echo
}

curl -s -X POST http://127.0.0.1:8012/stats/reset >/dev/null
printf '  %-8s %-20s -> ' viewer tools/list
curl -s -X POST http://127.0.0.1:8002/mcp -H 'Authorization: Bearer viewer-token' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
echo
call viewer get_customer_record
call viewer admin_reset_key
call admin  admin_reset_key

echo -n "  downstream counters: "
curl -s http://127.0.0.1:8012/stats
echo "  (the denied call never reached the downstream server)"
