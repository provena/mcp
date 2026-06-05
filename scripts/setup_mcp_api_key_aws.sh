#!/usr/bin/env bash
# Create or update the MCP API key in AWS Secrets Manager, wire CDK .env.<env>, and deploy.
#
# Note: deployed stacks use OAuth by default. API key auth is legacy / optional.
#
# Usage:
#   ./scripts/setup_mcp_api_key_aws.sh dev
#   ./scripts/setup_mcp_api_key_aws.sh prod "$(openssl rand -hex 32)"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/mcp_deploy_env.sh
source "$SCRIPT_DIR/lib/mcp_deploy_env.sh"

ENV_NAME="${1:-}"
shift || true

API_KEY="${1:-}"
if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <dev|prod> [api-key]" >&2
  exit 1
fi

mcp_deploy_env_activate "$ENV_NAME"
mcp_deploy_env_sync

SECRET_NAME="provena-mcp/api-key"
export AWS_PROFILE AWS_REGION

if [[ -z "$API_KEY" && -f "$ROOT/.env" ]]; then
  API_KEY="$(grep -E '^MCP_API_KEY=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
fi
if [[ -z "$API_KEY" ]]; then
  echo "Error: set MCP_API_KEY in $ROOT/.env or pass the key as the second argument." >&2
  exit 1
fi

echo "Checking AWS credentials (profile: $AWS_PROFILE)..."
aws sts get-caller-identity >/dev/null

if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  echo "Updating existing secret: $SECRET_NAME"
  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$API_KEY" >/dev/null
else
  echo "Creating secret: $SECRET_NAME"
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "API key for Provena MCP HTTP endpoint ($DEPLOY_ENV)" \
    --secret-string "$API_KEY" >/dev/null
fi

SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text)"
echo "Secret ARN: $SECRET_ARN"

if grep -q '^MCP_API_KEY_SECRET_ARN=' "$CDK_ENV_SRC" 2>/dev/null; then
  sed -i "s|^MCP_API_KEY_SECRET_ARN=.*|MCP_API_KEY_SECRET_ARN=\"$SECRET_ARN\"|" "$CDK_ENV_SRC"
else
  printf '\nMCP_API_KEY_SECRET_ARN="%s"\n' "$SECRET_ARN" >>"$CDK_ENV_SRC"
fi
cp "$CDK_ENV_SRC" "$CDK_ENV_ACTIVE"
echo "Updated $CDK_ENV_SRC"

"$SCRIPT_DIR/deploy_mcp_stack.sh" "$ENV_NAME" deploy

echo "Done ($DEPLOY_ENV)."
