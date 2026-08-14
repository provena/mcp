# Shared helpers for dev/prod MCP CDK deployments.
# Source from other scripts: source "$(dirname "$0")/lib/mcp_deploy_env.sh"

_mcp_deploy_env_root() {
  cd "$(dirname "${BASH_SOURCE[1]}")/../.." && pwd
}

# Resolve env name (dev|prod), set CDK_ENV_SRC/CDK_ENV_ACTIVE and AWS profile defaults.
# Usage: mcp_deploy_env_activate dev
mcp_deploy_env_activate() {
  local env_name="${1:-}"
  ROOT="$(_mcp_deploy_env_root)"
  CDK_DIR="$ROOT/cdk-infra"

  case "$env_name" in
    dev)
      DEPLOY_ENV="dev"
      CDK_ENV_SRC="$CDK_DIR/.env.dev"
      DEFAULT_AWS_PROFILE="${MCP_DEV_AWS_PROFILE:-239021088610_AdministratorAccess}"
      EXPECTED_BASE_DOMAIN="rrap-is.com"
      EXPECTED_PROVENA_INSTANCE="dev.rrap-is.com"
      ;;
    prod)
      DEPLOY_ENV="prod"
      CDK_ENV_SRC="$CDK_DIR/.env.prod"
      DEFAULT_AWS_PROFILE="${MCP_PROD_AWS_PROFILE:-mds-prod-administrator}"
      EXPECTED_BASE_DOMAIN="mds.gbrrestoration.org"
      EXPECTED_PROVENA_INSTANCE="mds.gbrrestoration.org"
      ;;
    *)
      echo "Error: environment must be 'dev' or 'prod' (got: ${env_name:-<empty>})" >&2
      return 1
      ;;
  esac

  CDK_ENV_ACTIVE="$CDK_DIR/.env"
  export AWS_PROFILE="${AWS_PROFILE:-$DEFAULT_AWS_PROFILE}"
  export AWS_REGION="${AWS_REGION:-ap-southeast-2}"
  export AWS_DEFAULT_REGION="$AWS_REGION"
}

mcp_deploy_env_require_file() {
  if [[ ! -f "$CDK_ENV_SRC" ]]; then
    echo "Error: missing $CDK_ENV_SRC" >&2
    echo "Copy from ${CDK_ENV_SRC}.dist and fill in account/secret ARNs." >&2
    return 1
  fi
}

mcp_deploy_env_sync() {
  mcp_deploy_env_require_file
  cp "$CDK_ENV_SRC" "$CDK_ENV_ACTIVE"
  echo "Using $DEPLOY_ENV config: $CDK_ENV_SRC -> $CDK_ENV_ACTIVE"
}

mcp_deploy_env_print_target() {
  # shellcheck disable=SC1090
  set -a
  source "$CDK_ENV_ACTIVE"
  set +a
  echo "  account: ${AWS_ACCOUNT_ID:-?}"
  echo "  region:  ${AWS_REGION:-?}"
  echo "  stack:   ${STACK_NAME:-?}"
  echo "  url:     https://${MCP_SUBDOMAIN:-?}.${BASE_DOMAIN:-?}"
  echo "  provena: ${PROVENA_INSTANCE:-?}"
}
