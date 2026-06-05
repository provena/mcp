# Provena MCP — AWS CDK infrastructure

Deploys the [Provena MCP](../README.md) HTTP server on **ECS Fargate** (default path `/` on the MCP subdomain) behind an **HTTPS Application Load Balancer**, with DNS in an existing **Route 53** hosted zone.

Configuration follows the same pattern as [rrap-cf-aws-infra](https://github.com/gbrrestoration/rrap-cf-aws-infra): **`.env`** + **Zod** validation in `lib/config.ts`.

While the stack is deployed, the ECS service runs with **`desiredCount = 1`**. There is no automatic scale-to-zero. To save cost, **destroy the stack** when the environment is not needed and **deploy** again when it is.

## Prerequisites

- Node.js **22+** and **npm** or **pnpm**
- AWS CLI credentials for the target account
- CDK bootstrapped in **`AWS_REGION`**: `npm exec cdk bootstrap aws://ACCOUNT/REGION` (use the same region as in `.env`, e.g. `ap-southeast-2` — not your CLI default if that differs)
- Route 53 **hosted zone** for `BASE_DOMAIN` (zone ID in `.env`)
- Docker running locally (CDK builds the image from the parent repo `Dockerfile` on deploy)

### Docker build inputs (parent repo)

The root `Dockerfile` copies `provena_instances.json` and `provena_tokens.json`. Before the first deploy, from the **repository root**:

```sh
cp provena_instances.example.json provena_instances.json
```

Use a minimal placeholder for tokens (runtime auth should come from Secrets Manager, not the image):

```sh
echo "{}" > provena_tokens.json
```

Do **not** commit real tokens. Prefer `PROVENA_OFFLINE_TOKEN_SECRET_ARN` in `.env` for production.

## Setup

```sh
cd cdk-infra
pnpm install
cp .env.dist .env
# Edit .env with your account, region, domain, and Provena instance key
pnpm config-check
```

## Secrets (recommended)

Create secrets in **AWS Secrets Manager** (plain string secret values), then set full ARNs in `.env`:

| Variable | Injected as |
|----------|-------------|
| `PROVENA_OFFLINE_TOKEN_SECRET_ARN` | `PROVENA_OFFLINE_TOKEN` |
| `OPENAI_API_KEY_SECRET_ARN` | `OPENAI_API_KEY` |

Example CLI (adjust region/name):

```sh
aws secretsmanager create-secret \
  --name provena-mcp/offline-token \
  --secret-string "YOUR_REFRESH_TOKEN"
```

Grant the ECS task execution role read access (CDK grants this when ARNs are set).

The CDK app sets `CDK_DEFAULT_REGION` and `AWS_REGION` from `.env` on startup so `cdk diff` / `cdk deploy` target the same region as the stack (not necessarily your AWS CLI default, e.g. `us-east-1`).

## Deploy (spin up)

From `cdk-infra/`:

```sh
pnpm config-check
pnpm exec cdk diff
pnpm exec cdk deploy
```

After deploy, note the **`McpHttpUrl`** output (default: `https://provena-mcp.example.com` with MCP at path `/`) and configure remote MCP clients:

```json
{
  "mcpServers": {
    "provena": {
      "type": "http",
      "url": "https://provena-mcp.example.com"
    }
  }
}
```

To use `/mcp` instead (local Docker default), set `MCP_HTTP_PATH=/mcp` in `.env` before deploy.

## Destroy (spin down)

Stops billing for the ALB, NAT gateway, Fargate task, and related stack resources created by this app:

```sh
pnpm exec cdk destroy
```

**Retained by default or outside this stack:** ECR images built during deploy, Secrets Manager secrets you created manually, and Route 53 records in zones you manage separately. Review the destroy prompt before confirming.

## Configuration reference

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_ACCOUNT_ID` | yes | Deployment account |
| `AWS_REGION` | yes | e.g. `ap-southeast-2` |
| `AWS_HOSTED_ZONE_ID` | yes | Route 53 hosted zone for `BASE_DOMAIN` |
| `BASE_DOMAIN` | yes | Root domain (e.g. `example.com`) |
| `MCP_SUBDOMAIN` | yes | Hostname prefix (e.g. `provena-mcp`) |
| `STACK_NAME` | yes | CloudFormation stack name |
| `PROVENA_INSTANCE` | yes | Instance key in `provena_instances.json` |
| `MCP_HTTP_PATH` | no | Streamable HTTP path (default `/` on subdomain root) |
| `MCP_CPU` | no | Fargate CPU units (default `256`) |
| `MCP_MEMORY_MIB` | no | Memory MiB (default `1024`) |
| `MCP_CONTAINER_IMAGE` | no | ECR/registry URI; skips local Docker build when set |
| `PROVENA_OFFLINE_TOKEN_SECRET_ARN` | no | Secrets Manager ARN |
| `OPENAI_API_KEY_SECRET_ARN` | no | Secrets Manager ARN |

Validate: `npm run config-check` (or `pnpm config-check`)

## Faster `cdk diff` / `cdk deploy`

CDK is slow when it **builds the Docker image** (`ContainerImage.fromAsset`) — the Dockerfile runs a full `pip install`, which often takes **several minutes** on the first run or after app file changes.

**What helps:**

| Situation | What to expect |
|-----------|----------------|
| **First `cdk diff`** | Slow (Docker build + CloudFormation compare) |
| **Repeat diff, no app/Dockerfile changes** | Much faster (CDK reuses cached asset hash) |
| **Only editing CDK TypeScript** | Still fast if Docker context unchanged |
| **Changed `server/`, `Dockerfile`, etc.** | Full Docker rebuild again |

**Infra-only iteration (skip Docker during diff):** after you have an image in ECR once, set in `.env`:

```bash
MCP_CONTAINER_IMAGE=123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/provena-mcp:latest
```

CDK then references that URI instead of building locally. Rebuild and push the image only when the Python app changes.

**Other tips:**

- Use `npm exec cdk diff` (or `npx cdk diff`) if you do not use pnpm.
- Keep Docker Desktop running; ensure BuildKit is enabled (Docker default on recent versions).
- `.dockerignore` excludes `cdk-infra/`, `.venv`, and large `.xlsx` files so context upload stays small.

## Common commands

```sh
pnpm build
pnpm test
pnpm exec cdk synth
pnpm exec cdk diff
pnpm exec cdk deploy
pnpm exec cdk destroy
```

## GitHub Actions

Optional workflow: [`.github/workflows/deploy-aws-cdk.yml`](.github/workflows/deploy-aws-cdk.yml). Configure a GitHub **environment** with the same variables as `.env` (repository or environment **vars**), plus `CDK_DEPLOY_GA_ROLE_ARN` for OIDC deploy.

## Architecture

```text
Internet → Route 53 (A/alias) → ALB :443 → Fargate (private subnets) :5000
                                      ↓
                              NAT → Provena / OpenAI APIs
```

## Cost note

With the stack **up**, expect roughly **USD 60–85/month** (ALB + NAT dominate; Fargate is smaller). **`cdk destroy`** removes most of that until the next deploy. Figures vary by region and task size; use the [AWS Pricing Calculator](https://calculator.aws/) for AUD/regional estimates.
