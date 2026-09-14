import json
import time

import httpx
import pytest

from gateways.llm_stream_guard.sse import SseParser
from tests.live_server import serve


async def collect(gateway, body: dict) -> tuple[str, list[str]]:
    """Return the joined text and the list of event names."""
    parser, text, events = SseParser(), [], []
    async with gateway.stream("POST", "/v1/messages", json=body) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            for event in parser.feed(chunk.decode()):
                events.append(event.event)
                payload = event.json or {}
                if payload.get("type") == "content_block_delta":
                    text.append(payload["delta"]["text"])
    return "".join(text), events


@pytest.mark.req("T3-R1", "T3-R2", "T3-R3")
async def test_the_gateway_streams_the_provider_reply(gateway):
    text, events = await collect(gateway, {"reply": "hello there", "chunk_size": 3})

    assert text == "hello there"
    assert events[0] == "message_start"
    assert events[-1] == "message_stop"


@pytest.mark.req("T3-R4", "T3-R5")
@pytest.mark.parametrize("chunk_size", [1, 2, 3, 5, 11, 200])
async def test_pii_is_redacted_at_every_chunk_size(gateway, chunk_size):
    reply = "mail ada@example.com ssn 123-45-6789 card 4111111111111111 end"
    text, _ = await collect(gateway, {"reply": reply, "chunk_size": chunk_size})

    assert text == "mail [REDACTED] ssn [REDACTED] card [REDACTED] end"


@pytest.mark.req("T3-R4")
async def test_pii_at_the_end_of_the_stream_is_redacted(gateway):
    text, _ = await collect(gateway, {"reply": "write to ada@example.com", "chunk_size": 4})
    assert text == "write to [REDACTED]"


@pytest.mark.req("T3-R6", "T3-R7")
async def test_the_first_token_arrives_before_the_provider_finishes():
    """Over a real socket the first delta must not wait for the whole reply."""
    from gateways.llm_stream_guard import mock_provider, proxy

    body = {"reply": "one two three four five six seven", "chunk_size": 4, "delay_ms": 30}
    expected_total = body["delay_ms"] / 1000 * len(body["reply"]) / body["chunk_size"]

    async with serve(mock_provider.app) as provider_url, serve(proxy.app) as gateway_url:
        proxy.settings.provider_url = f"{provider_url}/v1/stream"
        async with httpx.AsyncClient(base_url=gateway_url, timeout=30.0) as client:
            start = time.perf_counter()
            first_delta = None
            parser = SseParser()
            async with client.stream("POST", "/v1/messages", json=body) as response:
                async for chunk in response.aiter_bytes():
                    for event in parser.feed(chunk.decode()):
                        if (event.json or {}).get("type") == "content_block_delta":
                            first_delta = time.perf_counter() - start
                            break
                    if first_delta is not None:
                        break

    assert first_delta is not None
    assert first_delta < expected_total / 2


@pytest.mark.req("T3-R2")
async def test_the_response_declares_an_unbuffered_event_stream(gateway):
    async with gateway.stream("POST", "/v1/messages", json={"reply": "hi"}) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["x-accel-buffering"] == "no"
        await response.aread()


@pytest.mark.req("T3-R1")
async def test_a_provider_failure_becomes_an_error_event(gateway, monkeypatch):
    from gateways.llm_stream_guard import proxy

    monkeypatch.setattr(proxy.settings, "provider_url", "http://provider/v1/missing")
    _, events = await collect(gateway, {"reply": "hi"})

    assert events == ["error"]


@pytest.mark.req("T3-R5")
async def test_every_frame_holds_valid_json(gateway):
    async with gateway.stream("POST", "/v1/messages", json={"reply": "a b c"}) as response:
        parser = SseParser()
        async for chunk in response.aiter_bytes():
            for event in parser.feed(chunk.decode()):
                json.loads(event.data)
