# mcpshared: one folder on your server, exposed to Claude / any MCP client.
# Build context is the repo root (common.py is shared by every server):
#   docker build -f mcpshared/Dockerfile -t mcpshared .
FROM python:3.12-slim-bookworm

# 7-Zip (transfer archives), tesseract (OCR), LibreOffice without GUI (office -> PDF), fonts for PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
        7zip \
        tesseract-ocr tesseract-ocr-eng \
        libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui \
        fonts-dejavu-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY mcpshared/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common.py mcpshared/*.py ./
COPY mcpshared/entrypoint.sh /usr/local/bin/entrypoint.sh

# /share = the folder to expose (mount it). /data = small writable state
# (saved zip password, LibreOffice profile). HOME points there so any user id works.
# Runs as PUID:PGID (default 1000:1000); the entrypoint fixes /data ownership first.
ENV MCP_ROOT=/share \
    MCP_PORT=5001 \
    MCP_HOST=0.0.0.0 \
    ZIPPER_CONFIG=/data/zipper.json \
    HOME=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PUID=1000 \
    PGID=1000
RUN mkdir -p /share /data && chmod 777 /data

EXPOSE 5001
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"MCP_PORT\"]}/healthz', timeout=4)"

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "server.py"]
