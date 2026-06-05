#!/usr/bin/env bash
# Create or update the Provena offline token secret and wire cdk-infra/.env.<env>.
#
# Usage:
#   ./scripts/setup_mcp_offline_token_aws.sh dev
#   ./scripts/setup_mcp_offline_token_aws.sh prod "$(cat /path/to/token.txt)"
#   ./scripts/setup_mcp_offline_token_aws.sh dev --deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/mcp_deploy_env.sh
source "$SCRIPT_DIR/lib/mcp_deploy_env.sh"

ENV_NAME="${1:-}"
shift || true

DEPLOY_AFTER=false
TOKEN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy) DEPLOY_AFTER=true; shift ;;
    *) TOKEN="$1"; shift ;;
  esac
done

if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <dev|prod> [token] [--deploy]" >&2
  exit 1
fi

mcp_deploy_env_activate "$ENV_NAME"
mcp_deploy_env_sync

SECRET_NAME="provena-mcp/offline-token"
export AWS_PROFILE AWS_REGION

if [[ -z "$TOKEN" ]]; then
  echo "Error: pass the offline refresh token as the second argument." >&2
  echo "Generate with: python scripts/generate_provena_offline_token.py" >&2
  exit 1
fi

echo "Checking AWS credentials (profile: $AWS_PROFILE)..."
aws sts get-caller-identity >/dev/null

if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
  echo "Updating existing secret: $SECRET_NAME"
  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "$TOKEN" >/dev/null
else
  echo "Creating secret: $SECRET_NAME"
  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --description "Provena offline token for MCP ($DEPLOY_ENV)" \
    --secret-string "$TOKEN" >/dev/null
fi

SECRET_ARN="$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text)"
echo "Secret ARN: $SECRET_ARN"

if grep -q '^PROVENA_OFFLINE_TOKEN_SECRET_ARN=' "$CDK_ENV_SRC" 2>/dev/null; then
  sed -i "s|^PROVENA_OFFLINE_TOKEN_SECRET_ARN=.*|PROVENA_OFFLINE_TOKEN_SECRET_ARN=\"$SECRET_ARN\"|" "$CDK_ENV_SRC"
else
  printf '\nPROVENA_OFFLINE_TOKEN_SECRET_ARN="%s"\n' "$SECRET_ARN" >>"$CDK_ENV_SRC"
fi
cp "$CDK_ENV_SRC" "$CDK_ENV_ACTIVE"
echo "Updated $CDK_ENV_SRC"

if [[ "$DEPLOY_AFTER" == true ]]; then
  "$SCRIPT_DIR/deploy_mcp_stack.sh" "$ENV_NAME" deploy
fi
