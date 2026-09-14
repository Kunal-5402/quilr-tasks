"""Run the guardrail gateway. Add --provider to run the mock provider instead."""

import sys

import uvicorn

if __name__ == "__main__":
    if "--provider" in sys.argv:
        uvicorn.run("gateways.llm_stream_guard.mock_provider:app", host="127.0.0.1", port=8013)
    else:
        uvicorn.run("gateways.llm_stream_guard.proxy:app", host="127.0.0.1", port=8003)
