import httpx
import pytest

from fde.task2_mcp_gateway import mock_downstream
from fde.task2_mcp_gateway.proxy import app as gateway_app
from fde.task2_mcp_gateway.settings import settings

ADMIN = {"Authorization": "Bearer admin-token"}
VIEWER = {"Authorization": "Bearer viewer-token"}


@pytest.fixture
async def downstream():
    mock_downstream.STATS.update(requests=0, tool_calls=0)
    transport = httpx.ASGITransport(app=mock_downstream.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://downstream") as client:
        yield client


@pytest.fixture
async def gateway(downstream, monkeypatch):
    """The gateway talks to the mock downstream server in the same process."""
    monkeypatch.setattr(settings, "downstream_url", "http://downstream/mcp")
    gateway_app.state.client = downstream
    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client


@pytest.fixture
def stats():
    return mock_downstream.STATS
