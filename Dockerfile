# Provena MCP server over HTTP (MCP Streamable HTTP). Repository root is /app.
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

# provenaclient pins httpx<0.28; Streamable HTTP needs fastmcp>=2.12 which requires httpx>=0.28.1.
# Install a compatible stack, then this package without re-resolving those pins.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "fastmcp>=2.12.0" "httpx>=0.28.1,<1" \
    && pip install --no-cache-dir boto3==1.27.1 "cloudpathlib[s3]==0.15.1" \
        "provena-interfaces-v2>=2.10.5" "pydantic>=2,<3" "python-jose<3.3.0" "requests>=2.26.0,<3" \
    && pip install --no-cache-dir "provenaclient==0.29.1" --no-deps \
    && pip install --no-cache-dir "typing-extensions>=4.5.0" "keyring>=24.0.0" "openai>=1.102.0" "python-dotenv>=1.0.0" \
    && pip install --no-cache-dir . --no-deps

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

# Run MCP server (Streamable HTTP); configure auth via env or mounted provena_tokens.json
CMD ["python", "server/provena_mcp_server.py", "--http"]
