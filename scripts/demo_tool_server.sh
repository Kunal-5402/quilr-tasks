#!/usr/bin/env bash
# strict validation and stdout isolation over the stdio transport.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== MCP tool server ==="
uv run python scripts/mcp_client.py
