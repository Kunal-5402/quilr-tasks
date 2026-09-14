"""LLM gateway with a token budget and provider failover."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from gateways.core.errors import InvalidRequest, install_handlers, new_request_id
from gateways.core.logging import get_logger
from gateways.llm_router.limiter import TokenRateLimiter, estimate_tokens
from gateways.llm_router.providers import Provider
from gateways.llm_router.router import ModelRouter
from gateways.llm_router.settings import settings

log = get_logger(__name__)


class CompletionRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: int = Field(default=256, gt=0, le=8192)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=2.0))
    app.state.client = client
    app.state.limiter = TokenRateLimiter.open()
    app.state.router = ModelRouter(
        Provider("primary", settings.primary_url, client),
        Provider("secondary", settings.secondary_url, client),
    )
    yield
    await client.aclose()
    app.state.limiter.close()


app = FastAPI(title="LLM Gateway router", lifespan=lifespan)
install_handlers(app)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = new_request_id()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _resolve_tenant(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    tenant = settings.api_keys.get(token.strip()) if scheme.lower() == "bearer" else None
    if tenant is None:
        raise InvalidRequest(detail="missing or unknown api key")
    return tenant


@app.post("/v1/completions")
async def completions(
    body: CompletionRequest, request: Request, authorization: str | None = Header(default=None)
) -> JSONResponse:
    tenant = _resolve_tenant(authorization)
    limiter: TokenRateLimiter = request.app.state.limiter
    router: ModelRouter = request.app.state.router

    # Reserve the worst case first, then correct it with the real usage.
    reservation = await limiter.reserve(tenant, estimate_tokens(body.prompt) + body.max_tokens)
    try:
        result = await router.complete(body.model_dump())
    except Exception:
        # A failed call must not consume the tenant budget.
        await limiter.release(reservation)
        raise

    await limiter.settle(reservation, estimate_tokens(body.prompt) + result.tokens)
    return JSONResponse(
        {"text": result.text, "tokens": result.tokens, "tenant": tenant},
        headers={"X-Gateway-Provider": result.provider},
    )
