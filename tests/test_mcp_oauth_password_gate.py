from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

from server.mcp_oauth_password_gate import (
    COOKIE_NAME,
    GATE_PATH,
    _cookie_is_valid,
    _make_cookie_value,
    oauth_gate_endpoint,
    resolve_oauth_password,
)


def test_resolve_oauth_password_empty(monkeypatch):
    monkeypatch.delenv("MCP_OAUTH_PASSWORD", raising=False)
    assert resolve_oauth_password() is None


def test_resolve_oauth_password_set(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_PASSWORD", "secret")
    assert resolve_oauth_password() == "secret"


def test_cookie_round_trip(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_PASSWORD", "secret")
    value = _make_cookie_value("secret")
    assert _cookie_is_valid("secret", value)


def test_cookie_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_PASSWORD", "secret")
    value = _make_cookie_value("secret")
    assert not _cookie_is_valid("other", value)


def _gate_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("MCP_OAUTH_PASSWORD", "secret")
    app = Starlette(
        routes=[Route(GATE_PATH, oauth_gate_endpoint, methods=["GET", "POST"])],
    )
    return TestClient(app)


def test_gate_post_sets_cookie(monkeypatch):
    client = _gate_client(monkeypatch)
    response = client.post(
        GATE_PATH,
        data={"password": "secret", "next": "/authorize?client_id=test"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/authorize?client_id=test"
    assert COOKIE_NAME in response.headers.get("set-cookie", "")


def test_gate_post_rejects_bad_password(monkeypatch):
    client = _gate_client(monkeypatch)
    response = client.post(
        GATE_PATH,
        data={"password": "wrong", "next": "/authorize"},
    )
    assert response.status_code == 200
    assert "Incorrect password" in response.text
