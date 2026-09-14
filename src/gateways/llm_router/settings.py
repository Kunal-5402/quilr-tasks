"""Settings for the model router. Every value has a working default."""

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class RouterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROUTER_")

    database_path: str = "var/router.sqlite3"
    token_limit_per_minute: int = 50_000
    window_seconds: int = 60
    primary_url: str = "http://127.0.0.1:8014/v1/completions"
    secondary_url: str = "http://127.0.0.1:8015/v1/completions"
    primary_timeout_seconds: float = 3.0
    secondary_timeout_seconds: float = 10.0
    # A static map stands in for a tenant directory.
    api_keys_json: str = json.dumps({"tenant-a-key": "tenant-a", "tenant-b-key": "tenant-b"})

    @property
    def api_keys(self) -> dict[str, str]:
        return json.loads(self.api_keys_json)


settings = RouterSettings()
