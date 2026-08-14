#!/usr/bin/env python3
"""Generate or export a Provena offline token.

Modes
-----
Device flow (default)
    Initiates an OAuth device flow to obtain a new offline refresh token.

    python scripts/generate_provena_offline_token.py --instance dev.rrap-is.com --save
    python scripts/generate_provena_offline_token.py --output token.txt

Export from provena_tokens.json  (--export)
    Reads the saved token for the given instance and prints a shell export
    statement.  Useful for loading a token into the environment without
    running the device flow again.

    eval "$(python scripts/generate_provena_offline_token.py --instance mds.gbrrestoration.org --export)"

    After eval, PROVENA_TOKEN is set in the current shell.  The AWS secret
    helper script (setup_mcp_offline_token_aws.sh) will pick it up
    automatically.

Environment variables
---------------------
PROVENA_TOKEN
    If set, skip the device flow and use this value as the token directly.
    Combined with --save or --output to persist it.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))


def _requests_verify() -> bool | str:
    """CA bundle for internal PKI; prefers REQUESTS_CA_BUNDLE then SSL_CERT_FILE."""
    for key in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE", "CURL_CA_BUNDLE"):
        path = os.environ.get(key, "").strip()
        if path:
            return path
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a Provena offline token via OAuth device flow."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write token to file instead of stdout.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not attempt to open the verification URL in a browser.",
    )
    parser.add_argument(
        "--instance",
        "-i",
        type=str,
        default=None,
        help="Provena instance key (matches a key in provena_instances.json, often the domain).",
    )
    parser.add_argument(
        "--save",
        "-s",
        action="store_true",
        help="Save token to provena_tokens.json (recommended for MCP).",
    )
    parser.add_argument(
        "--export",
        "-e",
        action="store_true",
        help=(
            "Print 'export PROVENA_TOKEN=<token>' for the instance from "
            "provena_tokens.json and exit.  No device flow is run.  "
            "Use with eval: eval \"$(... --export)\"."
        ),
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help=(
            "Force a new device flow even if PROVENA_TOKEN is set or a token "
            "already exists in provena_tokens.json.  Overwrites the saved token "
            "when combined with --save."
        ),
    )
    args = parser.parse_args()

    if args.instance:
        os.environ["PROVENA_INSTANCE"] = args.instance

    try:
        from dotenv import load_dotenv

        load_dotenv(_project_root / ".env")
    except ImportError:
        pass

    from server.provena_runtime import (
        build_api_overrides_for_config,
        get_provena_config,
        save_provena_token,
    )
    from provenaclient.utils.config import Config

    cfg = get_provena_config()
    domain = cfg["domain"]
    realm = cfg["realm"]
    instance = cfg["instance"]

    # --export without --force: read saved token from provena_tokens.json and print shell export
    if args.export and not args.force:
        import json as _json

        tokens_path = _project_root / "provena_tokens.json"
        if not tokens_path.exists():
            print(f"Error: {tokens_path} not found. Run with --save first.", file=sys.stderr)
            sys.exit(1)
        tokens_data = _json.loads(tokens_path.read_text())
        key = instance or domain or "default"
        token = tokens_data.get("tokens", {}).get(key)
        if not token:
            print(
                f"Error: No token found for instance '{key}' in {tokens_path}.",
                file=sys.stderr,
            )
            print(
                f"  Available instances: {list(tokens_data.get('tokens', {}).keys())}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"export PROVENA_TOKEN={token}")
        return

    # PROVENA_TOKEN env var: skip device flow, use token directly (unless --force)
    env_token = os.environ.get("PROVENA_TOKEN", "").strip()
    if env_token and not args.force:
        print("Using token from PROVENA_TOKEN environment variable.")
        token_str = env_token
        key = instance or domain or "default"
        if args.save:
            saved_path = save_provena_token(key, token_str)
            print(f"Token saved to {saved_path} for instance '{key}'")
            print("(provena_tokens.json is gitignored; do not commit it.)")
        elif args.output:
            args.output.write_text(token_str, encoding="utf-8")
            print(f"Token written to {args.output}")
        else:
            print(token_str)
        return

    if not domain or not realm:
        print(
            "Error: Add domain and realm to provena_instances.json, or set "
            "PROVENA_KEYCLOAK_DOMAIN and PROVENA_KEYCLOAK_REALM (or PROVENA_DOMAIN / PROVENA_REALM) in .env",
            file=sys.stderr,
        )
        print(
            '  Example provena_instances.json: {"instances": {"dev.rrap-is.com": '
            '{"domain": "dev.rrap-is.com", "realm": "rrap"}}}',
            file=sys.stderr,
        )
        sys.exit(1)

    api_overrides = build_api_overrides_for_config(cfg)
    config = Config(domain=domain, realm_name=realm, api_overrides=api_overrides)
    keycloak_endpoint = config.keycloak_endpoint
    device_endpoint = f"{keycloak_endpoint}/protocol/openid-connect/auth/device"
    token_endpoint = f"{keycloak_endpoint}/protocol/openid-connect/token"

    client_id = "automated-access"
    scopes = ["offline_access"]

    print("Initiating Provena device auth flow...")
    print(f"  Keycloak: {keycloak_endpoint}")
    print()

    verify = _requests_verify()
    resp = requests.post(
        device_endpoint,
        data={"client_id": client_id, "scope": " ".join(scopes)},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        verify=verify,
    )
    if resp.status_code != 200:
        print(f"Error: Device flow request failed ({resp.status_code})", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    device_code = data.get("device_code")
    interval = data.get("interval", 5)
    verification_url = data.get("verification_uri_complete", data.get("verification_uri"))
    user_code = data.get("user_code", "")

    if not device_code or not verification_url:
        print("Error: Invalid device flow response", file=sys.stderr)
        sys.exit(1)

    print("Open this URL in your browser and complete the login:")
    print()
    print(f"  {verification_url}")
    print()
    if user_code:
        print(f"  User code: {user_code}")
    print()

    if not args.no_browser:
        try:
            import webbrowser

            webbrowser.open(verification_url)
            print("  (Browser opened automatically)")
        except Exception:
            print("  (Could not open browser - please visit the URL above)")
    print()

    grant_type = "urn:ietf:params:oauth:grant-type:device_code"
    poll_data = {
        "grant_type": grant_type,
        "device_code": device_code,
        "client_id": client_id,
        "scope": " ".join(scopes),
    }

    print("Waiting for you to complete the login...")
    while True:
        time.sleep(interval)
        poll_resp = requests.post(
            token_endpoint,
            data=poll_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            verify=verify,
        )
        poll_json = poll_resp.json()

        if poll_json.get("error"):
            err = poll_json["error"]
            if err == "authorization_pending":
                print(".", end="", flush=True)
                continue
            if err == "expired_token":
                print("\nError: Device code expired. Run the script again.", file=sys.stderr)
                sys.exit(1)
            print(f"\nError: {err}", file=sys.stderr)
            sys.exit(1)

        refresh_token = poll_json.get("refresh_token")
        if not refresh_token:
            print(
                "\nError: No refresh token in response (offline_access may not be granted)",
                file=sys.stderr,
            )
            sys.exit(1)

        print("\n")
        print("Login complete. Offline token obtained.")
        print()

        token_str = refresh_token.strip()
        instance_key = instance or domain or "default"

        if args.save:
            saved_path = save_provena_token(instance_key, token_str)
            print(f"Token saved to {saved_path} for instance '{instance_key}'")
            print("(provena_tokens.json is gitignored; do not commit it.)")
            if args.export:
                print(f"export PROVENA_TOKEN={token_str}")
        elif args.export:
            # --export --force: print export statement (optionally also --save above)
            print(f"export PROVENA_TOKEN={token_str}")
        elif args.output:
            args.output.write_text(token_str, encoding="utf-8")
            print(f"Token written to {args.output}")
            print()
            print("Run with --save to add to provena_tokens.json:")
            print("  python scripts/generate_provena_offline_token.py --instance <key> --save")
        else:
            print("Run with --save to add token to provena_tokens.json:")
            print()
            print(token_str)
            print()
            print("(Do not share this token or commit it to version control.)")

        break


if __name__ == "__main__":
    main()
