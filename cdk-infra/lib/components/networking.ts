import { Construct } from "constructs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecs from "aws-cdk-lib/aws-ecs";

export interface NetworkingProps {}

/**
 * VPC and ECS cluster shared by the Provena MCP service.
 */
export class Networking extends Construct {
  public readonly vpc: ec2.IVpc;
  public readonly cluster: ecs.Cluster;

  constructor(scope: Construct, id: string, props: NetworkingProps) {
    super(scope, id);

    this.vpc = new ec2.Vpc(this, "vpc", {
      maxAzs: 2,
      natGateways: 1,
    });

    this.cluster = new ecs.Cluster(this, "cluster", {
      vpc: this.vpc,
    });
  }
}
