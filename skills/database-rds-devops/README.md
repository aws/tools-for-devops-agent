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

- **On-demand** — interactive health checks, targeted category checks, and follow-up
  investigation
- **Incident RCA** — root cause analysis where database performance may be a contributing
  factor

Select **Generic** instead if you want the skill available to all agent types.

## Uploading to AWS DevOps Agent

Grant the IAM permissions and enable the CloudWatch Logs exports in [Prerequisites](#prerequisites) first, and deploy the optional `rds-aidba` MCP server if you want database-level diagnostics, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand health checks in chat and helps root cause analysis when database performance may be a factor, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, incident triage and evaluation included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `database-rds-devops`, or filter by AWS service **Amazon RDS**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to tune the severity thresholds in `references/mysql-health-checks.md` to your workload, or to choose different agent types.

1. Clone the repository, make your changes under `skills/database-rds-devops/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f database-rds-devops.zip
   zip -r database-rds-devops.zip database-rds-devops/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l database-rds-devops.zip | tail -1   # expect 8 files
   ```

2. Check that the zip has this structure:

   ```text
   database-rds-devops.zip
   └── database-rds-devops/
       ├── SKILL.md                # required: frontmatter with name and description
       ├── DEPLOYMENT.md
       └── references/             # 6 files: MySQL and PostgreSQL health checks, best practices, runbooks, validation checklist, MCP setup
   ```

   The zip leaves out `evals/`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `database-rds-devops.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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

