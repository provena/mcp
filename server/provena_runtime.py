"""Provena instance and token resolution (ported from RRAP cf-airflow MCP).

Resolves domain, realm, API endpoints, and offline tokens from ``provena_instances.json``,
``provena_tokens.json``, ``PROVENA_INSTANCE``, and related environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from provenaclient.utils.config import APIOverrides

_PROVENACLIENT_PATCHED = False


def apply_provenaclient_patches() -> None:
    """Work around provenaclient refresh requests that send an empty ``scope`` param.

    Keycloak returns ``400 invalid_scope`` when ``scope`` is present but empty; omit it instead.
    """
    global _PROVENACLIENT_PATCHED
    if _PROVENACLIENT_PATCHED:
        return

    from provenaclient.auth import helpers as auth_helpers

    _original = auth_helpers.keycloak_refresh_token_request

    def keycloak_refresh_token_request(
        token_endpoint: str,
        client_id: str,
        scopes: list,
        refresh_token: str,
        logger,
    ) -> dict[str, Any]:
        filtered = [s for s in (scopes or []) if s]
        if filtered:
            return _original(token_endpoint, client_id, filtered, refresh_token, logger)

        import requests

        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
        logger.info("Attempting to refresh token.")
        response = requests.post(token_endpoint, data=data)
        if response.status_code != 200:
            err_msg = (
                "The token used for refresh is invalid or has potentially expired. "
                f"Something went wrong during token refresh. Status code: {response.status_code}."
            )
            logger.error(err_msg)
            raise Exception(err_msg)
        return response.json()

    auth_helpers.keycloak_refresh_token_request = keycloak_refresh_token_request

    try:
        from provenaclient.auth import implementations as auth_impl

        auth_impl.keycloak_refresh_token_request = keycloak_refresh_token_request
    except ImportError:
        pass

    _PROVENACLIENT_PATCHED = True


def _project_root() -> Path:
    """Repository root (parent of ``server/``)."""
    return Path(__file__).resolve().parent.parent


def _resolve_existing_file_path(path_str: str) -> Path | None:
    """Resolve a config path from env: absolute, then cwd-relative, then repo-root-relative."""
    raw = Path(path_str.strip())
    if not raw.parts:
        return None
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append((Path.cwd() / raw).resolve())
        candidates.append((_project_root() / raw).resolve())
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def _resolve_writeable_path(path_str: str) -> Path:
    """Path for writing token files; relative paths are under the repository root."""
    raw = Path(path_str.strip())
    if raw.is_absolute():
        return raw
    return (_project_root() / raw).resolve()


def _get_config_file_path() -> Path | None:
    """Path to ``provena_instances.json``, or ``None`` if not found."""
    path = os.environ.get("PROVENA_CONFIG_FILE", "").strip()
    if path:
        found = _resolve_existing_file_path(path)
        return found
    default = _project_root() / "provena_instances.json"
    return default if default.is_file() else None


def _get_tokens_file_path() -> Path | None:
    """Path to ``provena_tokens.json``, or ``None`` if not found."""
    path = os.environ.get("PROVENA_TOKENS_FILE", "").strip()
    if path:
        found = _resolve_existing_file_path(path)
        return found
    default = _project_root() / "provena_tokens.json"
    return default if default.is_file() else None


def _load_tokens() -> dict[str, str] | None:
    """Load tokens from ``provena_tokens.json``. Returns ``None`` if file missing/invalid."""
    path = _get_tokens_file_path()
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        tokens = data.get("tokens")
        if isinstance(tokens, dict):
            return {k: str(v).strip() for k, v in tokens.items() if v}
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_provena_token(instance: str, token: str) -> Path:
    """Append or update token for instance in ``provena_tokens.json``. Creates file if missing."""
    path = os.environ.get("PROVENA_TOKENS_FILE", "").strip()
    file_path = _resolve_writeable_path(path) if path else _project_root() / "provena_tokens.json"
    data: dict[str, Any] = {}
    if file_path.is_file():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    if "tokens" not in data or not isinstance(data["tokens"], dict):
        data["tokens"] = {}
    data["tokens"][instance] = token.strip()
    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path


def _resolve_token(instance: str | None) -> str:
    """Resolve offline token from env and ``provena_tokens.json``."""
    env_only = os.environ.get("PROVENA_OFFLINE_TOKEN", "").strip()
    if env_only:
        return env_only

    tokens = _load_tokens()
    if instance and tokens:
        for key, token in tokens.items():
            if key.lower() == instance.lower() and token:
                return token
    if tokens and not instance:
        domain = _resolve_provena_env("KEYCLOAK_DOMAIN", None)
        if domain:
            for key, token in tokens.items():
                if key.lower() == domain.lower() and token:
                    return token
        default = tokens.get("default") or tokens.get("")
        if default:
            return str(default).strip()
    return ""


def _load_instances_config() -> dict[str, Any] | None:
    """Load instances from ``provena_instances.json``."""
    path = _get_config_file_path()
    if not path:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        instances = data.get("instances")
        if isinstance(instances, dict):
            return instances
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _instance_to_env_suffix(instance: str) -> str:
    """Convert instance key to env var suffix (``dev.rrap-is.com`` -> ``DEV_RRAP_IS_COM``)."""
    return instance.replace(".", "_").replace("-", "_").upper()


def _resolve_provena_env(key_suffix: str, instance: str | None) -> str:
    """Resolve ``PROVENA_<SUFFIX>_<KEY>`` or ``PROVENA_<KEY>``."""
    if instance:
        suffix = _instance_to_env_suffix(instance)
        val = os.environ.get(f"PROVENA_{suffix}_{key_suffix}", "").strip()
        if val:
            return val
    return os.environ.get(f"PROVENA_{key_suffix}", "").strip()


def _inst_value(inst: dict[str, Any], *keys: str) -> str:
    """First non-empty value from instance dict."""
    for k in keys:
        v = inst.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def default_api_endpoint_map() -> dict[str, str]:
    """Default API base URLs from environment (legacy unprefixed names)."""
    return {
        "datastore_api": os.getenv("DATASTORE_API", "https://data-api.dev.rrap-is.com"),
        "registry_api": os.getenv("REGISTRY_API", "https://registry-api.dev.rrap-is.com"),
        "prov_api": os.getenv("PROV_API", "https://prov-api.dev.rrap-is.com"),
        "search_api": os.getenv("SEARCH_API", "https://search.dev.rrap-is.com"),
        "search_service": os.getenv("SEARCH_SERVICE", "https://search.dev.rrap-is.com"),
        "handle_service": os.getenv("HANDLE_SERVICE", "https://handle.dev.rrap-is.com"),
        "jobs_service": os.getenv("JOBS_SERVICE", "https://job-api.dev.rrap-is.com"),
    }


def build_api_overrides_for_config(cfg: dict[str, Any]) -> APIOverrides:
    """Build ``APIOverrides`` from resolved config dict, falling back to env defaults."""
    defaults = default_api_endpoint_map()

    def pick(key: str) -> str | None:
        v = cfg.get(key)
        if v and str(v).strip():
            return str(v).strip()
        d = defaults.get(key)
        return d if d else None

    keycloak = cfg.get("keycloak_endpoint")
    if not keycloak or not str(keycloak).strip():
        keycloak = _resolve_provena_env("KEYCLOAK_ENDPOINT", cfg.get("instance"))

    return APIOverrides(
        datastore_api_endpoint_override=pick("datastore_api"),
        registry_api_endpoint_override=pick("registry_api"),
        prov_api_endpoint_override=pick("prov_api"),
        search_api_endpoint_override=pick("search_api"),
        search_service_endpoint_override=pick("search_service"),
        handle_service_api_endpoint_override=pick("handle_service"),
        jobs_service_api_endpoint_override=pick("jobs_service"),
        keycloak_endpoint_override=keycloak.strip() if keycloak else None,
    )


def get_provena_config() -> dict[str, Any]:
    """Resolved Provena config: domain, realm, token, instance, API URLs.

    When ``provena_instances.json`` exists, domain/realm come from that file for the
    selected instance. Tokens come from ``provena_tokens.json`` or ``PROVENA_OFFLINE_TOKEN``.
    ``PROVENA_INSTANCE`` selects the instance when multiple are defined.

    Falls back to ``PROVENA_KEYCLOAK_DOMAIN`` / ``PROVENA_KEYCLOAK_REALM`` (RRAP style),
    then ``PROVENA_DOMAIN`` / ``PROVENA_REALM``, then defaults ``dev.rrap-is.com`` / ``rrap``.
    """

    def _api_from_inst(inst: dict[str, Any]) -> dict[str, str | None]:
        def _v(k: str) -> str | None:
            v = inst.get(k)
            return str(v).strip() or None if v else None

        return {
            "datastore_api": _v("datastore_api"),
            "registry_api": _v("registry_api"),
            "prov_api": _v("prov_api"),
            "search_api": _v("search_api"),
            "search_service": _v("search_service"),
            "handle_service": _v("handle_service"),
            "jobs_service": _v("jobs_service"),
            "keycloak_endpoint": _v("keycloak_endpoint"),
        }

    instance = os.environ.get("PROVENA_INSTANCE", "").strip()
    instances = _load_instances_config()

    if instances:
        inst_key: str | None = None
        if instance:
            inst_key = next((k for k in instances if k.lower() == instance.lower()), None)
        if inst_key is None and len(instances) == 1:
            inst_key = next(iter(instances))
        if inst_key is not None:
            inst = instances[inst_key]
            if isinstance(inst, dict):
                domain = _inst_value(inst, "domain", "keycloak_domain")
                realm = _inst_value(inst, "realm", "keycloak_realm")
                apis = _api_from_inst(inst)
                return {
                    "domain": domain,
                    "realm": realm,
                    "token": _resolve_token(inst_key),
                    "instance": inst_key,
                    **apis,
                }

    prefix = f"PROVENA_{_instance_to_env_suffix(instance)}_" if instance else "PROVENA_"

    def _api(key: str) -> str | None:
        v = os.environ.get(f"{prefix}{key}", "").strip()
        return v or None

    domain = (
        _resolve_provena_env("KEYCLOAK_DOMAIN", instance)
        or os.getenv("PROVENA_DOMAIN", "").strip()
        or "dev.rrap-is.com"
    )
    realm = (
        _resolve_provena_env("KEYCLOAK_REALM", instance)
        or os.getenv("PROVENA_REALM", "").strip()
        or "rrap"
    )
    token = _resolve_token(instance)
    return {
        "domain": domain,
        "realm": realm,
        "token": token,
        "instance": instance or None,
        "datastore_api": _api("DATASTORE_API"),
        "registry_api": _api("REGISTRY_API"),
        "prov_api": _api("PROV_API"),
        "search_api": _api("SEARCH_API"),
        "search_service": _api("SEARCH_SERVICE"),
        "handle_service": _api("HANDLE_SERVICE"),
        "jobs_service": _api("JOBS_SERVICE"),
        "keycloak_endpoint": _resolve_provena_env("KEYCLOAK_ENDPOINT", instance) or None,
    }


def list_provena_instances() -> dict[str, Any]:
    """Defined instances from config file, with token presence (never token values)."""
    instances = _load_instances_config()
    tokens = _load_tokens()
    config_path = _get_config_file_path()
    tokens_path = _get_tokens_file_path()

    if not instances:
        return {
            "instances": {},
            "config_file": str(config_path) if config_path else None,
            "tokens_file": str(tokens_path) if tokens_path else None,
        }

    summary: dict[str, Any] = {}
    for name, cfg in instances.items():
        if not isinstance(cfg, dict):
            continue
        domain = cfg.get("domain") or cfg.get("keycloak_domain")
        realm = cfg.get("realm") or cfg.get("keycloak_realm")
        has_token = bool(
            tokens
            and next(
                (t for k, t in (tokens or {}).items() if k.lower() == name.lower() and t),
                None,
            )
        )
        summary[name] = {
            "domain": domain,
            "realm": realm,
            "has_token": has_token,
        }

    return {
        "instances": summary,
        "config_file": str(config_path) if config_path else None,
        "tokens_file": str(tokens_path) if tokens_path else None,
    }


def offline_token_instructions(script_relative: str = "scripts/generate_provena_offline_token.py") -> dict[str, Any]:
    """Structured instructions for obtaining an offline token (for MCP tools)."""
    return {
        "when_to_use": "Use device login, or when running headless with an offline refresh token",
        "steps": [
            "Set PROVENA_CONFIG_FILE=provena_instances.example.json (Option A) or copy the example to provena_instances.json; set domain/realm and optional API URLs.",
            f"Run: python {script_relative} --instance <instance-key> --save",
            "Complete the login in the browser that opens.",
            "Token is written to provena_tokens.json (gitignored).",
            "Set PROVENA_INSTANCE to the instance key if you use multiple instances, then restart the MCP server.",
        ],
        "script_path": script_relative,
        "multi_instance": (
            "Use --instance <key> matching a key in your instances file (e.g. provena_instances.example.json) so the token is stored under that key."
        ),
        "env_alternative": "Set PROVENA_OFFLINE_TOKEN instead of a tokens file (avoid committing it).",
    }
