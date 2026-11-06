# Prometheus (AMP) MCP Server

An MCP server that gives AWS DevOps Agent read-only access to Amazon Managed Prometheus (AMP) via PromQL, so investigations can correlate Prometheus-sourced metrics (EKS/Kubernetes, container, and custom application signals) with the agent's other evidence. It is deployed as an AWS Lambda function fronted by Amazon API Gateway, with machine-to-machine authentication through Amazon Cognito (OAuth client credentials, JWT-verified by a Lambda authorizer).

> **Sample code notice.** This is sample code and is not intended for production use without additional review and testing. Validate it in a non-production environment first, review the IAM permissions and authentication configuration against your organization's policies, and confirm the behavior meets your operational requirements before any production use. See the repository [LICENSE](../../LICENSE).

## Tools (5)

| Tool | Description |
|------|-------------|
| `GetAvailableWorkspaces` | List available Amazon Managed Prometheus workspaces in the region |
| `ListMetrics` | Return the sorted list of available metric names in a workspace |
| `ExecuteQuery` | Run a PromQL instant query |
| `ExecuteRangeQuery` | Run a PromQL range query over a time window for trend analysis |
| `GetServerInfo` | Return Prometheus server/workspace configuration and connection info |

The backing AMP workspace is **customer-owned and is not created by this stack** — you supply an existing workspace. The Lambda is granted read-only AMP permissions only (`aps:QueryMetrics`, `aps:GetSeries`, `aps:GetLabels`, `aps:GetMetricMetadata`, `aps:ListWorkspaces`, `aps:DescribeWorkspace`).

### Tool safety classification

Every tool is **read-only**; none mutate customer state.

| Tool | Classification | AWS actions |
|------|----------------|-------------|
| `GetAvailableWorkspaces` | Read-only | `aps:ListWorkspaces`, `aps:DescribeWorkspace` |
| `ListMetrics` | Read-only | AMP query API (label/metadata read) |
| `ExecuteQuery` | Read-only | AMP query API (`aps:QueryMetrics`) |
| `ExecuteRangeQuery` | Read-only | AMP query API (`aps:QueryMetrics`) |
| `GetServerInfo` | Read-only | AMP metadata read |

There are no write, remote-write, create, modify, or delete operations in this
server's tool surface.

## Security

- **AuthN/AuthZ:** `/mcp` is protected by a Cognito machine-to-machine OAuth flow;
  a Lambda authorizer verifies the JWT signature against the Cognito JWKS, the
  issuer, expiry, `token_use`, and the required scope before the request reaches
  the MCP Lambda. `/health` is unauthenticated and returns only static liveness.
- **Least privilege:** the MCP Lambda role carries only the read-only AMP actions
  listed above plus basic Lambda logging. No write actions, no `iam:*`, no
  `organizations:*`.
- **Data boundary:** the server reads time-series metric values (data-plane) from
  the operator-supplied AMP workspace and returns them to the caller. It stores
  nothing and writes nothing back to the workspace.
- **Threat-model notes for review:** inputs are PromQL strings and workspace ids
  from an authenticated caller; the main abuse vectors are expensive/high-
  cardinality queries (mitigated by AMP's own query limits and the companion
  skill's query-hygiene guidance) and token misuse (mitigated by signature +
  scope verification). The generated `mcp-server-config.json` contains an OAuth
  client secret and is git-ignored. This tool has not yet completed a Talos
  AppSec review; that review is tracked as a prerequisite in the pull request.

## Architecture

```
MCP client / DevOps Agent
        │  (HTTPS + OAuth JWT)
        ▼
API Gateway  ──►  JWT Authorizer Lambda  ──►  (validates Cognito access token + scope)
        │
        ▼
Prometheus MCP Lambda  ──►  Amazon Managed Prometheus (AMP)  [customer-owned]
```

- `/mcp` (POST) — protected by the Cognito JWT authorizer
- `/health` (GET) — public health check

Three CDK stacks are deployed: `PrometheusLambdaMCPCognitoStack` (user pool, M2M client, domain), `PrometheusLambdaMCPStack` (MCP Lambda + IAM role), and `PrometheusLambdaMCPAPIGatewayStack` (REST API, authorizer, config generation). See [`docs/CALL_FLOW.md`](docs/CALL_FLOW.md) and [`docs/AUTHENTICATION_METHODS.md`](docs/AUTHENTICATION_METHODS.md) for details.

## Prerequisites

- Node.js 18+ and npm
- AWS CDK v2 CLI (`npm install -g aws-cdk`)
- Docker running locally — Python dependencies are installed at synth time via CDK bundling (they are not vendored into this repository)
- `jq` (for the config helper scripts)
- AWS credentials for the target account/region, and an existing Amazon Managed Prometheus workspace

## Deploy

```bash
npm install

# first time in the account/region
cdk bootstrap --region us-west-2

# deploy all three stacks
cdk deploy --app 'npx ts-node bin/lambda-app.ts' --all --region us-west-2

# fill in the generated client secret
./update-mcp-config.sh        # use update-mcp-config-cloudshell.sh in CloudShell
```

Deployment writes `mcp-server-config.json` (endpoint, OAuth client id/secret, token exchange URL, tool list). This file contains a client secret and is git-ignored — do not commit it.

### Verify

```bash
# health check
curl "$(jq -r '.endpoint' mcp-server-config.json | sed 's/mcp$/health/')"

# authenticated tools/list
python3 test_lambda_mcp_endpoint.py
```

## Register in AWS DevOps Agent

This server authenticates with OAuth (Cognito client credentials), so register it as an MCP server using the values from `mcp-server-config.json`:

- Endpoint: the `endpoint` value (ends in `/mcp`)
- Token exchange URL, client id, and client secret: from `authorization_configuration`
- Scope: `prometheus-mcp-server/read`

Attaching the registered server to an Agent Space is a one-time manual step in the DevOps Agent console. See the [guide to connecting MCP servers](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-connecting-mcp-servers.html).

## Development

```bash
npm run build     # tsc
npm run synth     # cdk synth
npm run destroy   # tear down all stacks

# Python unit / property / integration tests for the MCP wrapper
cd lambda-mcp-wrapper/lambda
python3 -m pytest test_migration.py test_properties.py
```

## Cleanup

```bash
cdk destroy --app 'npx ts-node bin/lambda-app.ts' --all --region us-west-2
rm -f mcp-server-config.json
```

## Repository layout

This server is an AWS CDK app, following the CDK-based MCP convention already
used in this repo by `mcp/ecs-instance-log-mcp/` and
`mcp/aws-eks-node-diagnostics-mcp/`:

| Path | Contents |
|------|----------|
| `bin/`, `lib/`, `cdk.json` | CDK app entry and the three stacks |
| `lambda-mcp-wrapper/lambda/` | MCP server Lambda source (`awslabs/prometheus_mcp_server`, handlers) + `requirements.txt` |
| `lambda/` | JWT authorizer Lambda source + `requirements.txt` |
| `docs/` | call flow and authentication-method docs, architecture image |
| `tests` | `test_lambda_mcp_endpoint.py` (endpoint) and `lambda-mcp-wrapper/lambda/test_*.py` (unit/property/integration) |

Python dependencies are installed at synth time via CDK pip bundling, so no
third-party packages are committed. The other repo layout — a SAM
`template.yaml` + `src/` (as in `rds-aidba` and `aws-vpc-dns-diagnostics-mcp`) —
is an alternative convention; this contribution stays on CDK. Happy to convert
to the SAM layout if maintainers prefer it standardized.

## Companion skill

An investigation skill that teaches the agent when and how to use these five
tools (discover-before-query, RED/USE method, baselining, query hygiene) is at
[`skills/prometheus-amp-investigation/`](../../skills/prometheus-amp-investigation).

## Attribution

Derived from the open-source sample [`aws-samples/sample-AIDevops-Prometheus-MCP`](https://github.com/aws-samples/sample-AIDevops-Prometheus-MCP). The Prometheus MCP server package under `lambda-mcp-wrapper/lambda/awslabs/prometheus_mcp_server/` originates from AWS Labs.
