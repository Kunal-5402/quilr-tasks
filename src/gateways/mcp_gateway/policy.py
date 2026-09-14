"""Method level authorization rules."""

from gateways.mcp_gateway.auth import Role
from gateways.mcp_gateway.settings import settings

TRANSPARENT_METHODS = {"tools/list"}


def needs_admin(tool_name: str) -> bool:
    return tool_name.startswith(settings.admin_tool_prefix)


def is_allowed(method: str, tool_name: str | None, role: Role | None) -> bool:
    if method in TRANSPARENT_METHODS:
        return True
    if method == "tools/call" and tool_name and needs_admin(tool_name):
        return role is Role.ADMIN
    return True
