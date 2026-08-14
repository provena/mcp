import * as path from "path";
import { CfnOutput, Duration, Stack } from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecsPatterns from "aws-cdk-lib/aws-ecs-patterns";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as logs from "aws-cdk-lib/aws-logs";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";
import { buildMcpPublicUrl, Settings } from "../config";

export interface McpServiceProps {
  settings: Settings;
  cluster: ecs.ICluster;
  hostedZone: route53.IHostedZone;
  /** Override for tests; default builds parent repo Dockerfile on deploy. */
  containerImage?: ecs.ContainerImage;
}

/**
 * Fargate service behind HTTPS ALB, running the Provena MCP HTTP container.
 */
export class McpService extends Construct {
  public readonly service: ecsPatterns.ApplicationLoadBalancedFargateService;
  public readonly mcpUrl: string;

  constructor(scope: Construct, id: string, props: McpServiceProps) {
    super(scope, id);

    const { settings, cluster, hostedZone } = props;
    const fullDomain = `${settings.mcpSubdomain}.${settings.baseDomain}`;
    this.mcpUrl = buildMcpPublicUrl(
      settings.mcpSubdomain,
      settings.baseDomain,
      settings.mcpHttpPath,
    );

    const repoRoot = path.resolve(__dirname, "..", "..", "..");
    const containerImage = props.containerImage
      ? props.containerImage
      : settings.mcpContainerImage
        ? ecs.ContainerImage.fromRegistry(settings.mcpContainerImage)
        : ecs.ContainerImage.fromAsset(repoRoot, {
            file: "Dockerfile",
          });

    const containerSecrets: { [name: string]: ecs.Secret } = {};
    if (settings.provenaOfflineTokenSecretArn) {
      const provenaSecret = secretsmanager.Secret.fromSecretCompleteArn(
        this,
        "ProvenaOfflineTokenSecret",
        settings.provenaOfflineTokenSecretArn,
      );
      containerSecrets.PROVENA_OFFLINE_TOKEN = ecs.Secret.fromSecretsManager(
        provenaSecret,
      );
    }
    if (settings.openAiApiKeySecretArn) {
      const openAiSecret = secretsmanager.Secret.fromSecretCompleteArn(
        this,
        "OpenAiApiKeySecret",
        settings.openAiApiKeySecretArn,
      );
      containerSecrets.OPENAI_API_KEY = ecs.Secret.fromSecretsManager(
        openAiSecret,
      );
    }
    if (settings.mcpApiKeySecretArn) {
      const mcpApiKeySecret = secretsmanager.Secret.fromSecretCompleteArn(
        this,
        "McpApiKeySecret",
        settings.mcpApiKeySecretArn,
      );
      containerSecrets.MCP_API_KEY = ecs.Secret.fromSecretsManager(mcpApiKeySecret);
    }
    if (settings.mcpOauthPasswordSecretArn) {
      const mcpOauthPasswordSecret = secretsmanager.Secret.fromSecretCompleteArn(
        this,
        "McpOauthPasswordSecret",
        settings.mcpOauthPasswordSecretArn,
      );
      containerSecrets.MCP_OAUTH_PASSWORD = ecs.Secret.fromSecretsManager(
        mcpOauthPasswordSecret,
      );
    }

    this.service = new ecsPatterns.ApplicationLoadBalancedFargateService(
      this,
      "service",
      {
        cluster,
        desiredCount: 1,
        cpu: settings.mcpCpu,
        memoryLimitMiB: settings.mcpMemoryMiB,
        publicLoadBalancer: true,
        assignPublicIp: false,
        taskSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        protocol: elbv2.ApplicationProtocol.HTTPS,
        redirectHTTP: true,
        domainName: fullDomain,
        domainZone: hostedZone,
        enableExecuteCommand: true,
        circuitBreaker: { rollback: true },
        taskImageOptions: {
          image: containerImage,
          containerPort: 5000,
          environment: {
            MCP_HTTP_HOST: "0.0.0.0",
            MCP_HTTP_PORT: "5000",
            MCP_HTTP_PATH: settings.mcpHttpPath,
            MCP_HTTP_AUTH: "oauth",
            MCP_OAUTH_BASE_URL: this.mcpUrl,
            MCP_OAUTH_STATE_DIR: "/app/.oauth-state",
            PROVENA_MCP_NO_DOTENV: "1",
            PROVENA_INSTANCE: settings.provenaInstance,
            PROVENA_CONFIG_FILE: "/app/provena_instances.json",
          },
          secrets: containerSecrets,
          logDriver: ecs.LogDrivers.awsLogs({
            streamPrefix: "provena-mcp",
            logRetention: logs.RetentionDays.ONE_WEEK,
          }),
        },
      },
    );

    this.service.targetGroup.configureHealthCheck({
      path: "/health",
      protocol: elbv2.Protocol.HTTP,
      port: "5000",
      healthyHttpCodes: "200-499",
    });

    new CfnOutput(this, "McpHttpUrl", {
      value: this.mcpUrl,
      description: "Streamable HTTP MCP endpoint for remote clients (Cursor, etc.)",
      exportName: `${Stack.of(this).stackName}-McpHttpUrl`,
    });

    new CfnOutput(this, "LoadBalancerDns", {
      value: this.service.loadBalancer.loadBalancerDnsName,
      description: "ALB DNS name (Route53 alias should point MCP subdomain here)",
    });
  }
}
