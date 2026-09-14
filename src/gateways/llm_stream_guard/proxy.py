"""LLM gateway with a streaming PII guardrail.

The gateway forwards each redacted delta as soon as it is safe. It holds one
frame and a short tail, never the whole response.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from gateways.core.errors import UpstreamUnavailable, install_handlers
from gateways.core.logging import get_logger
from gateways.llm_stream_guard.redactor import StreamRedactor
from gateways.llm_stream_guard.sse import SseParser, build_event

log = get_logger(__name__)

TEXT_DELTA_EVENT = "content_block_delta"
STOP_EVENT = "message_stop"


class ProxySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDE_STREAM_")

    provider_url: str = "http://127.0.0.1:8013/v1/stream"


settings = ProxySettings()


class CompletionRequest(BaseModel):
    prompt: str = ""
    reply: str | None = None
    chunk_size: int | None = None
    delay_ms: int | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0))
    yield
    await app.state.client.aclose()


app = FastAPI(title="LLM Gateway streaming guardrail", lifespan=lifespan)
install_handlers(app)


def _delta_text(payload: dict | None) -> str | None:
    if not payload or payload.get("type") != "content_block_delta":
        return None
    return payload.get("delta", {}).get("text")


async def _guarded_stream(client: httpx.AsyncClient, body: dict) -> AsyncIterator[bytes]:
    parser, redactor = SseParser(), StreamRedactor()

    async with client.stream("POST", settings.provider_url, json=body) as upstream:
        upstream.raise_for_status()
        # aiter_bytes keeps the latency of the provider; it adds no line buffering.
        async for chunk in upstream.aiter_bytes():
            for event in parser.feed(chunk.decode("utf-8", errors="replace")):
                payload = event.json
                text = _delta_text(payload)

                if text is None:
                    if event.event == STOP_EVENT and (tail := redactor.flush()):
                        yield _text_event(tail)
                    yield build_event(event.event, payload or {})
                    continue

                if safe := redactor.feed(text):
                    yield _text_event(safe)

    # The provider may end without a stop event.
    if tail := redactor.flush():
        yield _text_event(tail)


def _text_event(text: str) -> bytes:
    return build_event(
        TEXT_DELTA_EVENT,
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
    )


@app.post("/v1/messages")
async def messages(request: CompletionRequest) -> StreamingResponse:
    client: httpx.AsyncClient = app.state.client
    body = request.model_dump(exclude_none=True)

    async def body_stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in _guarded_stream(client, body):
                yield chunk
        except httpx.HTTPError as exc:
            # The stream has already started, so report the failure inside it.
            log.warning("provider stream failed: %s", exc)
            yield build_event("error", {"type": "error", "error": UpstreamUnavailable.message})

    return StreamingResponse(
        body_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
