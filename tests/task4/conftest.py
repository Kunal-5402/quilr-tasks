import httpx
import pytest

from fde.task4_router import providers
from fde.task4_router.app import app as gateway_app
from fde.task4_router.limiter import TokenRateLimiter
from fde.task4_router.router import ModelRouter
from fde.task4_router.settings import settings

TENANT_A = {"Authorization": "Bearer tenant-a-key"}


@pytest.fixture
def provider_apps():
    return {"primary": providers.make_app("primary"), "secondary": providers.make_app("secondary")}


@pytest.fixture
def behaviour(provider_apps):
    """Set the status or the delay of one mock provider."""

    def set_behaviour(name: str, **values) -> None:
        provider_apps[name].state.behaviour = providers.Behaviour(**values)

    return set_behaviour


@pytest.fixture
async def provider_clients(provider_apps):
    clients = {}
    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=provider_apps["primary"]), base_url="http://primary"
        ) as primary,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=provider_apps["secondary"]),
            base_url="http://secondary",
        ) as secondary,
    ):
        clients["primary"], clients["secondary"] = primary, secondary
        yield clients


@pytest.fixture
def router(provider_clients):
    return ModelRouter(
        providers.Provider("primary", "http://primary/v1/completions", provider_clients["primary"]),
        providers.Provider(
            "secondary", "http://secondary/v1/completions", provider_clients["secondary"]
        ),
        primary_timeout=0.2,
        secondary_timeout=0.5,
    )


@pytest.fixture
async def gateway(router, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "router.sqlite3"))
    limiter = TokenRateLimiter.open(settings.database_path, limit=1000)
    gateway_app.state.limiter = limiter
    gateway_app.state.router = router

    transport = httpx.ASGITransport(app=gateway_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://gateway") as client:
        yield client
    limiter.close()
