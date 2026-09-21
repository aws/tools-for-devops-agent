# Changelog

All notable changes to this integration are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-23

### Added

- Initial release. Single CloudFormation template
  (`cloudformation/integration.yaml`) that registers the AWS-managed
  Apache Spark Troubleshooting MCP endpoint (SageMaker Unified Studio) with
  AWS DevOps Agent.
- Native use of the CloudFormation resource type
  `AWS::DevOpsAgent::Service` — no Lambda-backed custom resource is
  required for the DevOps Agent side of the registration.
- SigV4 IAM role trusted by `aidevops.amazonaws.com`, with
  `aws:SourceAccount` and `aws:SourceArn` conditions (scoped to
  `arn:aws:aidevops:<region>:<account>:service/*` per the console
  guidance), and conditional inline policies for MCP invoke, EMR on EC2,
  EMR Serverless, Glue, S3 access on caller-supplied Spark artifacts
  buckets, and optional CloudWatch Logs KMS decrypt.
- IAM shape mirrors the AWS canonical
  `spark-troubleshooting-mcp-setup.yaml` template with S3 access
  tightened to caller-supplied bucket names.
- Region fail-fast (`Rules` block) covering the 11 regions where both AWS
  DevOps Agent and the SageMaker Unified Studio MCP service are
  available.

### Notes

- **Only the IAM role and the DevOps Agent Service registration are
  deployed.** No VPC, subnets, VPC endpoint, or DevOps Agent Private
  Connection are created. Investigation during PR review (see
  [`aws/tools-for-devops-agent#103`](https://github.com/aws/tools-for-devops-agent/pull/103))
  confirmed that AWS DevOps Agent reaches SigV4-authenticated MCPs over
  the AWS backbone using the MCP's publicly-resolvable endpoint. The
  DevOps Agent API also explicitly rejects `PrivateConnectionName` on
  SigV4 Services. Any VPC endpoint / Private Connection deployed
  alongside a SigV4 MCP is inert for the DevOps Agent → MCP data path.
- Attaching the registered Service to an Agent Space is a one-time manual
  step performed via the DevOps Agent console — out of scope for the
  template.
