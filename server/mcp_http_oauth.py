"""Lightweight OAuth 2.1 for MCP HTTP using PersonalAuthProvider.

Enabled when ``MCP_HTTP_AUTH=oauth`` and ``MCP_OAUTH_BASE_URL`` is set.
"""

from __future__ import annotations

import os
from typing import Any

# Claude.ai, Claude Code (cursor://), and local dev redirects.
DEFAULT_REDIRECT_DOMAINS = [
    "claude.ai",
    "claude.com",
    "localhost",
    "anysphere.cursor-mcp",
]


def resolve_http_auth_mode() -> str:
    """Return ``oauth``, ``api_key``, or ``none`` for HTTP transport auth."""
    explicit = os.environ.get("MCP_HTTP_AUTH", "").strip().lower()
    if explicit in {"oauth", "api_key", "none"}:
        return explicit
    if os.environ.get("MCP_OAUTH_BASE_URL", "").strip():
        return "oauth"
    if os.environ.get("MCP_API_KEY", "").strip():
        return "api_key"
    return "none"


def _parse_redirect_domains(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_REDIRECT_DOMAINS)
    domains = [part.strip() for part in raw.split(",") if part.strip()]
    return domains or list(DEFAULT_REDIRECT_DOMAINS)


def build_oauth_provider() -> Any | None:
    """Build PersonalAuthProvider when OAuth mode is active."""
    if resolve_http_auth_mode() != "oauth":
        return None

    base_url = os.environ.get("MCP_OAUTH_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise ValueError(
            "MCP_HTTP_AUTH=oauth requires MCP_OAUTH_BASE_URL "
            "(e.g. https://provena-mcp.example.com)"
        )

    from server.personal_auth import PersonalAuthProvider

    # Browser gate (mcp_oauth_password_gate) verifies MCP_OAUTH_PASSWORD before /authorize.
    # Do not also enforce password inside authorize(); Claude/Cursor never embed it in state.
    state_dir = os.environ.get("MCP_OAUTH_STATE_DIR", ".oauth-state").strip()
    redirect_domains = _parse_redirect_domains(
        os.environ.get("MCP_OAUTH_ALLOWED_REDIRECT_DOMAINS")
    )

    return PersonalAuthProvider(
        base_url=base_url,
        password=None,
        allowed_redirect_domains=redirect_domains,
        state_dir=state_dir,
    )
