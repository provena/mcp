import { z } from "zod";
import * as dotenv from "dotenv";
import * as path from "path";

dotenv.config({ path: path.resolve(__dirname, "..", ".env") });

const envSchema = z.object({
  AWS_ACCOUNT_ID: z
    .string()
    .min(1, "AWS_ACCOUNT_ID: AWS Account ID is required"),
  AWS_REGION: z.string().min(1, "AWS_REGION: AWS Region is required"),
  AWS_HOSTED_ZONE_ID: z
    .string()
    .min(1, "AWS_HOSTED_ZONE_ID: AWS Hosted Zone ID is required"),
  BASE_DOMAIN: z.string().min(1, "BASE_DOMAIN: Base domain is required"),
  MCP_SUBDOMAIN: z
    .string()
    .min(1, "MCP_SUBDOMAIN: MCP subdomain is required"),
  STACK_NAME: z
    .string()
    .min(1, "STACK_NAME: Must supply a stack name for the CDK stack"),
  PROVENA_INSTANCE: z
    .string()
    .min(1, "PROVENA_INSTANCE: Provena instance key is required"),
  MCP_CPU: z.string().optional(),
  MCP_MEMORY_MIB: z.string().optional(),
  MCP_HTTP_PATH: z.string().optional(),
  MCP_CONTAINER_IMAGE: z.string().optional(),
  PROVENA_OFFLINE_TOKEN_SECRET_ARN: z.string().optional(),
  OPENAI_API_KEY_SECRET_ARN: z.string().optional(),
  MCP_API_KEY_SECRET_ARN: z.string().optional(),
  MCP_OAUTH_PASSWORD_SECRET_ARN: z.string().optional(),
});

const settingsSchema = z.object({
  stackName: z.string(),
  awsAccountId: z.string(),
  awsRegion: z.string(),
  awsHostedZoneId: z.string(),
  baseDomain: z.string(),
  mcpSubdomain: z.string(),
  provenaInstance: z.string(),
  mcpCpu: z.number().int().positive(),
  mcpMemoryMiB: z.number().int().positive(),
  mcpHttpPath: z.string(),
  mcpContainerImage: z.string().optional(),
  provenaOfflineTokenSecretArn: z.string().optional(),
  openAiApiKeySecretArn: z.string().optional(),
  mcpApiKeySecretArn: z.string().optional(),
  mcpOauthPasswordSecretArn: z.string().optional(),
});

export type Settings = z.infer<typeof settingsSchema>;

/** Align CDK CLI and AWS SDK region/account with validated `.env` settings. */
export function applyCdkEnvironment(settings: Settings): void {
  process.env.AWS_REGION = settings.awsRegion;
  process.env.AWS_DEFAULT_REGION = settings.awsRegion;
  process.env.CDK_DEFAULT_REGION = settings.awsRegion;
  process.env.CDK_DEFAULT_ACCOUNT = settings.awsAccountId;
}

/** Public HTTPS URL for remote MCP clients (no trailing slash when path is `/`). */
export function buildMcpPublicUrl(
  mcpSubdomain: string,
  baseDomain: string,
  httpPath: string,
): string {
  const host = `${mcpSubdomain}.${baseDomain}`;
  const path = httpPath.startsWith("/") ? httpPath : `/${httpPath}`;
  if (path === "/") {
    return `https://${host}`;
  }
  return `https://${host}${path}`;
}

export function buildSettingsFromEnv(): Settings {
  let env;
  try {
    env = envSchema.parse(process.env);
  } catch (error) {
    let hint = "";
    if (error instanceof z.ZodError) {
      const missingVars = error.issues
        .map((issue) => issue.path[0])
        .filter((path) => path !== undefined);
      if (missingVars.length > 0) {
        hint = `\nLikely missing env variable(s): ${missingVars.join(", ")}`;
      }
    }
    throw new Error(
      `Config validation failed: Missing or invalid environment variables; check your '.env' file.${hint}\n${error}`,
    );
  }

  const mcpCpu = env.MCP_CPU ? parseInt(env.MCP_CPU, 10) : 256;
  const mcpMemoryMiB = env.MCP_MEMORY_MIB
    ? parseInt(env.MCP_MEMORY_MIB, 10)
    : 1024;

  if (Number.isNaN(mcpCpu) || Number.isNaN(mcpMemoryMiB)) {
    throw new Error(
      "Config validation failed: MCP_CPU and MCP_MEMORY_MIB must be integers when set.",
    );
  }

  const mcpHttpPath = env.MCP_HTTP_PATH?.trim() || "/";

  try {
    return settingsSchema.parse({
      stackName: env.STACK_NAME,
      awsRegion: env.AWS_REGION,
      awsAccountId: env.AWS_ACCOUNT_ID,
      awsHostedZoneId: env.AWS_HOSTED_ZONE_ID,
      baseDomain: env.BASE_DOMAIN,
      mcpSubdomain: env.MCP_SUBDOMAIN,
      provenaInstance: env.PROVENA_INSTANCE,
      mcpCpu,
      mcpMemoryMiB,
      mcpHttpPath,
      mcpContainerImage: env.MCP_CONTAINER_IMAGE?.trim() || undefined,
      provenaOfflineTokenSecretArn: env.PROVENA_OFFLINE_TOKEN_SECRET_ARN,
      openAiApiKeySecretArn: env.OPENAI_API_KEY_SECRET_ARN,
      mcpApiKeySecretArn: env.MCP_API_KEY_SECRET_ARN,
      mcpOauthPasswordSecretArn: env.MCP_OAUTH_PASSWORD_SECRET_ARN,
    } satisfies Settings);
  } catch (error) {
    throw new Error(
      `Config validation failed: Invalid settings transformation.\n${error}`,
    );
  }
}

/** Resolved settings (loads `.env` from `cdk-infra/` when imported). */
export const settings = buildSettingsFromEnv();

function printConfigSummary(): void {
  console.log("Config OK");
  console.log(`  stack: ${settings.stackName}`);
  console.log(`  region: ${settings.awsRegion}`);
  console.log(
    `  mcp url: ${buildMcpPublicUrl(
      settings.mcpSubdomain,
      settings.baseDomain,
      settings.mcpHttpPath,
    )}`,
  );
  console.log(`  mcp http path (container): ${settings.mcpHttpPath}`);
}

// ts-node / node entry (CommonJS main check)
const isMain =
  typeof require !== "undefined" &&
  require.main === module;

if (isMain) {
  printConfigSummary();
}
