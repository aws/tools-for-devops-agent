# Database RDS DevOps Skill

A skill for AWS DevOps Agent that performs **read-only** health assessments, performance
diagnostics, and log-based troubleshooting for Amazon Aurora MySQL and Aurora PostgreSQL
clusters, and produces scored findings with operational recommendations.

## Purpose

Database performance investigations usually stall at the boundary between what AWS APIs
can see and what is happening inside the database engine. CloudWatch shows that CPU is
high; it cannot show which query is holding a lock or how the buffer pool is behaving.

This skill closes that gap with a three-layer approach: it grounds every recommendation
in control-plane configuration, CloudWatch observability, and — when the companion
`rds-aidba` MCP server is deployed — predefined read-only queries executed inside the
database itself.

## Key Capabilities

- **AWS-level health scoring** across encryption, monitoring, high availability, version
  currency, auto scaling, and deletion protection
- **Database-level health scoring** across connections, buffer pool, replication, locks,
  storage, indexes, and instrumentation
- **Allowlisted diagnostic queries** — 54 predefined read-only queries (24 MySQL, 30
  PostgreSQL) across 10 categories, executed via the RDS Data API through the
  `rds-aidba` MCP server. No dynamic or caller-supplied SQL.
- **CloudWatch metrics analysis** — CPU, connections, freeable memory, IOPS, and replica
  lag evaluated against severity thresholds
- **CloudWatch Logs Insights** — slow query analysis, error pattern detection, and
  deadlock identification
- **Performance Insights** — top wait events by average database load
- **Operational validation checklist** — monitoring, alerting, security, HA, cost, and
  tagging review
- **Manual-execution query references** — annotated MySQL and PostgreSQL query libraries
  for environments where the MCP server is not deployed

## Prerequisites

### IAM Permissions

The DevOps Agent role needs the following read-only permissions (most are covered by
`AIDevOpsAgentAccessPolicy`):

```
rds:DescribeDBClusters
rds:DescribeDBInstances
rds:DescribeDBEngineVersions
rds:DescribeDBClusterParameters
rds:DescribeDBLogFiles
rds:ListTagsForResource
rds:DescribeReservedDBInstances
rds:DescribeGlobalClusters
cloudwatch:GetMetricData
cloudwatch:GetMetricStatistics
cloudwatch:DescribeAlarms
logs:StartQuery
logs:GetQueryResults
logs:DescribeLogGroups
application-autoscaling:DescribeScalableTargets
ec2:DescribeSecurityGroups
```

### AWS Resources

- An Aurora MySQL or Aurora PostgreSQL cluster
- CloudWatch Logs export enabled (`slowquery`, `error`, or `postgresql` logs)
- Enhanced Monitoring enabled (recommended)
- Performance Insights enabled (recommended, required for wait-event analysis)

### For Database-Level Diagnostics (Optional)

Layers 1 and 2 work with no additional infrastructure. Database-internal diagnostics
require the **`rds-aidba`** MCP server, co-located in this repository at `mcp/rds-aidba/`.

- **Setup guide:** [`references/mcp-setup.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/database-rds-devops/references/mcp-setup.md)
- **Transport:** Streamable HTTP over a Lambda Function URL
- **Authentication:** AWS SigV4 (service name `lambda`)
- **Caller permissions:** `lambda:InvokeFunctionUrl` and `lambda:InvokeFunction` on the
  function ARN

Requirements:

- **RDS Data API enabled** on the target Aurora cluster
- Secrets Manager secret holding database credentials
- `performance_schema` enabled (default ON for Aurora MySQL 2.x and later)
- `pg_stat_statements` extension installed (Aurora PostgreSQL)
- A read-only monitoring user with `SELECT` on the relevant system schemas

Without the MCP server the skill still runs, using AWS CLI and CloudWatch only, and
supplies query references for manual execution.

## Limitations

- **Aurora clusters only.** Database-level queries run through the RDS Data API, which
  AWS supports for Aurora Serverless v1 and, on recent engine versions, Aurora
  Serverless v2 and Aurora provisioned clusters. Standard (non-Aurora) RDS MySQL and RDS
  PostgreSQL instances have no Data API endpoint and are out of scope for Layer 3. See
  [Enabling the RDS Data API](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/data-api.enabling.html).
- **One cluster per MCP deployment.** The MCP server executes SQL against the single
  cluster configured at deploy time via `CLUSTER_ARN`. Reviewing additional clusters
  requires additional deployments.
- **Read-only by design.** The skill produces recommendations; it never applies them.
- **Diagnostic output includes database identifiers.** Query results can contain database
  usernames, client addresses, and query text. Query text may embed literal values from
  `WHERE` clauses. Treat skill output with the same sensitivity as the database itself.
- **Thresholds are starting points.** Severity thresholds are general guidance and should
  be tuned to your workload.
- **Performance Insights required for wait events.** Instances without PI enabled return
  no wait-event data rather than an error.

## Agent Types

This skill is used by the following agent types (selected in the Operator Web App at
upload time):

- **Chat tasks** — interactive health checks, targeted category checks, and follow-up
  investigation
- **Incident RCA** — root cause analysis where database performance may be a contributing
  factor

Select **Generic** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/database-rds-devops` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

> **Note:** You cannot connect the `aws` GitHub organization directly because the GitHub connection setup requires admin rights on the organization. Instead, connect your personal GitHub account and select any repository from it during the connection setup. Once a GitHub connection is established, you can import skills from any public repository, including this one, even if it wasn't selected during the connection setup.

**Option B: Upload as a zip file**

1. Zip the `database-rds-devops/` directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r database-rds-devops.zip database-rds-devops/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the `database-rds-devops.zip` file (max 6 MB).
5. Select the agent types: **Chat tasks** and **Incident RCA**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to programmatically manage skills — useful for CI/CD pipelines or automation workflows. Assign the skill to the `CHAT` and `INCIDENT_RCA` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end) for the full API workflow.

For more details, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) in the AWS DevOps Agent User Guide.

## How to Use This Skill

Describe the task in natural language — you do not need to name the skill.

### Chat

```
"Run a health check on my Aurora MySQL cluster my-prod-cluster"
"Why is my Aurora MySQL cluster showing high CPU usage?"
"Check for slow queries on my Aurora cluster in the last 3 hours"
"My application is getting Too many connections errors"
"Is my Aurora PostgreSQL at risk for transaction ID wraparound?"
"Check replication lag on my Aurora read replicas"
"Review the security configuration of my database cluster"
```

### Incident RCA

```
"Aurora cluster my-prod-cluster had a latency spike at 14:20 — what happened?"
"Correlate the connection errors in this incident with database-side metrics"
"Was lock contention a factor in the checkout service degradation?"
```

### Modes

| Mode | Trigger | Behavior |
|------|---------|----------|
| Full health check | "health check", "full assessment", "comprehensive review" | All 10 diagnostic categories, scored report |
| Category check | "check connections", "storage analysis", "replication status" | One category, focused report |
| CloudWatch analysis | "analyze logs", "slow queries", "error patterns" | Logs Insights queries correlated with metrics |
| Interactive | Follow-up questions, "dig deeper" | Iterative investigation with retained context |

## MCP Tools

When the `rds-aidba` MCP server is deployed, the skill has access to these ten tools:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `execute_health_query` | `engine`, `category`, `query_id` | Run one predefined query |
| `list_health_queries` | `engine` | List available queries |
| `run_category_check` | `engine`, `category` | Run all queries in a category |
| `run_full_health_check` | `engine` | Key queries from every category |
| `list_clusters` | none | List clusters in the account |
| `get_cluster_health` | `cluster_identifier` | Cluster configuration and health |
| `get_cluster_metrics` | `cluster_identifier`, `hours_back` | CloudWatch metrics per instance |
| `get_performance_insights` | `instance_identifier` | Top wait events by DB load |
| `get_proxy_health` | `proxy_name` | RDS Proxy status and targets |
| `get_serverless_capacity` | `cluster_identifier` | Serverless v2 ACU utilization |

## Skill Structure

```
database-rds-devops/
├── SKILL.md                              # Main skill instructions
├── README.md                             # This file
├── CHANGELOG.md                          # Version history
├── DEPLOYMENT.md                         # Deployment and prerequisites detail
├── references/
│   ├── mysql-health-checks.md            # MySQL diagnostic query library
│   ├── postgresql-health-checks.md       # PostgreSQL diagnostic query library
│   ├── best-practices.md                 # Best practices by operational domain
│   ├── troubleshooting-runbooks.md       # Symptom-driven runbooks
│   ├── aurora-validation-checklist.md    # Operational validation checklist
│   └── mcp-setup.md                      # MCP server deployment guide
└── evals/
    ├── evals.json                        # Functional test scenarios
    ├── eval_queries.json                 # Trigger tests
    └── report.json                        # Evaluation results
```

## Safety

This skill operates in **read-only** mode:

- No DDL, DML, or DCL operations
- No configuration changes — recommendations only
- All database queries are predefined and allowlisted; no dynamic or caller-supplied SQL
- Credentials are resolved from Secrets Manager by the MCP server and never surfaced

## Supported Engines

| Engine | Health Check | CloudWatch | Log Analysis | DB Queries |
|--------|-------------|------------|--------------|------------|
| Aurora MySQL 2.x (5.7 compatible) | ✅ | ✅ | ✅ | ✅ |
| Aurora MySQL 3.x (8.0 compatible) | ✅ | ✅ | ✅ | ✅ |
| Aurora PostgreSQL | ✅ | ✅ | ✅ | ✅ |
| RDS MySQL / RDS PostgreSQL (non-Aurora) | ❌ | ❌ | ❌ | ❌ |

Database queries additionally require the RDS Data API to be enabled on the cluster.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Health check thresholds are
> guidelines and should be tuned to your workload characteristics.

