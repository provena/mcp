#!/usr/bin/env bash
# Bootstrap CDK in the dev or prod AWS account/region from cdk-infra/.env.<env>.
#
# Usage:
#   ./scripts/bootstrap_mcp_aws.sh dev
#   AWS_PROFILE=mds-prod-admin ./scripts/bootstrap_mcp_aws.sh prod

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/mcp_deploy_env.sh
source "$SCRIPT_DIR/lib/mcp_deploy_env.sh"

ENV_NAME="${1:-}"
if [[ -z "$ENV_NAME" ]]; then
  echo "Usage: $0 <dev|prod>" >&2
  exit 1
fi

mcp_deploy_env_activate "$ENV_NAME"
mcp_deploy_env_sync

# shellcheck disable=SC1090
source "$CDK_ENV_ACTIVE"

echo "Bootstrapping CDK for $DEPLOY_ENV ($AWS_ACCOUNT_ID / $AWS_REGION)..."
aws sts get-caller-identity >/dev/null

cd "$CDK_DIR"
if command -v pnpm >/dev/null 2>&1; then
  pnpm exec cdk bootstrap "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
else
  npx cdk bootstrap "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
fi

echo "Done. Next: ./scripts/setup_mcp_offline_token_aws.sh $ENV_NAME <token>"
