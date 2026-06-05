"""Browser password gate before OAuth /authorize when MCP_OAUTH_PASSWORD is set."""

from __future__ import annotations

import hashlib
import hmac
import html
import os
import secrets
import time
from typing import Any, Callable, Awaitable
from urllib.parse import quote, urlencode

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

COOKIE_NAME = "provena_mcp_oauth_gate"
COOKIE_MAX_AGE_SECONDS = 24 * 60 * 60
GATE_PATH = "/oauth/gate"

PUBLIC_PREFIXES = (
    "/health",
    "/.well-known/",
    "/register",
    "/token",
    GATE_PATH,
)


def resolve_oauth_password() -> str | None:
    value = os.environ.get("MCP_OAUTH_PASSWORD", "").strip()
    return value or None


def _cookie_secret(password: str) -> bytes:
    explicit = os.environ.get("MCP_OAUTH_COOKIE_SECRET", "").strip()
    material = explicit or password
    return hashlib.sha256(material.encode("utf-8")).digest()


def _make_cookie_value(password: str) -> str:
    issued_at = str(int(time.time()))
    digest = hmac.new(
        _cookie_secret(password),
        issued_at.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{issued_at}.{digest}"


def _cookie_is_valid(password: str, raw_cookie: str | None) -> bool:
    if not raw_cookie:
        return False
    try:
        issued_at, digest = raw_cookie.split(".", 1)
        issued_ts = int(issued_at)
    except ValueError:
        return False
    if time.time() - issued_ts > COOKIE_MAX_AGE_SECONDS:
        return False
    expected = hmac.new(
        _cookie_secret(password),
        issued_at.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, expected)


def _is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _gate_url(request: Request) -> str:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return f"{GATE_PATH}?{urlencode({'next': next_path})}"


def _login_page(*, error: str | None = None, next_url: str = "/") -> HTMLResponse:
    error_html = (
        f'<p class="error">{html.escape(error)}</p>' if error else ""
    )
    safe_next = html.escape(next_url)
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Provena MCP</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #f6f7f9; margin: 0; }}
    .card {{
      max-width: 420px; margin: 10vh auto; background: #fff; border-radius: 12px;
      padding: 28px; box-shadow: 0 8px 30px rgba(0,0,0,.08);
    }}
    h1 {{ font-size: 1.25rem; margin: 0 0 8px; }}
    p {{ color: #4b5563; margin: 0 0 18px; }}
    label {{ display: block; font-weight: 600; margin-bottom: 8px; }}
    input[type=password] {{
      width: 100%; box-sizing: border-box; padding: 10px 12px;
      border: 1px solid #d1d5db; border-radius: 8px; font-size: 1rem;
    }}
    button {{
      margin-top: 16px; width: 100%; padding: 10px 12px; border: 0;
      border-radius: 8px; background: #111827; color: #fff; font-size: 1rem;
      cursor: pointer;
    }}
    .error {{ color: #b91c1c; margin-bottom: 12px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Provena MCP</h1>
    <p>Enter the connector password to continue OAuth authorization.</p>
    {error_html}
    <form method="post" action="{GATE_PATH}">
      <input type="hidden" name="next" value="{safe_next}" />
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />
      <button type="submit">Continue</button>
    </form>
  </div>
</body>
</html>"""
    return HTMLResponse(body)


async def oauth_gate_endpoint(request: Request) -> Response:
    password = resolve_oauth_password()
    if not password:
        return HTMLResponse("OAuth password gate is not configured.", status_code=404)

    if request.method == "GET":
        next_url = request.query_params.get("next") or "/"
        return _login_page(next_url=next_url)

    form = await request.form()
    submitted = str(form.get("password") or "")
    next_url = str(form.get("next") or "/")
    if not hmac.compare_digest(submitted, password):
        return _login_page(error="Incorrect password.", next_url=next_url)

    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        COOKIE_NAME,
        _make_cookie_value(password),
        max_age=COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return response


class OAuthPasswordGateMiddleware:
    """Redirect /authorize to a password form until the gate cookie is set."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        password: str,
    ) -> None:
        self.app = app
        self.password = password

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path != "/authorize":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        cookie_header = headers.get("cookie", "")
        cookie_value = None
        for part in cookie_header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE_NAME:
                cookie_value = value
                break

        if _cookie_is_valid(self.password, cookie_value):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        response = RedirectResponse(url=_gate_url(request), status_code=302)
        await response(scope, receive, send)


def register_oauth_password_gate(mcp: Any) -> list[Any] | None:
    """Register /oauth/gate and middleware when MCP_OAUTH_PASSWORD is configured."""
    password = resolve_oauth_password()
    if not password or not hasattr(mcp, "custom_route"):
        return None

    @mcp.custom_route(GATE_PATH, methods=["GET", "POST"], include_in_schema=False)
    async def oauth_gate_route(request: Request) -> Response:
        return await oauth_gate_endpoint(request)

    from starlette.middleware import Middleware

    return [Middleware(OAuthPasswordGateMiddleware, password=password)]
