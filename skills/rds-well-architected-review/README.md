# RDS WAR — Amazon RDS / Aurora Well-Architected Review (All Five Pillars)

A single, consolidated Well-Architected Review skill for Amazon RDS and Aurora,
built for the [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html).
It merges the five previously separate pillar skills — **Reliability, Security,
Operational Excellence, Performance Efficiency, and Cost Optimization** — into one
workflow. Database-internal (data-plane) diagnostics are **folded into the relevant
pillar** and executed read-only via the **AWS CLI RDS Data API** — there is no
separate data-plane document and no MCP server.

The combined final report covers **all five pillars**, with each pillar's section
including both its AWS-managed findings and its database-internal findings.

## What It Does

When activated, this skill instructs the DevOps Agent to:
1. Discover RDS instances and Aurora clusters in the configured account/regions.
2. **Reliability** — Multi-AZ/replication, backups, deletion protection, DR readiness, engine version lifecycle/EOL, replication lag, failover; plus database-internal checks (transaction-ID wraparound via `pg_database`, connection capacity via `pg_stat_activity`/`Threads_connected`, Aurora replica lag via `mysql.ro_replica_status`, long transactions via `innodb_trx`).
3. **Security** — encryption at rest/in transit, network exposure & security groups, IAM auth, Secrets Manager, audit logging, log-pattern scan, PCI-DSS/HIPAA/SOC 2/GDPR mapping; plus database-internal checks (roles/privileges via `pg_roles`/`mysql.user`, TLS via `pg_settings`/`require_secure_transport`, password storage, `pg_hba_file_rules`, audit plugins).
4. **Operational Excellence** — CloudWatch alarm coverage, event subscriptions, logging config, CloudWatch Database Insights (Standard/Advanced) & Enhanced Monitoring, maintenance windows, autovacuum/InnoDB maintenance, tagging, change management; plus database-internal checks (logging & instrumentation via `pg_settings`/`performance_schema`, autovacuum tuning/effectiveness, critical MySQL variables).
5. **Performance Efficiency** — 15-day metrics, Database Insights (DB load), slow/expensive queries, index health, table bloat, temp-space usage, tuning parameters; plus database-internal checks (buffer pool/cache hit, activity & lock waits, top queries via `pg_stat_statements`/`events_statements_summary_by_digest`, unused/redundant indexes, sizes/fragmentation, config baselines).
6. **Cost Optimization** — spend breakdown, right-sizing, Graviton, Serverless v2, storage (gp2→gp3), I/O-Optimized decisions, idle resources, backup/snapshot cost, RI/Database Savings Plans coverage; plus database-internal checks (idle-database confirmation, storage-reclaim/archiving candidates).
7. Produce a single combined WAR report artifact — reproducing the full detail of every individual pillar skill (all tables, findings, and recommendations) — with a per-pillar scorecard, **PNG charts** (scorecard, findings-by-severity, and per-pillar metric/coverage/spend charts), a Scope Covered section, consolidated findings, and prioritized recommendations. The report `.md` plus its `.png` charts are saved as artifacts.

## How Database-Internal Checks Run

Where a pillar needs engine-level state that the RDS/CloudWatch APIs don't expose, the
skill queries the database catalogs/views directly with the **AWS CLI RDS Data API**:

```
aws rds-data execute-statement \
  --resource-arn <cluster-arn> \
  --secret-arn <secrets-manager-arn> \
  --database <db-name> \
  --sql "<read-only SELECT / SHOW>"
```

The SKILL describes each check as **intent** — the catalog/view/variable to query
(e.g. `pg_stat_statements`, `pg_settings`, `pg_stat_activity`, `mysql.user`,
`innodb_trx`) and what to look for — and the agent composes the read-only statement
for the target engine. If the RDS Data API is unavailable (e.g. standard RDS or Data
API disabled), the skill reports control-plane + CloudWatch findings and lists the
intended catalog/view checks for manual execution.

## Agent Types

* **On-demand** — conversational invocation ("run an RDS Well-Architected Review", "Aurora WAR", "check my RDS backups", "RDS cost review", "check RDS buffer pool / locks / connections").
* **Evaluation** — proactive multi-pillar recommendations.

## Single-Pillar vs Full Review

- Ask for a **full review / WAR** (or don't specify) → all five pillars.
- Ask for **one pillar** (e.g., "RDS security review") → that pillar's section only, including its database-internal checks.

## Prerequisites

The Agent Space's IAM role must have read access to (union across all pillars):

* `rds:Describe*`, `rds:ListTagsForResource`
* `cloudwatch:GetMetricData`, `cloudwatch:DescribeAlarmsForMetric`, `cloudwatch:DescribeAlarms`, `cloudwatch:GetMetricStatistics`
* `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:StartQuery`, `logs:GetQueryResults`
* `ec2:DescribeSecurityGroups`, `ec2:DescribeSubnets`
* `kms:DescribeKey`, `kms:ListAliases`
* `pi:GetResourceMetrics`, `pi:DescribeDimensionKeys` (DB-load retrieval for CloudWatch Database Insights, via the Performance Insights API)
* `ce:GetCostAndUsage`, `ce:GetReservationCoverage`, `ce:GetSavingsPlansCoverage` (Cost Explorer)
* `application-autoscaling:DescribeScalableTargets`
* `iam:*` read for database-auth review

**Database-internal checks:** collected through the API permissions above — CloudWatch
Database Insights / Performance Insights (`pi:*`), CloudWatch metrics & Logs, and
parameter groups (`rds:DescribeDB[Cluster]Parameters`, covered by `rds:Describe*`). No
DB connection, DB credentials, or MCP server are required. A small set of catalog-only
residual checks (roles/grants, `pg_hba`, autovacuum effectiveness, table bloat,
unused/redundant indexes, per-object sizes) is optional; where the environment does not
permit them, the skill marks those checks NOT VERIFIED and still produces the report.

## Read-Only & Safety

This skill is strictly **read-only**. It never modifies resources, data, schema, or
configuration, never executes DDL/DML/DCL, and never exposes credentials.
Database-internal checks are read-only `SELECT`/`SHOW` statements only. If a tool call
fails or data is unavailable, it reports that explicitly rather than estimating.

## Uploading

```bash
cd "RDS Well Architected Review Skills"
zip -r rds-war.zip rds-war/ -x '*.DS_Store'
```

Upload the zip via the Operator Web App **Skills** page → **Add skill** → **Upload skill**.

## Skill Contents

```
rds-war/
├── SKILL.md                                # combined skill instructions (all 5 pillars, data-plane folded in)
├── README.md                               # this file
└── references/
    ├── reliability-checklist.md            # Reliability pillar checklist
    ├── security-checklist.md               # Security pillar checklist + compliance mapping
    ├── ops-excellence-checklist.md         # Operational Excellence checklist
    ├── performance-metrics-thresholds.md   # Performance metrics thresholds & config baselines
    ├── cost-optimization-reference.md      # Cost optimization reference tables
    └── report-structure.md                 # authoritative combined report template + PNG chart catalog
```

## Provenance

This skill consolidates, without loss of content, the five source pillar skills
(`rds-reliability-review`, `rds-security-review`, `rds-ops-excellence-review`,
`rds-performance-review`, `rds-cost-optimization-review`). The database-internal
(data-plane) diagnostics from the `database-rds-devops` skill are incorporated as
per-pillar **intent** — the catalog/view to query and what to look for — run via the
AWS CLI RDS Data API, rather than as copied SQL, a separate document, or an MCP server.
