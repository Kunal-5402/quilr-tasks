"""Run the gateway. Add --downstream to run the mock MCP server instead."""

import sys

import uvicorn

if __name__ == "__main__":
    if "--downstream" in sys.argv:
        uvicorn.run("fde.task2_mcp_gateway.mock_downstream:app", host="127.0.0.1", port=8012)
    else:
        uvicorn.run("fde.task2_mcp_gateway.proxy:app", host="127.0.0.1", port=8002)
