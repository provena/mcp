#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { applyCdkEnvironment, settings } from "../lib/config";
import { ProvenaMcpStack } from "../lib/provena-mcp-stack";

applyCdkEnvironment(settings);

const app = new cdk.App();

new ProvenaMcpStack(app, settings.stackName, {
  env: { account: settings.awsAccountId, region: settings.awsRegion },
  settings,
});
