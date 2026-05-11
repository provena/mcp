"""Tests for ``server.provena_runtime`` instance and token resolution."""

import json
from pathlib import Path

import pytest

from server import provena_runtime as pr


@pytest.fixture(autouse=True)
def clear_provena_env(monkeypatch):
    """Avoid leaking PROVENA_* from host into tests."""
    for key in list(__import__("os").environ):
        if key.startswith("PROVENA_") or key in ("DATASTORE_API", "REGISTRY_API", "PROV_API"):
            monkeypatch.delenv(key, raising=False)


def test_get_provena_config_defaults(monkeypatch):
    monkeypatch.delenv("PROVENA_DOMAIN", raising=False)
    monkeypatch.delenv("PROVENA_REALM", raising=False)
    cfg = pr.get_provena_config()
    assert cfg["domain"] == "dev.rrap-is.com"
    assert cfg["realm"] == "rrap"
    assert cfg["token"] == ""


def test_get_provena_config_legacy_env(monkeypatch):
    monkeypatch.setenv("PROVENA_DOMAIN", "custom.example")
    monkeypatch.setenv("PROVENA_REALM", "myrealm")
    cfg = pr.get_provena_config()
    assert cfg["domain"] == "custom.example"
    assert cfg["realm"] == "myrealm"


def test_get_provena_config_instances_and_tokens(monkeypatch, tmp_path: Path):
    inst_path = tmp_path / "provena_instances.json"
    inst_path.write_text(
        json.dumps(
            {
                "instances": {
                    "one": {"domain": "a.example", "realm": "r1"},
                    "two": {"domain": "b.example", "realm": "r2"},
                }
            }
        ),
        encoding="utf-8",
    )
    tok_path = tmp_path / "provena_tokens.json"
    tok_path.write_text(json.dumps({"tokens": {"two": "offline-refresh"}}), encoding="utf-8")
    monkeypatch.setenv("PROVENA_CONFIG_FILE", str(inst_path))
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(tok_path))
    monkeypatch.setenv("PROVENA_INSTANCE", "two")
    cfg = pr.get_provena_config()
    assert cfg["instance"] == "two"
    assert cfg["domain"] == "b.example"
    assert cfg["realm"] == "r2"
    assert cfg["token"] == "offline-refresh"


def test_get_provena_config_single_instance_without_env(monkeypatch, tmp_path: Path):
    inst_path = tmp_path / "pi.json"
    inst_path.write_text(
        json.dumps({"instances": {"solo": {"domain": "solo.test", "realm": "sr"}}}),
        encoding="utf-8",
    )
    tok_path = tmp_path / "pt.json"
    tok_path.write_text(json.dumps({"tokens": {"solo": "t-solo"}}), encoding="utf-8")
    monkeypatch.setenv("PROVENA_CONFIG_FILE", str(inst_path))
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(tok_path))
    cfg = pr.get_provena_config()
    assert cfg["instance"] == "solo"
    assert cfg["token"] == "t-solo"


def test_provena_offline_token_env_overrides_file(monkeypatch, tmp_path: Path):
    inst_path = tmp_path / "pi.json"
    inst_path.write_text(
        json.dumps({"instances": {"solo": {"domain": "solo.test", "realm": "sr"}}}),
        encoding="utf-8",
    )
    tok_path = tmp_path / "pt.json"
    tok_path.write_text(json.dumps({"tokens": {"solo": "from-file"}}), encoding="utf-8")
    monkeypatch.setenv("PROVENA_CONFIG_FILE", str(inst_path))
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(tok_path))
    monkeypatch.setenv("PROVENA_OFFLINE_TOKEN", "from-env")
    cfg = pr.get_provena_config()
    assert cfg["token"] == "from-env"


def test_list_provena_instances(monkeypatch, tmp_path: Path):
    inst_path = tmp_path / "pi.json"
    inst_path.write_text(
        json.dumps({"instances": {"a": {"domain": "d1", "realm": "r"}}}),
        encoding="utf-8",
    )
    tok_path = tmp_path / "pt.json"
    tok_path.write_text(json.dumps({"tokens": {"a": "x"}}), encoding="utf-8")
    monkeypatch.setenv("PROVENA_CONFIG_FILE", str(inst_path))
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(tok_path))
    out = pr.list_provena_instances()
    assert out["instances"]["a"]["has_token"] is True
    assert out["instances"]["a"]["domain"] == "d1"
    assert str(inst_path) in (out["config_file"] or "")


def test_save_provena_token(tmp_path: Path, monkeypatch):
    target = tmp_path / "out.json"
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(target))
    path = pr.save_provena_token("myinst", "  tok  ")
    assert path == target
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["tokens"]["myinst"] == "tok"


def test_build_api_overrides_merges_instance_and_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("REGISTRY_API", "https://registry-env.example")
    inst_path = tmp_path / "pi.json"
    inst_path.write_text(
        json.dumps(
            {
                "instances": {
                    "solo": {
                        "domain": "solo.test",
                        "realm": "sr",
                        "prov_api": "https://prov-custom.example",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PROVENA_CONFIG_FILE", str(inst_path))
    monkeypatch.setenv("PROVENA_TOKENS_FILE", str(tmp_path / "missing.json"))
    cfg = pr.get_provena_config()
    ov = pr.build_api_overrides_for_config(cfg)
    assert ov.prov_api_endpoint_override == "https://prov-custom.example"
    assert ov.registry_api_endpoint_override == "https://registry-env.example"


def test_offline_token_instructions_shape():
    doc = pr.offline_token_instructions("scripts/generate_provena_offline_token.py")
    assert "steps" in doc
    assert "PROVENA_OFFLINE_TOKEN" in doc["env_alternative"]
