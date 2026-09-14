"""Stream through the guardrail and report the arrival time of each delta."""

import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gateways.llm_stream_guard.sse import SseParser  # noqa: E402

REPLY = (
    "Sure. Reach the owner at ada@example.com, the tax id is 123-45-6789, "
    "and the card on file is 4111111111111111. Anything else?"
)


async def main() -> None:
    body = {"reply": REPLY, "chunk_size": 5, "delay_ms": 25}
    parser, pieces = SseParser(), []
    start = time.perf_counter()
    first = None

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8003", timeout=30) as client:
        async with client.stream("POST", "/v1/messages", json=body) as response:
            async for chunk in response.aiter_bytes():
                for event in parser.feed(chunk.decode()):
                    payload = event.json or {}
                    if payload.get("type") != "content_block_delta":
                        continue
                    first = first or time.perf_counter() - start
                    pieces.append(payload["delta"]["text"])

    total = time.perf_counter() - start
    print(f"  provider chunks: {len(REPLY) // body['chunk_size'] + 1} at {body['delay_ms']} ms each")
    print(f"  time to first token: {first * 1000:.0f} ms")
    print(f"  total stream time:   {total * 1000:.0f} ms")
    print(f"  deltas received:     {len(pieces)}")
    print(f"\n  source: {REPLY}")
    print(f"  client: {''.join(pieces)}")


if __name__ == "__main__":
    asyncio.run(main())
