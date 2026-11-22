# Purpose: shared HTTP plumbing for every MCP server in apps/mcp
# =============================================================================
# Each server does:
#
#     from common import env, serve
#     mcp = MCPServer("my-server", instructions="...")
#     ... @mcp.tool() definitions ...
#     if __name__ == "__main__":
#         serve(mcp)
#
# serve() gives every server the same contract, which deployment and reverse-proxy setup rely on:
#
#   GET  /healthz                     unauthenticated liveness check
#   GET  /favicon.ico, /icon.png, /icon.svg
#                                     unauthenticated connector icon, served from the
#                                     server's static/ folder when present (else 404)
#   POST /<MCP_TOKEN>/mcp             Streamable HTTP endpoint (secret path)
#   POST /mcp  + Authorization: Bearer <MCP_TOKEN>
#   anything else                     plain 404 (no OAuth discovery, nothing to probe)
#
# A server may open extra path prefixes with serve(..., open_prefixes=("/files/",));
# routes under them must authenticate themselves (mcp-proxmox uses signed, expiring
# links there). Everything else stays 404.
#
# Environment read here:
#   MCP_TOKEN   secret, 16+ chars (required)
#   MCP_PORT    listen port (default 5001)
#   MCP_HOST    bind address (default 0.0.0.0)
# =============================================================================

from __future__ import annotations

import hmac
import os
import sys
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

# Public icon files: claude.ai shows the connector's favicon, so these must be reachable without the token.
ICON_FILES = {"/favicon.ico": "image/x-icon", "/icon.png": "image/png", "/icon.svg": "image/svg+xml"}


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    val = os.environ.get(name, "").strip() or (default or "")
    if required and not val:
        sys.exit(f"{name} is not set")
    return val


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


class TokenGate:
    """ASGI wrapper enforcing the URL/Bearer token contract described above."""

    def __init__(self, app, token: str, open_prefixes: tuple[str, ...] = ()):  # type: ignore[no-untyped-def]
        self.app = app
        self.token = token.encode()
        self.prefix = f"/{token}"
        self.open_prefixes = open_prefixes

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path: str = scope.get("path", "")
        if path == "/healthz" or path in ICON_FILES or path.startswith(self.open_prefixes):
            return await self.app(scope, receive, send)
        if path.startswith(self.prefix + "/") and hmac.compare_digest(path[1 : 1 + len(self.token)].encode(), self.token):
            scope = dict(scope)
            scope["path"] = path[len(self.prefix):]
            scope["raw_path"] = scope["path"].encode()
            return await self.app(scope, receive, send)
        auth = dict(scope.get("headers", [])).get(b"authorization", b"")
        if auth.startswith(b"Bearer ") and hmac.compare_digest(auth[7:].strip(), self.token):
            return await self.app(scope, receive, send)
        resp = PlainTextResponse("not found", status_code=404)
        await resp(scope, receive, send)


def build_app(mcp: MCPServer, *, token: str, host: str, extra_health: dict | None = None, open_prefixes: tuple[str, ...] = (), static_dir: str | None = None):  # type: ignore[no-untyped-def]
    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request):  # type: ignore[no-untyped-def]
        return JSONResponse({"ok": True, "name": mcp.name, "time": int(time.time()), **(extra_health or {})})

    for route, mime in ICON_FILES.items():
        f = Path(static_dir or "", route.lstrip("/"))
        if static_dir and f.is_file():
            def make(f: Path = f, mime: str = mime):  # type: ignore[no-untyped-def]
                async def icon(_request: Request):  # type: ignore[no-untyped-def]
                    return FileResponse(f, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})
                return icon
            mcp.custom_route(route, methods=["GET", "HEAD"], include_in_schema=False)(make())

    inner = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host=host,
        max_request_body_size=16 * 1024 * 1024,
        # Behind Cloudflare Tunnel the Host header is the public name; the token is the gate.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return TokenGate(inner, token, open_prefixes)


def icons(static_dir: str) -> list:  # type: ignore[type-arg]
    """serverInfo icons (MCP spec) as data URIs, so clients need no extra request or public URL."""
    import base64

    from mcp.types import Icon

    out = []
    for name, mime, sizes in (("icon.svg", "image/svg+xml", ["any"]), ("icon.png", "image/png", ["180x180"])):
        f = Path(static_dir, name)
        if f.is_file():
            out.append(Icon(src=f"data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}", mime_type=mime, sizes=sizes))
    return out


def serve(mcp: MCPServer, *, extra_health: dict | None = None, open_prefixes: tuple[str, ...] = (), static_dir: str | None = None) -> None:
    import uvicorn

    token = env("MCP_TOKEN", required=True)
    if len(token) < 16:
        sys.exit("MCP_TOKEN is too short (need 16+ chars)")
    host = env("MCP_HOST", "0.0.0.0")
    port = int(env("MCP_PORT", "5001"))
    app = build_app(mcp, token=token, host=host, extra_health=extra_health, open_prefixes=open_prefixes, static_dir=static_dir)
    print(f"[mcp] {mcp.name}: listening on {host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")
