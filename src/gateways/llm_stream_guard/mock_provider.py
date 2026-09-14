"""Mock LLM provider that streams Server-Sent Events.

The client controls the reply text and the chunk size, so a test can force a
PII pattern to split across chunks.
"""

import asyncio
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from gateways.llm_stream_guard.sse import build_event

app = FastAPI(title="Mock LLM provider")

DEFAULT_REPLY = (
    "Sure. The account owner is ada@example.com, "
    "the social security number is 123-45-6789, "
    "and the card on file is 4111111111111111. Let me know if you need more."
)


class StreamRequest(BaseModel):
    prompt: str = ""
    reply: str = DEFAULT_REPLY
    chunk_size: int = 7
    delay_ms: int = 0


async def _stream(request: StreamRequest) -> AsyncIterator[bytes]:
    yield build_event("message_start", {"type": "message_start"})

    text = request.reply
    for start in range(0, len(text), request.chunk_size):
        if request.delay_ms:
            await asyncio.sleep(request.delay_ms / 1000)
        piece = text[start : start + request.chunk_size]
        yield build_event(
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": piece},
            },
        )

    yield build_event("message_stop", {"type": "message_stop"})


@app.post("/v1/stream")
async def stream(request: StreamRequest) -> StreamingResponse:
    return StreamingResponse(_stream(request), media_type="text/event-stream")
