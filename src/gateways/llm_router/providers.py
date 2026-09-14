"""Model providers.

The client side raises 2 typed failures, so the router never reads a status
code or an upstream message. The mock providers replace real endpoints and can
be told to return 429 or to stall.
"""

import asyncio
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gateways.core.logging import get_logger

log = get_logger(__name__)


class UpstreamRateLimited(Exception):
    """The provider answered 429."""


class UpstreamFailed(Exception):
    """The provider answered 5xx, or the connection broke."""


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    text: str
    tokens: int


class Provider:
    def __init__(self, name: str, url: str, client: httpx.AsyncClient) -> None:
        self.name = name
        self.url = url
        self._client = client

    async def complete(self, payload: dict) -> ProviderResult:
        try:
            response = await self._client.post(self.url, json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamFailed(str(exc)) from exc

        if response.status_code == 429:
            raise UpstreamRateLimited(f"{self.name} returned 429")
        if response.status_code >= 500:
            raise UpstreamFailed(f"{self.name} returned {response.status_code}")
        if response.status_code >= 400:
            # A client error repeats on the backup provider, so it is not a failover case.
            raise UpstreamFailed(f"{self.name} rejected the request: {response.status_code}")

        body = response.json()
        return ProviderResult(self.name, body["text"], body["tokens"])


# --- The mock provider application -------------------------------------------------


class Behaviour(BaseModel):
    """Test control: force a status code or a delay."""

    status: int = 200
    delay_ms: int = 0


class CompletionBody(BaseModel):
    prompt: str = ""
    max_tokens: int = 256


def make_app(name: str) -> FastAPI:
    """Build one mock provider. Each app keeps its own behaviour."""
    app = FastAPI(title=f"Mock model provider {name}")
    app.state.behaviour = Behaviour()

    @app.post("/control")
    async def control(behaviour: Behaviour, request: Request) -> Behaviour:
        request.app.state.behaviour = behaviour
        return behaviour

    @app.post("/v1/completions")
    async def completions(body: CompletionBody, request: Request) -> JSONResponse:
        behaviour: Behaviour = request.app.state.behaviour
        if behaviour.delay_ms:
            await asyncio.sleep(behaviour.delay_ms / 1000)
        if behaviour.status != 200:
            return JSONResponse({"detail": "mock failure"}, status_code=behaviour.status)

        text = f"{name} answered: {body.prompt[:40]}"
        return JSONResponse({"text": text, "tokens": max(1, len(text) // 4)})

    return app
