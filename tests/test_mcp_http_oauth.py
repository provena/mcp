import pytest

from server.mcp_http_oauth import (
    DEFAULT_REDIRECT_DOMAINS,
    build_oauth_provider,
    resolve_http_auth_mode,
)


def test_resolve_http_auth_mode_defaults_to_none(monkeypatch):
    monkeypatch.delenv("MCP_HTTP_AUTH", raising=False)
    monkeypatch.delenv("MCP_OAUTH_BASE_URL", raising=False)
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    assert resolve_http_auth_mode() == "none"


def test_resolve_http_auth_mode_oauth_from_base_url(monkeypatch):
    monkeypatch.delenv("MCP_HTTP_AUTH", raising=False)
    monkeypatch.setenv("MCP_OAUTH_BASE_URL", "https://provena-mcp.example.com")
    assert resolve_http_auth_mode() == "oauth"


def test_resolve_http_auth_mode_explicit_api_key(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_AUTH", "api_key")
    monkeypatch.setenv("MCP_OAUTH_BASE_URL", "https://provena-mcp.example.com")
    assert resolve_http_auth_mode() == "api_key"


def test_build_oauth_provider_requires_base_url(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_AUTH", "oauth")
    monkeypatch.delenv("MCP_OAUTH_BASE_URL", raising=False)
    with pytest.raises(ValueError, match="MCP_OAUTH_BASE_URL"):
        build_oauth_provider()


def test_build_oauth_provider_returns_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("MCP_HTTP_AUTH", "oauth")
    monkeypatch.setenv("MCP_OAUTH_BASE_URL", "https://provena-mcp.example.com")
    monkeypatch.setenv("MCP_OAUTH_STATE_DIR", str(tmp_path / "oauth-state"))

    provider = build_oauth_provider()
    assert provider is not None
    assert provider.allowed_redirect_domains == DEFAULT_REDIRECT_DOMAINS


def test_build_oauth_provider_none_when_disabled(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_AUTH", "none")
    assert build_oauth_provider() is None
