"""Turn a Bearer token into a role."""

from enum import StrEnum

from fde.task2_mcp_gateway.settings import settings


class Role(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"


def resolve_role(authorization: str | None) -> Role | None:
    """Return the role, or None for a missing, malformed, or unknown token."""
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    role = settings.tokens.get(token.strip())
    return Role(role) if role in set(Role) else None
