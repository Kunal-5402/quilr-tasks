"""Settings for the MCP gateway. Every value has a working default."""

import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_GATEWAY_")

    downstream_url: str = "http://127.0.0.1:8012/mcp"
    admin_tool_prefix: str = "admin_"
    forward_authorization: bool = False
    # A static map stands in for an identity provider. See design/04-decisions.md ADR-005.
    tokens_json: str = json.dumps({"admin-token": "admin", "viewer-token": "viewer"})

    @property
    def tokens(self) -> dict[str, str]:
        return json.loads(self.tokens_json)


settings = GatewaySettings()
