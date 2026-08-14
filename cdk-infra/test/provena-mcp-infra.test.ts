import * as cdk from "aws-cdk-lib";
import * as ecs from "aws-cdk-lib/aws-ecs";
import { Template } from "aws-cdk-lib/assertions";
import { Settings } from "../lib/config";
import { McpService } from "../lib/components/mcp-service";
import { Networking } from "../lib/components/networking";
import * as route53 from "aws-cdk-lib/aws-route53";

const testSettings: Settings = {
  stackName: "provena-mcp-test",
  awsAccountId: "123456789012",
  awsRegion: "ap-southeast-2",
  awsHostedZoneId: "Z1234567890ABC",
  baseDomain: "example.com",
  mcpSubdomain: "provena-mcp",
  provenaInstance: "dev.rrap-is.com",
  mcpCpu: 256,
  mcpMemoryMiB: 1024,
  mcpHttpPath: "/",
};

test("McpService synthesizes without Docker build", () => {
  const app = new cdk.App();
  const stack = new cdk.Stack(app, "TestStack");
  const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
    stack,
    "Zone",
    {
      hostedZoneId: testSettings.awsHostedZoneId,
      zoneName: testSettings.baseDomain,
    },
  );
  const { cluster } = new Networking(stack, "networking", {});
  new McpService(stack, "mcp", {
    settings: testSettings,
    cluster,
    hostedZone,
    containerImage: ecs.ContainerImage.fromRegistry("amazon/amazon-ecs-sample"),
  });
  const template = Template.fromStack(stack);

  template.resourceCountIs("AWS::ECS::Service", 1);
  template.hasResourceProperties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
    Scheme: "internet-facing",
  });
});
