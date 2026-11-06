# rds-aidba - Read-Only MySQL/PostgreSQL MCP Server

Custom MCP server for AWS DevOps Agent providing safe, query-allowlisted diagnostic access to Aurora MySQL and Aurora PostgreSQL clusters (RDS Data API required) via the RDS Data API.

## Tools (10)

| Tool | Description |
|------|-------------|
| execute_health_query | Run predefined query by engine + category + query_id |
| list_health_queries | List all queries for an engine (mysql/postgresql) |
| run_category_check | All queries in a category |
| run_full_health_check | Key queries from all categories |
| list_clusters | List Aurora/RDS clusters |
| get_cluster_health | Config, encryption, backups, monitoring |
| get_cluster_metrics | CloudWatch: CPU, connections, IOPS, lag |
| get_performance_insights | PI wait events and DB load |
| get_proxy_health | RDS Proxy status and targets |
| get_serverless_capacity | Serverless v2 ACU utilization |

## Queries: 54 total (24 MySQL + 30 PostgreSQL, 10 categories each)

## Security

- Query allowlist only (no dynamic SQL)
- Cluster/database allowlists (defense-in-depth)
- Production enforcement blocks wildcards
- No VPC required (RDS Data API)
- Function URL with AWS_IAM auth

## ⚠️ Account-level API Gateway setting

This stack creates an `AWS::ApiGateway::Account` resource to set the CloudWatch
Logs role API Gateway uses for access logging/metrics. **This is an
account-wide, region-wide setting** — it applies to every API Gateway REST API
in the account/region, not just this stack.

- If your account already has this role configured, pass its ARN via the
  `ExistingApiGatewayCloudWatchRoleArn` parameter so the stack reuses it instead
  of creating a new one.
- Deleting this stack can reset the account's CloudWatch role, which may affect
  access logging for unrelated APIs.

Deploy into a dedicated/sandbox account, or coordinate with your account owner,
before deploying into a shared account.

## Deploy

    sam build
    sam deploy --stack-name rds-aidba-mcp --capabilities CAPABILITY_NAMED_IAM --resolve-s3 --no-confirm-changeset

## Register in DevOps Agent

- URL: McpEndpointUrl from stack output (already includes /Prod/mcp)
- Service Name: execute-api
- Auth: IAM (SigV4)

## Disclaimer

This is sample code, not intended for production use without review. Validate in non-production first.
