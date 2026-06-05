import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from server.mcp_http_auth import (
    ApiKeyAuthMiddleware,
    extract_api_key_from_headers,
    resolve_mcp_api_key,
)


async def _ok(_request):
    return PlainTextResponse("ok")


def _app(api_key: str | None = None) -> Starlette:
    routes = [
        Route("/health", _ok, methods=["GET"]),
        Route("/mcp", _ok, methods=["GET", "POST"]),
    ]
    if api_key:
        return Starlette(
            routes=routes,
            middleware=[Middleware(ApiKeyAuthMiddleware, api_key=api_key)],
        )
    return Starlette(routes=routes)


def test_extract_api_key_from_x_api_key_header():
    assert extract_api_key_from_headers({"x-api-key": "secret"}) == "secret"


def test_extract_api_key_from_bearer_header():
    assert (
        extract_api_key_from_headers({"authorization": "Bearer my-token"})
        == "my-token"
    )


def test_extract_api_key_missing():
    assert extract_api_key_from_headers({}) is None


def test_resolve_mcp_api_key_from_env(monkeypatch):
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    assert resolve_mcp_api_key() is None
    monkeypatch.setenv("MCP_API_KEY", "  test-key  ")
    assert resolve_mcp_api_key() == "test-key"


def test_health_is_public_without_api_key():
    client = TestClient(_app())
    assert client.get("/health").status_code == 200


def test_health_is_public_with_api_key_enabled():
    client = TestClient(_app(api_key="secret"))
    assert client.get("/health").status_code == 200


def test_mcp_requires_api_key_when_enabled():
    client = TestClient(_app(api_key="secret"))
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"X-API-Key": "secret"}).status_code == 200
    assert (
        client.post("/mcp", headers={"Authorization": "Bearer secret"}).status_code
        == 200
    )


def test_wrong_api_key_rejected():
    client = TestClient(_app(api_key="secret"))
    assert client.post("/mcp", headers={"X-API-Key": "wrong"}).status_code == 401
