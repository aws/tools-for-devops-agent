#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { GpuDiagnosticsMcpStack } from '../src/gpu-diagnostics-mcp-stack';

const app = new cdk.App();

new GpuDiagnosticsMcpStack(app, 'AwsGpuDiagnosticsMcpStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
  allowedRegions: process.env.ALLOWED_REGIONS?.split(',').filter(Boolean),
  trustedInstanceProfileArns: process.env.TRUSTED_INSTANCE_PROFILE_ARNS
    ?.split(',')
    .filter(Boolean),
  trustedInstanceRoleArns: process.env.TRUSTED_INSTANCE_ROLE_ARNS
    ?.split(',')
    .filter(Boolean),
  approvalApproverArns: process.env.APPROVAL_APPROVER_ARNS
    ?.split(',')
    .filter(Boolean),
  requireHumanApproval: process.env.REQUIRE_HUMAN_APPROVAL === 'true',
});
