#!/usr/bin/env bash
# Task 1: strict validation and stdout isolation over the stdio transport.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== Task 1: MCP server ==="
uv run python scripts/mcp_client.py
