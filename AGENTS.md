# Agent instructions

Self-hosted remote MCP servers, one folder and one Docker image per server
(`ghcr.io/therepos/<id>`, built by `.github/workflows/build.yml` on every push to `main`).
Deployments use Watchtower, so `main` must always build and run.
The real compose files live in the private repo `therepos/docker` as `<id>-compose.yml`;
`<id>/compose.example.yml` here is the public, generic version.

## Layout

- `common.py`  shared plumbing: token gate, `/healthz`, `serve()`. Copied into every image.
- `<id>/server.py` + tool modules, `<id>/requirements.txt`, `<id>/Dockerfile` (context = repo root).
- `mcpshared/zipper.py` is a copy of `therepos/skills` `zipper/scripts/zipper.py`. Edit it there,
  then re-copy; CI warns when the copies differ.

## Rules

- Server id: one lowercase word starting with `mcp`, used for folder, image, container and connector.
- All servers keep the endpoint contract in `common.py`: `/healthz`, `/<TOKEN>/mcp`, Bearer on
  `/mcp`, 404 otherwise. Do not add OAuth or change this without discussion.
- Python deps go in `<id>/requirements.txt`; optional imports stay lazy so the server still boots
  and the tool says what is missing. Host programs go in the Dockerfile.
- Every path a tool takes is relative to the share root and jailed there.
- Configuration only through environment variables; nothing personal in code or docs
  (no tokens, domains, LAN IPs, serial numbers or MAC addresses; use `<host-ip>`).
- Do not put model names in commits, comments or docs.

## Before pushing

- `python3 -m py_compile common.py <id>/*.py`
- Build the image (`docker build -f <id>/Dockerfile -t <id>:test .`), run it against a temp folder
  and exercise the tools with an MCP client. Path-escape attempts must be rejected.
