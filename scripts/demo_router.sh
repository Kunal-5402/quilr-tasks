#!/usr/bin/env bash
# failover on 429, failover on timeout, and the token budget.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== LLM model router ==="
rm -f var/router.sqlite3*
uv run python -m gateways.llm_router --primary   >/dev/null 2>&1 & P=$!
uv run python -m gateways.llm_router --secondary >/dev/null 2>&1 & S=$!
uv run python -m gateways.llm_router             >/dev/null 2>&1 & G=$!
trap 'kill $P $S $G 2>/dev/null || true' EXIT

until curl -sf http://127.0.0.1:8004/healthz >/dev/null; do sleep 0.2; done

behave() { curl -s -X POST "http://127.0.0.1:$1/control" -H 'Content-Type: application/json' \
  -d "$2" >/dev/null; }

ask() {  # label max_tokens
  printf '  %-26s -> ' "$1"
  curl -s -o /tmp/gw_body -w '%{http_code}' -X POST http://127.0.0.1:8004/v1/completions \
    -H 'Authorization: Bearer tenant-a-key' -H 'Content-Type: application/json' \
    -D /tmp/gw_head -d "{\"prompt\":\"hello gateway\",\"max_tokens\":$2"'}'
  printf ' provider=%s ' "$(grep -i '^x-gateway-provider' /tmp/gw_head | tr -d '\r' | cut -d' ' -f2)"
  head -c 150 /tmp/gw_body; echo
}

behave 8014 '{"status":200}'; behave 8015 '{"status":200}'
ask "healthy primary" 64

behave 8014 '{"status":429}'
ask "primary returns 429" 64

behave 8014 '{"status":200,"delay_ms":5000}'
ask "primary stalls 5000 ms" 64
echo "    (the 3000 ms budget cut the primary off)"

behave 8014 '{"status":500}'; behave 8015 '{"status":500}'
ask "both providers fail" 64

behave 8014 '{"status":200}'; behave 8015 '{"status":200}'
echo "  burst of 10 parallel requests, 8192 tokens each, against a 50000 token window:"
seq 10 | xargs -P 10 -I{} curl -s -o /dev/null -w '%{http_code}\n' \
  -X POST http://127.0.0.1:8004/v1/completions \
  -H 'Authorization: Bearer tenant-a-key' -H 'Content-Type: application/json' \
  -d '{"prompt":"hello gateway","max_tokens":8192}' | sort | uniq -c | sed 's/^/    /'
echo "    (200 = served, 429 = the token window is full)"
