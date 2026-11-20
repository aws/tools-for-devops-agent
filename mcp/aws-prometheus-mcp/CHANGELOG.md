# Changelog

All notable changes to this tool are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-08

### Added

- Initial contribution of the Prometheus (AMP) MCP Server, adapted from the
  open-source sample `aws-samples/sample-AIDevops-Prometheus-MCP`.
- MCP server deployed as AWS Lambda behind Amazon API Gateway, with five
  read-only tools against Amazon Managed Prometheus: `GetAvailableWorkspaces`,
  `ListMetrics`, `ExecuteQuery`, `ExecuteRangeQuery`, and `GetServerInfo`.
- Machine-to-machine authentication via Amazon Cognito (OAuth client
  credentials) with a JWT-verifying Lambda authorizer on the `/mcp` route;
  public `/health` route.
- Three-stack AWS CDK app (Cognito, Lambda, API Gateway) with read-only AMP
  IAM permissions on the MCP Lambda role.

### Changed

- Python Lambda dependencies are now installed at synth time via CDK pip
  bundling (`requirements.txt`) instead of being vendored into the repository,
  so no third-party packages or compiled artifacts are committed.
