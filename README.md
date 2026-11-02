# mcp

Self-hosted remote [MCP](https://modelcontextprotocol.io) servers that give Claude (claude.ai,
Claude Desktop, Claude Code) or any MCP client access to things on your own server.
One folder per server, one Docker image per server.

| Server | Image | What it does |
|---|---|---|
| [mcpshared](mcpshared/) | `ghcr.io/therepos/mcpshared` | One folder on your server: browse, search, read and write files; read, build and edit xlsx, docx, pptx and pdf; OCR; office to PDF; password-protected 7z transfer archives (split sets); signed download / upload links |

## Quick start (mcpshared)

1. Copy [`mcpshared/compose.example.yml`](mcpshared/compose.example.yml), set the folder to expose
   and a token (`openssl rand -hex 32`), then `docker compose up -d`.
2. Publish it over HTTPS, e.g. a Cloudflare Tunnel public hostname pointing at
   `http://<docker-host-ip>:8765`.
3. Add it to Claude: Settings → Connectors → Add custom connector, URL
   `https://<hostname>/<TOKEN>/mcp`, OAuth fields empty.
   Claude Code: `claude mcp add --transport http mcpshared https://<hostname>/<TOKEN>/mcp`

Updates: the image is rebuilt on every change to `main`; Watchtower (label in the example)
or `docker compose pull && docker compose up -d` picks it up.

## Contract (common.py)

Every server exposes the same endpoints:

| Endpoint | Auth |
|---|---|
| `GET /healthz` | none |
| `POST /<TOKEN>/mcp` | token in the path (what claude.ai uses) |
| `POST /mcp` | `Authorization: Bearer <TOKEN>` |
| anything else | plain 404 |

A server may open extra prefixes with `serve(..., open_prefixes=(...))`; routes there
authenticate themselves. mcpshared opens `/files/` for signed, expiring links.

## Security

- The token is the only credential: anyone with the URL has the server's access. Use 32+
  random characters, keep the share read-only (`MCP_READ_ONLY=1`) unless Claude must write,
  and expose only the folder you mean to share.
- A wrong or missing token returns 404, so nothing is discoverable by scanning. Optionally add a
  Cloudflare WAF rule allowing only paths starting with `/<TOKEN>/` or `/files/`.
- Cloudflare Access cannot sit in front of it: claude.ai cannot log in through it.
- Every path is jailed to the shared folder; symlinks and `..` that leave it are rejected.

## Adding a server

The id is one lowercase word starting with `mcp` (e.g. `mcpjellyfin`) and is used for the
folder, the image, the container and the connector name.

1. `<id>/server.py` that imports `env` and `serve` from `common`:
   ```python
   import os, sys
   from mcp.server.mcpserver import MCPServer
   _HERE = os.path.dirname(os.path.abspath(__file__))
   sys.path[:0] = [_HERE, os.path.dirname(_HERE)]
   from common import env, serve

   mcp = MCPServer("<id>", instructions="what this server is for")

   @mcp.tool()
   def hello(name: str) -> str:
       """Say hello."""
       return f"hello {name}"

   if __name__ == "__main__":
       serve(mcp)
   ```
2. `<id>/requirements.txt`, `<id>/Dockerfile` (copy mcpshared's), `<id>/compose.example.yml`,
   `<id>/README.md`.
3. Add `<id>` to the matrix in `.github/workflows/build.yml` and a row to the table above.

## License

MIT
