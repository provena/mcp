#!/usr/bin/env bash
# Create or update the OAuth connector password in AWS Secrets Manager, wire CDK .env.<env>, and deploy.
#
# Usage:
#   ./scripts/setup_mcp_oauth_password_aws.sh dev
#   ./scripts/setup_mcp_oauth_password_aws.sh prod "$(openssl rand -hex 16)"
#   ./scripts/setup_mcp_oauth_password_aws.sh dev --no-deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/mcp_deploy_env.sh
source "$SCRIPT_DIR/lib/mcp_deploy_env.sh"

ENV_NAME="${1:-}"
shift || true

DEPLOY_AFTER=true
PASSWORD=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-deploy) DEPLOY_AFTER=false; shift ;;
    *) PASSWORD="$1"; shift ;;
  esac
done

if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <dev|prod> [password] [--no-deploy]" >&2
  exit 1
fi

mcp_deploy_env_activate "$ENV_NAME"
mcp_deploy_env_sync

SECRET_NAME="provena-mcp/oauth-password"
export AWS_PROFILE AWS_REGION

if [[ -z "$PASSWORD" && -f "$ROOT/.env" ]]; then
  PASSWORD="$(grep -E '^MCP_OAUTH_PASSWORD=' "$ROOT/.env" | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true)"
fi
if [[ -z "$PASSWORD" ]]; then
  PASSWORD="$(openssl rand -hex 16)"
  echo "Generated OAuth password: $PASSWORD"
fi

echo "Checking AWS credentials (profile: $AWS_PROFILE)..."
aws sts get-caller-identity >/dev/null

if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  echo "Updating existing secret: $SECRET_NAME"
  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$PASSWORD" >/dev/null
else
  echo "Creating secret: $SECRET_NAME"
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Browser password gate for Provena MCP OAuth /authorize ($DEPLOY_ENV)" \
    --secret-string "$PASSWORD" >/dev/null
fi

SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text)"
echo "Secret ARN: $SECRET_ARN"

if grep -q '^MCP_OAUTH_PASSWORD_SECRET_ARN=' "$CDK_ENV_SRC" 2>/dev/null; then
  sed -i "s|^MCP_OAUTH_PASSWORD_SECRET_ARN=.*|MCP_OAUTH_PASSWORD_SECRET_ARN=\"$SECRET_ARN\"|" "$CDK_ENV_SRC"
else
  printf '\nMCP_OAUTH_PASSWORD_SECRET_ARN="%s"\n' "$SECRET_ARN" >>"$CDK_ENV_SRC"
fi
cp "$CDK_ENV_SRC" "$CDK_ENV_ACTIVE"
echo "Updated $CDK_ENV_SRC"

if [[ -f "$ROOT/.env" && "$DEPLOY_ENV" == "dev" ]]; then
  if grep -q '^MCP_OAUTH_PASSWORD=' "$ROOT/.env" 2>/dev/null; then
    sed -i "s|^MCP_OAUTH_PASSWORD=.*|MCP_OAUTH_PASSWORD=$PASSWORD|" "$ROOT/.env"
  else
    printf '\nMCP_OAUTH_PASSWORD=%s\n' "$PASSWORD" >>"$ROOT/.env"
  fi
fi

if [[ "$DEPLOY_AFTER" == true ]]; then
  "$SCRIPT_DIR/deploy_mcp_stack.sh" "$ENV_NAME" deploy
fi

echo "Done ($DEPLOY_ENV). When connecting Claude or Cursor, enter this password on /oauth/gate:"
echo "$PASSWORD"
