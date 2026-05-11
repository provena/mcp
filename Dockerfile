# Provena MCP server over HTTP (SSE). Repository root is /app.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install package (needs pyproject + README for metadata)
COPY pyproject.toml README.md ./
COPY server/ ./server/
COPY scripts/ ./scripts/
COPY provena_instances.json ./
COPY provena_tokens.json ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Option A: committed example instances (override at runtime if needed)
ENV PROVENA_CONFIG_FILE=/app/provena_instances.json
# Required when the instances file defines more than one instance
ENV PROVENA_INSTANCE=dev.rrap-is.com

# Do not load a host .env inside the container (explicit -e / --env-file only)
ENV PROVENA_MCP_NO_DOTENV=1

ENV MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=5000

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Run MCP server (SSE transport); configure auth via env or mounted provena_tokens.json
CMD ["python", "server/provena_mcp_server.py", "--http"]
