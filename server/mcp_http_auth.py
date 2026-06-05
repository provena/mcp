"""Optional API-key gate for MCP HTTP / Streamable HTTP transports.

When ``MCP_API_KEY`` is set, remote clients must send the key via:
- ``Authorization: Bearer <key>``, or
- ``X-API-Key: <key>``

The ``/health`` path stays public so load balancers can probe without a key.
"""

from __future__ import annotations

import os
import secrets
from typing import Any, Callable, Awaitable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

PUBLIC_PATHS = frozenset({"/health"})


def resolve_mcp_api_key() -> str | None:
    """Return the configured MCP API key, or None when HTTP auth is disabled."""
    value = os.environ.get("MCP_API_KEY", "").strip()
    return value or None


def extract_api_key_from_headers(headers: dict[str, str]) -> str | None:
    """Parse an API key from Bearer or X-API-Key headers."""
    x_api_key = headers.get("x-api-key", "").strip()
    if x_api_key:
        return x_api_key

    authorization = headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        return token or None
    return None


def _headers_from_scope(scope: dict[str, Any]) -> dict[str, str]:
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in scope.get("headers", [])
    }


class ApiKeyAuthMiddleware:
    """ASGI middleware that enforces a shared API key on HTTP requests."""

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        api_key: str,
        public_paths: frozenset[str] = PUBLIC_PATHS,
    ) -> None:
        self.app = app
        self.api_key = api_key
        self.public_paths = public_paths

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.public_paths:
            await self.app(scope, receive, send)
            return

        provided = extract_api_key_from_headers(_headers_from_scope(scope))
        if not provided or not secrets.compare_digest(provided, self.api_key):
            response = JSONResponse({"detail": "Unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def build_http_auth_middleware() -> list[Any] | None:
    """Build Starlette middleware list when ``MCP_API_KEY`` is configured."""
    api_key = resolve_mcp_api_key()
    if not api_key:
        return None

    from starlette.middleware import Middleware

    return [Middleware(ApiKeyAuthMiddleware, api_key=api_key)]


def register_health_route(mcp: Any) -> None:
    """Register a public health endpoint for load balancer probes."""
    if not hasattr(mcp, "custom_route"):
        return

    @mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health_check(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})
