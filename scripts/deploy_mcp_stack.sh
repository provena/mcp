#!/usr/bin/env bash
# Deploy, diff, or destroy the Provena MCP CDK stack for dev or prod.
#
# Usage:
#   ./scripts/deploy_mcp_stack.sh dev diff
#   ./scripts/deploy_mcp_stack.sh dev deploy
#   ./scripts/deploy_mcp_stack.sh prod deploy
#   ./scripts/deploy_mcp_stack.sh dev destroy
#
# Override credentials:
#   AWS_PROFILE=my-dev-profile ./scripts/deploy_mcp_stack.sh dev deploy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/mcp_deploy_env.sh
source "$SCRIPT_DIR/lib/mcp_deploy_env.sh"

ENV_NAME="${1:-}"
ACTION="${2:-deploy}"

if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <dev|prod> [deploy|diff|destroy|synth|config-check]" >&2
  exit 1
fi

mcp_deploy_env_activate "$ENV_NAME"
mcp_deploy_env_sync

echo "Target ($DEPLOY_ENV):"
mcp_deploy_env_print_target
echo "AWS profile: $AWS_PROFILE"

echo "Checking AWS credentials..."
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
# shellcheck disable=SC1090
source "$CDK_ENV_ACTIVE"
if [[ "$ACCOUNT" != "$AWS_ACCOUNT_ID" ]]; then
  echo "Error: active AWS account ($ACCOUNT) does not match $CDK_ENV_SRC (AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID)." >&2
  exit 1
fi

cd "$CDK_DIR"
if command -v pnpm >/dev/null 2>&1; then
  RUNNER=(pnpm exec)
else
  RUNNER=(npx)
fi

case "$ACTION" in
  config-check)
    "${RUNNER[@]}" ts-node lib/config.ts
    ;;
  synth)
    "${RUNNER[@]}" cdk synth
    ;;
  diff)
    "${RUNNER[@]}" ts-node lib/config.ts
    "${RUNNER[@]}" cdk diff
    ;;
  deploy)
    "${RUNNER[@]}" ts-node lib/config.ts
    "${RUNNER[@]}" cdk deploy --require-approval never
    ;;
  destroy)
    "${RUNNER[@]}" ts-node lib/config.ts
    "${RUNNER[@]}" cdk destroy --force
    ;;
  *)
    echo "Unknown action: $ACTION" >&2
    exit 1
    ;;
esac
