import * as cdk from "aws-cdk-lib";
import * as route53 from "aws-cdk-lib/aws-route53";
import { Construct } from "constructs";
import { Settings } from "./config";
import { McpService } from "./components/mcp-service";
import { Networking } from "./components/networking";

export interface ProvenaMcpStackProps extends cdk.StackProps {
  settings: Settings;
}

export class ProvenaMcpStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ProvenaMcpStackProps) {
    super(scope, id, props);

    const settings = props.settings;

    const hostedZone = route53.HostedZone.fromHostedZoneAttributes(
      this,
      "HostedZone",
      {
        hostedZoneId: settings.awsHostedZoneId,
        zoneName: settings.baseDomain,
      },
    );

    const { cluster, vpc } = new Networking(this, "networking", {});

    new McpService(this, "mcp", {
      settings,
      cluster,
      hostedZone,
    });
  }
}
