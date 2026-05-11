"""Tests for ``ProvenaAuthManager`` offline vs device behaviour (mocked)."""

import types

import pytest

import server.provena_mcp_server as srv


@pytest.fixture
def offline_cfg():
    return {
        "domain": "auth.example",
        "realm": "realm1",
        "token": "offline-refresh-value",
        "instance": "auth.example",
        "datastore_api": None,
        "registry_api": None,
        "prov_api": None,
        "search_api": None,
        "search_service": None,
        "handle_service": None,
        "jobs_service": None,
    }


def test_offline_path_builds_client(monkeypatch, offline_cfg):
    class FakeOffline:
        def __init__(self, **kwargs):
            self.tokens = types.SimpleNamespace(access_token="header.payload.sig")
            self.file_name = "_nonexistent_token_file_"

    monkeypatch.setattr(srv.pr, "get_provena_config", lambda: offline_cfg)
    monkeypatch.setattr(srv, "OfflineFlow", FakeOffline)
    monkeypatch.setattr(
        srv,
        "ProvenaClient",
        lambda config, auth: types.SimpleNamespace(label="client-ok"),
    )

    mgr = srv.ProvenaAuthManager()
    client = mgr.get_client()
    assert client is not None
    assert client.label == "client-ok"
    assert mgr.auth_mode() == "offline"


def test_offline_invalid_returns_none(monkeypatch, offline_cfg):
    def boom(**kwargs):
        raise RuntimeError("bad token")

    monkeypatch.setattr(srv.pr, "get_provena_config", lambda: offline_cfg)
    monkeypatch.setattr(srv, "OfflineFlow", boom)

    mgr = srv.ProvenaAuthManager()
    assert mgr.get_client() is None
    assert mgr.auth_mode() == "offline_invalid"
