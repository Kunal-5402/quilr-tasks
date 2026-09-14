import httpx
import pytest

from gateways.llm_stream_guard import mock_provider
from gateways.llm_stream_guard.proxy import app as gateway_app
from gateways.llm_stream_guard.proxy import settings


@pytest.fixture
async def provider():
    transport = httpx.ASGITransport(app=mock_provider.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://provider") as client:
        yield client


@pytest.fixture
async def gateway(provider, monkeypatch):
    monkeypatch.setattr(settings, "provider_url", "http://provider/v1/stream")
    gateway_app.state.client = provider
    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client
