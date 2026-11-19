---
name: rds-well-architected-review
description: >-
  Run a Well-Architected Review (WAR) of Amazon RDS and Aurora across the five pillars
  (Reliability, Security, Operational Excellence, Performance Efficiency, Cost
  Optimization), or any single pillar, plus database-internal health checks (connections,
  locks, replication lag, buffer cache, autovacuum, transaction-ID wraparound). Read-only:
  uses RDS, CloudWatch, Database Insights and parameter-group data, with the RDS Data API
  only for catalog-only checks. Produces a scored report with charts. Use when the user asks
  for an "RDS Well-Architected Review", "RDS WAR", "Aurora WAR", "RDS security review",
  "RDS HA/DR audit", "RDS performance review", "RDS cost optimization", or to check RDS
  backups, alarms, buffer pool, locks or connections.
metadata:
  author: aws-samples
  version: "1.1.0"
  aws-devops-agent-skills.agent-types: "On-demand, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon RDS, Amazon Aurora"
  aws-devops-agent-skills.technical-domains: "Databases, Reliability, Security, Operations, Performance, Cost Optimization"
---

# RDS / Aurora Well-Architected Review (RDS WAR)

Conduct a complete Well-Architected operational review of Amazon RDS instances and
Amazon Aurora clusters across **all five pillars of the
[AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)**.
Each pillar assesses both the AWS-managed configuration (control plane + CloudWatch)
**and** the database-internal (data-plane) state, so engine-level findings land in the
pillar they belong to rather than in a separate section.

Pillars covered (with their canonical references):
- **Reliability** — [Reliability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/welcome.html) · [High Availability for Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- **Security** — [Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html) · [Security in Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.html)
- **Operational Excellence** — [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html) · [Monitoring Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Monitoring.html)
- **Performance Efficiency** — [Performance Efficiency Pillar](https://docs.aws.amazon.com/wellarchitected/latest/performance-efficiency-pillar/welcome.html) · [Monitoring Amazon RDS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_Monitoring.html)
- **Cost Optimization** — [Cost Optimization Pillar](https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html) · [RDS Best Practices for Cost Optimization](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html#CHAP_BestPractices.Optimization)

This skill uses **AWS RDS, CloudWatch, CloudWatch Logs, EC2, KMS, IAM, Performance
Insights, Cost Explorer, and Application Auto Scaling APIs**. Database-internal
diagnostics are executed **via the AWS CLI RDS Data API**
(`aws rds-data execute-statement`, read-only). **No MCP server, Kubernetes, or other
external tools are required.**

## Running Database-Internal (Data-Plane) Checks

Engine-level state is collected through AWS APIs that need no database connection —
**CloudWatch Database Insights / Performance Insights, CloudWatch metrics & Logs, and
the parameter group** — and each pillar's data-plane subsection names the single source
per check. Only a small set of **catalog-only** checks (roles/grants, `pg_hba`, table
bloat, unused/redundant indexes, per-table sizes) have no such
API and require the RDS Data API:

```
aws rds-data execute-statement \
  --resource-arn <cluster-arn> \
  --secret-arn <secrets-manager-arn> \
  --database <db-name> \
  --sql "<read-only SELECT / SHOW>"
```

Source precedence (each check states its source; do not substitute a Data API query
where an API source is named):

1. **Database Insights / Performance Insights API** — DB load (`db.load.avg` vs vCPU),
   top wait events, top SQL, active sessions. (`pi:GetResourceMetrics`,
   `pi:DescribeDimensionKeys`.)
2. **CloudWatch metrics & Logs Insights** — CPU/mem/IOPS/latency, `DatabaseConnections`,
   `AuroraReplicaLag`/`ReplicaLag`, `BufferCacheHitRatio`, `EngineUptime`,
   `MaximumUsedTransactionIDs`, volume totals, and slow-query/error log patterns.
3. **Parameter group (Step 2b)** — every configuration parameter (anything otherwise
   read from `pg_settings` / `SHOW VARIABLES`). Never query the Data API for config.
4. **RDS Data API — catalog-only residuals** — only where no API/CloudWatch/parameter
   source exists (roles/grants, `pg_hba_file_rules`, table
   bloat, unused/redundant indexes, per-table sizes / `data_free`). These are flagged
   **RDS Data API (catalog-only)** in each pillar.

The Data API path requires the RDS Data API (Aurora Serverless v2 and supported Aurora
provisioned clusters) plus a Secrets Manager secret. If it is unavailable (standard RDS,
Data API disabled, or blocked in the Agent Space) — or blocked mid-review — mark **only
the catalog-only checks** as **NOT VERIFIED** and continue: the Database Insights,
CloudWatch, and parameter-group findings still populate every pillar. This never cancels
the report — the artifact is produced with its gaps clearly labelled (see Step 8a).

## When to Use

Activate this skill when the user asks to:
- Run a **full RDS/Aurora Well-Architected Review** across all five pillars.
- Run **any single pillar**:
  - **Reliability** — HA config, backups/recovery, Multi-AZ, replication, DR, version lifecycle, failover readiness.
  - **Security** — security posture, encryption at rest/in transit, network exposure, IAM auth, audit logging, compliance gaps.
  - **Operational Excellence** — monitoring/alerting, logging config, CloudWatch alarm coverage, maintenance/parameter groups, autovacuum/InnoDB maintenance, observability posture.
  - **Performance Efficiency** — metrics/trends, query & slow-query analysis, CPU/memory/IOPS/storage utilization, index health, connection management, latency/throughput, tuning parameters.
  - **Cost Optimization** — spend breakdown, right-sizing, RI/Savings Plans coverage, idle resources, storage/I/O optimization, Graviton migration, backup/snapshot costs.
- Run a **database-internal health check** (folded into the relevant pillar) — buffer pool/cache, connections, locks, active transactions, replication detail, storage, index efficiency, autovacuum, transaction-ID wraparound risk.

If the user asks for a specific pillar only, run that pillar's steps (including its
data-plane checks) and emit that pillar's section. If the user asks for a "full
review" / "WAR" / does not specify, run **all five pillars** and emit the full
combined report.

## Constraints

- If a tool call fails or data is unavailable, state that explicitly rather than estimating or fabricating values. Report only what you can verify.
- This skill operates in **read-only** mode — it never modifies resources, data, schema, or configuration. Never execute DDL/DML/DCL; never expose credentials. Database-internal checks are read-only `SELECT`/`SHOW` statements only.
- **Cost pillar specifics:**
  - When referring to Savings Plans, consider **Database Savings Plans** — distinct from Compute Savings Plans (which cover EC2/Fargate/Lambda, not databases).
  - Do NOT hardcode Database Savings Plans terms, payment options, coverage, or savings percentages — verify the current values from the authoritative docs referenced in [`references/cost-optimization-reference.md`](references/cost-optimization-reference.md) (these change over time and differ by service/engine/Region).
  - Savings percentages vary by instance type. Do NOT assume a flat percentage — look up actual savings for the specific instance type/Region.
  - All cost savings must be quantified with dollar amounts or percentages where data permits.
  - Scope cost analysis to the specific cluster/instance being reviewed.

---

## Workflow Checklist

Copy this checklist and tick each step as you complete it. Steps are ordered and each
depends on the previous one. Steps 3–7 are the pillars; run only the pillars in scope
(all five by default) and skip the rest, but always finish with Step 8.

```
- [ ] Step 1: Identify target resources (databases, regions, pillars in scope)
- [ ] Step 2: Discover RDS / Aurora resources, parameter groups (2b) and log exports (2c)
- [ ] Step 3: Reliability pillar (3a–3e)
- [ ] Step 4: Security pillar (4a–4e)
- [ ] Step 5: Operational Excellence pillar (5a–5f)
- [ ] Step 6: Performance Efficiency pillar (6a–6d)
- [ ] Step 7: Cost Optimization pillar (7a–7e)
- [ ] Step 8: Generate the combined WAR report (return scorecard + key findings in chat, save artifact, charts)
```

## Step 1: Identify Target Resources

Ask the user which databases to review, and which pillars (default: **all five pillars**). Accept:
- Specific instance / cluster identifiers and regions
- "all instances" / "all clusters" in specific regions
- Tag-based filters (e.g., `Environment=Production`)

If no scope is given, default to all configured account regions.

## Step 2: Discover RDS / Aurora Resources (all pillars)

Per region:
```
rds.DescribeDBInstances
rds.DescribeDBClusters
rds.DescribeDBClusterEndpoints
rds.DescribeGlobalClusters          # Aurora Global Database (cross-region DR)
```

Capture the union of attributes needed by every pillar:

**Reliability / HA:**
- MultiAZ status, AvailabilityZones
- BackupRetentionPeriod, PreferredBackupWindow
- DeletionProtection, AutoMinorVersionUpgrade
- ReadReplicaSourceDBInstanceIdentifier / ReadReplicaDBInstanceIdentifiers
- DBSubnetGroup (AZ spread)

**Security:**
- StorageEncrypted, KmsKeyId
- PubliclyAccessible, VpcSecurityGroupIds
- IAMDatabaseAuthenticationEnabled
- EnabledCloudwatchLogsExports

**Operational Excellence:**
- DatabaseInsightsMode (`standard` / `advanced`), PerformanceInsightsEnabled, PerformanceInsightsRetentionPeriod
- MonitoringInterval (Enhanced Monitoring), MonitoringRoleArn
- PreferredMaintenanceWindow
- DBParameterGroupName / DBClusterParameterGroupName

**Performance:**
- DBInstanceClass, StorageType, Iops, StorageThroughput, AllocatedStorage

**Cost:**
- DBInstanceStatus, MaxAllocatedStorage
- Serverless v2 ACU configuration (MinCapacity, MaxCapacity)

**Common:** Engine, EngineVersion, Tags
(`rds.ListTagsForResource` — param is `ResourceName`, value is the resource ARN;
capture `Environment`, `Owner`, `Runbook`, `OnCall`, `CostCenter`, `Application`, `Project`).

### Step 2b: Read parameter group configuration (control plane — always)
Parameter values MUST be read even when the RDS Data API is unavailable. Do NOT rely
only on `pg_settings` / `SHOW VARIABLES` (data plane). For every resource, read the
**actual configured parameter values** from its parameter group via the control plane:
```
rds.DescribeDBParameters               --db-parameter-group-name <instance group>
rds.DescribeDBClusterParameters        --db-cluster-parameter-group-name <cluster group>
rds.DescribeDBParameterGroups / rds.DescribeDBClusterParameterGroups   # confirm custom vs default.*
```
**Always source these configuration parameters from the parameter group (control
plane) — do NOT use the RDS Data API for them.** Any parameter whose value can be read
from the parameter group MUST be read from there via
`rds.DescribeDBParameters` / `rds.DescribeDBClusterParameters`, regardless of whether
the Data API is reachable. The Data API is reserved only for catalog-only data that has
no CloudWatch / Database Insights / parameter-group equivalent (roles/grants,
`pg_hba_file_rules`, autovacuum effectiveness, table bloat, unused/redundant indexes,
per-object sizes). Runtime state — session activity, replication lag, buffer/cache hit,
top queries, transaction-ID/transaction-age signals — comes from Database Insights /
CloudWatch (see each pillar's data-plane subsection), NOT the Data API. Extract and
carry these parameter-group values into the pillar sections:
Parameters to extract per engine (PostgreSQL and MySQL/MariaDB lists): read [`references/parameter-lists.md`](references/parameter-lists.md) → "Step 2b parameters to extract".
- **Also record:** whether the group is custom or a `default.*` group, and any parameters with `ApplyType=static` that are pending a reboot.

### Step 2c: Confirm engine-log exports & log groups (always)
For every resource, capture `EnabledCloudwatchLogsExports` and enumerate the actual log
groups (`logs.DescribeLogGroups` under `/aws/rds/instance/<name>/` and
`/aws/rds/cluster/<name>/`), plus each group's **retention** (`retentionInDays`; flag
"never expires"). This feeds the per-engine Audit Logging / Log Retention tables.

---

## Step 3: Reliability Pillar

### 3a. Backup & maintenance data
```
rds.DescribeDBSnapshots                    # manual + automated snapshots
rds.DescribeDBClusterSnapshots             # Aurora cluster snapshots
rds.DescribeDBInstanceAutomatedBackups
rds.DescribeDBClusterAutomatedBackups
rds.DescribeDBEngineVersions               # current vs latest minor/major
rds.DescribePendingMaintenanceActions
rds.DescribeEvents                         # last 14 days (Duration=20160 minutes)
rds.DescribeEventSubscriptions
```

### 3b. CloudWatch metrics (15-day window, `Period=21600` / 6h)
Metrics to retrieve (RDS instances and Aurora clusters): [`references/metric-lists.md`](references/metric-lists.md) → "Step 3b metrics".

### 3c. Version lifecycle assessment
- Check current engine version against the AWS RDS/Aurora release calendar.
- Determine standard support end date, extended support start date; flag versions approaching/past end of standard support; identify extended support charges.
- Use `rds.DescribeDBEngineVersions` to compare current vs latest available.

### 3d. Reliability best-practice checks
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Reliability best-practice checks (Step 3d)" before evaluating this step.

Full checklist: [`references/reliability-checklist.md`](references/reliability-checklist.md).

> Record **every** matched check (any severity, per resource) as a row in the
> Reliability Findings table — see the completeness contract in Step 8c-bis.

### 3e. Database-internal checks (Database Insights / CloudWatch; parameter group; Data API only for catalog-only residuals)
Each check names its source. Prefer the stated source exactly; only the checks marked
**RDS Data API (catalog-only)** need `rds-data execute-statement`, and those are marked
**NOT VERIFIED** if the Data API is unavailable.

Per-engine check list (PostgreSQL and MySQL/Aurora MySQL, with each check's source): read [`references/database-internal-checks.md`](references/database-internal-checks.md) → "Reliability database-internal checks (Step 3e)" and run every check listed.

---

## Step 4: Security Pillar

### 4a. Security configuration
```
ec2.DescribeSecurityGroups    # ingress/egress rules for VPC security groups
kms.DescribeKey               # encryption key details (CMK vs AWS-managed)
kms.ListAliases               # key alias for readability
```

### 4b. Audit logging
Check `EnabledCloudwatchLogsExports` against expected log types:

**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Expected audit log exports by engine (Step 4b)" before evaluating this step.

```
logs.DescribeLogGroups  # prefix: /aws/rds/instance/<name>/ or /aws/rds/cluster/<name>/
```

### 4c. Log-event security patterns (`logs.FilterLogEvents`, 7-day window)
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Security log-event patterns (Step 4c)" before evaluating this step.

Record occurrence counts per pattern.

### 4d. Security best-practice checks
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Security best-practice checks (Step 4d)" before evaluating this step.

Full checklist and compliance mapping (PCI-DSS, HIPAA, SOC 2, GDPR): [`references/security-checklist.md`](references/security-checklist.md).

> Record **every** matched check (any severity, per resource) as a row in the
> Security Findings table — see the completeness contract in Step 8c-bis.

### 4e. Database-internal checks (parameter group for config; Data API only for catalog-only residuals)
Security data-plane checks split into config (read from the parameter group, Step 2b —
no Data API) and catalog-only checks (RDS Data API; **NOT VERIFIED** if unavailable).
There is no Database Insights equivalent for these.

Per-engine check list (PostgreSQL and MySQL/Aurora MySQL, with each check's source): read [`references/database-internal-checks.md`](references/database-internal-checks.md) → "Security database-internal checks (Step 4e)" and run every check listed.

---

## Step 5: Operational Excellence Pillar

### 5a. Monitoring & alerting
Use `cloudwatch.DescribeAlarmsForMetric` for each resource:

**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Expected CloudWatch alarm thresholds (Step 5a)" before evaluating this step.

```
rds.DescribeEventSubscriptions   # verify resource is covered
```

### 5b. Logging configuration
Logging parameters to read from the parameter group (PostgreSQL and MySQL): [`references/parameter-lists.md`](references/parameter-lists.md) → "Step 5b logging parameters".
Verify expected log exports (same engine matrix as Step 4b) and log groups.

### 5c. Log-event operational patterns (`logs.FilterLogEvents`, 7-day window)
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Operational log-event patterns (Step 5c)" before evaluating this step.

#### CloudWatch Logs Insights example queries (deeper analysis)
Example queries (MySQL slow-query, PostgreSQL duration, error rate, deadlocks, connection/auth failures): read [`references/check-tables.md`](references/check-tables.md) → "CloudWatch Logs Insights example queries (Step 5c)". Run against the resource's log groups via `logs:StartQuery` / `logs:GetQueryResults`, 7-day range.

Cross-reference spikes with the CloudWatch metrics at the same timestamp (CPU, IOPS,
connections) to confirm cause.

### 5d. Maintenance configuration
**PostgreSQL autovacuum (parameter group):** `autovacuum`, `autovacuum_max_workers`, `autovacuum_naptime`, `autovacuum_vacuum_threshold`, `autovacuum_vacuum_scale_factor`, `autovacuum_analyze_threshold`, `autovacuum_analyze_scale_factor`, `autovacuum_vacuum_cost_delay`, `autovacuum_vacuum_cost_limit`. Effectiveness (tables with old `last_autovacuum`) is catalog-only — see 5f. Instance-level wraparound risk is the CloudWatch `MaximumUsedTransactionIDs` metric (Reliability 3b/3e).
**MySQL InnoDB (parameter group):** `innodb_stats_auto_recalc`, `innodb_stats_persistent`; event scheduler status.
**Engine version currency:** `rds.DescribeDBEngineVersions` (minor not latest → LOW; major EOL/within 6 months → HIGH).

### 5e. Operational Excellence best-practice checks
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Operational Excellence best-practice checks (Step 5e)" before evaluating this step.

Full checklist: [`references/ops-excellence-checklist.md`](references/ops-excellence-checklist.md).

> Record **every** matched check (any severity, per resource) as a row in the
> Operational Excellence Findings table — see the completeness contract in Step 8c-bis.

### 5f. Database-internal checks (CloudWatch for context; parameter group for config; Data API only for catalog-only residuals)
Context/uptime from CloudWatch, all configuration from the parameter group (Step 2b),
and only autovacuum effectiveness needs the RDS Data API (**NOT VERIFIED** if
unavailable).

Per-engine check list (PostgreSQL and MySQL/Aurora MySQL, with each check's source): read [`references/database-internal-checks.md`](references/database-internal-checks.md) → "Operational Excellence database-internal checks (Step 5f)" and run every check listed.

---

## Step 6: Performance Efficiency Pillar

### 6a. CloudWatch metrics (15-day window, `Period=21600` / 6h)
Metrics to retrieve (RDS instances and Aurora clusters): [`references/metric-lists.md`](references/metric-lists.md) → "Step 6a metrics".

### 6b. Database Insights — DB load analysis (if enabled)
Use **Amazon CloudWatch Database Insights** for database load (DB Load) analysis
(Standard mode by default; Advanced mode adds execution plans, lock/query analysis,
and on-demand analysis). Programmatically retrieve DB-load data via the Performance
Insights API (the metrics interface Database Insights is built on):
```
pi.GetResourceMetrics     # db.load.avg vs vCPU count
pi.DescribeDimensionKeys  # top wait events by category, top SQL by DB load
```
Focus on: DB load vs vCPU (overloaded if load > vCPU sustained), top wait events (CPU/IO/Lock/Network), top SQL by average active sessions, queries with high db.load or frequent I/O waits. Note: standalone Performance Insights reaches EOL 2026-06-30 — prefer Database Insights (Advanced mode) going forward. See the Observability Stack references in [`references/ops-excellence-checklist.md`](references/ops-excellence-checklist.md).

### 6c. Database-internal checks (Database Insights / CloudWatch; parameter group for config; Data API only for catalog-only residuals)
Load, activity, top SQL and cache come from Database Insights / CloudWatch;
configuration from the parameter group (Step 2b); only bloat, per-table sizes, and
index inventory need the RDS Data API (**NOT VERIFIED** if unavailable).

Per-engine check list (PostgreSQL and MySQL/Aurora MySQL, with each check's source): read [`references/database-internal-checks.md`](references/database-internal-checks.md) → "Performance Efficiency database-internal checks (Step 6c)" and run every check listed.

Compare parameter-group baselines against [`references/performance-metrics-thresholds.md`](references/performance-metrics-thresholds.md)
sizing guidance.

### 6d. Performance thresholds
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Performance thresholds (Step 6d)" before evaluating this step.

Full thresholds & config baselines: [`references/performance-metrics-thresholds.md`](references/performance-metrics-thresholds.md).

> Record **every** threshold breach or check result (any severity, per resource) as a
> row in the Performance Findings table — see the completeness contract in Step 8c-bis.

---

## Step 7: Cost Optimization Pillar

### 7a. Cost Explorer data
```
costexplorer.GetCostAndUsage
  # Last 2 months, GroupBy: USAGE_TYPE
  # Filter: Service = "Amazon Relational Database Service"
```
Relevant usage types: [`references/cost-usage-types.md`](references/cost-usage-types.md).

**Commitment coverage:**
```
costexplorer.GetReservationCoverage     # RI coverage
costexplorer.GetSavingsPlansCoverage    # SP coverage
rds.DescribeReservedDBInstances         # RI inventory
```
Check for expiring RIs or underutilized Savings Plans.

### 7b. CloudWatch metrics (15-day window)
Metrics to retrieve: [`references/metric-lists.md`](references/metric-lists.md) → "Step 7b metrics".

### 7c. I/O cost optimization
1. Get ACTUAL monthly Read/Write I/O counts from Cost Explorer or CloudWatch.
2. Determine current storage tier (`standard` vs `aurora-iopt1`).
3. Look up actual I/O pricing for the engine and region.
- **Standard storage:** if I/O cost > 25% of total RDS cost → recommend I/O-Optimized (show cost comparison).
- **I/O-Optimized (`aurora-iopt1`):** if equivalent standard I/O would be < 25% of total → recommend switching back.

### 7d. Cost Optimization best-practice checks
**Table:** read [`references/check-tables.md`](references/check-tables.md) → "Cost Optimization best-practice checks (Step 7d)" before evaluating this step.

Full reference (instance-gen/storage comparison, Savings Plans details, right-sizing, backup cost): [`references/cost-optimization-reference.md`](references/cost-optimization-reference.md).

> Record **every** matched check (any severity, per resource) as a row in the Cost
> Findings table, each with its cost impact / potential savings — see the completeness
> contract in Step 8c-bis.

### 7e. Database-internal checks (CloudWatch / Database Insights only — no Data API)
- **Idle-database confirmation** — **CloudWatch + Database Insights only:** `DatabaseConnections` (max < 5) + `CPUUtilization` (avg < 5%) over 7 days, corroborated by DBI near-zero active sessions → supports stop/downsize/remove.
- **Over-sized capacity signals** — **CloudWatch only:** low `CPUUtilization`/`DatabaseConnections`/`ServerlessDatabaseCapacity` vs class/ACU ceiling → right-size or reduce Serverless v2 min ACU.
- **Storage growth & reclaim signal** — **CloudWatch only:** volume totals and trend from `VolumeBytesUsed` / `FreeStorageSpace` (and `AuroraVolumeBytesLeftTotal` where applicable) → project growth and flag reclaim/archiving candidates at the instance/cluster level. Note Aurora storage does not auto-shrink.

---

## Step 8: Generate the Combined WAR Report

### 8a. Deliver the report in chat AND save it as an artifact (both mandatory)
You MUST do both, in the same turn:
1. **Save** the full markdown report to an artifact (details below).
2. **Return in the chat response** the overall scorecard (score per pillar in scope),
   the key findings for each pillar (at least every CRITICAL/HIGH finding, naming the
   affected resource), the top prioritized recommendations, any checks marked
   **NOT VERIFIED**, and the saved artifact path(s).

Run the checks yourself and finish the review within this turn. Do NOT hand the review
off to background or asynchronous tasks, and do NOT reply with a status message such as
"the review is running, I'll send results when it finishes" — the user's reply must
contain the findings.

**The artifact is ALWAYS produced — partial or blocked data never suppresses it.**
If the RDS Data API is blocked/unavailable mid-review (or any tool call fails) and a
large portion of the data-plane checklist (e.g. transaction-ID wraparound, autovacuum
effectiveness, roles/grants, TLS/auth catalog state, query tuning) cannot be run, you
MUST STILL create the report with everything you did verify (control plane + CloudWatch
+ parameter-group config), and explicitly mark every unrun check as **NOT VERIFIED**.
Do NOT refuse to emit the artifact, do NOT withhold it, and do NOT silently omit the
missing checks. A report that is transparent about its gaps is required; a polished
report that looks complete but silently hides missing evidence is NOT acceptable.
- Record each unrun/failed check under **Scope Covered → checks skipped and why**
  (e.g. "RDS Data API blocked — data-plane checks NOT VERIFIED"), and mark its row in
  the relevant pillar Findings table as `NOT VERIFIED` rather than dropping it.
- Note in each affected pillar's score **Rationale** that the score reflects reduced
  evidence, and list the intended catalog/view checks the user can run manually.
- The reconciliation check in Step 8c-bis still applies: `NOT VERIFIED` items are
  counted and shown, not removed.

- **Single resource:** name it `rds-well-architected-review-review-<resource-name>-<YYYY-MM-DD>.md`.
- **Multiple resources / whole account (fleet review):** produce **one consolidated
  report** covering all in-scope resources named
  `rds-well-architected-review-<scope-label>-<YYYY-MM-DD>.md` (e.g. `AllClusters`), with per-cluster
  comparison tables in each pillar (one column per resource) — do NOT emit a separate
  file per cluster. This matches the fleet health-check format.

Also generate the PNG charts described in 8e and save them alongside the report
(referenced from the markdown), so the deliverable includes the same visual output the
individual pillar skills' runs produce. Use the available file-writing / plotting
capability to create these files (e.g., write to the working directory / artifacts
location), then confirm every saved path (the `.md` and each `.png`) to the user.
The saved `.md` report plus its `.png` charts is the complete deliverable; the chat
response carries the scorecard and key findings per pillar described in step 2 above.

**Format adaptivity:** the `.md` + `.png` deliverable above is the default (and the
format for file-artifact runtimes like AWS DevOps Agent). On a runtime that composes
**structured artifacts** instead of files, render the equivalent native elements
(`text` for narrative, `data_table` for every table, `chart` for the visualizations) in
the same order — do NOT force a markdown file if the runtime doesn't support one. Either
way, preserve the section order in [`references/report-structure.md`](references/report-structure.md), every table and
finding, and the 8c-bis reconciliation. See "Format adaptivity" in
[`references/report-structure.md`](references/report-structure.md).

### 8b. Scoring is mandatory and per-pillar
Every pillar section MUST end with its own score line in the exact form used by the
source pillar skills, followed by a rationale that cites specific evidence:
```
### <Pillar> Pillar Score: X/100
Rationale: <cite specific metric values / config / catalog results / dollar amounts>
```
- Produce a score for **each pillar reviewed** (all five for a full WAR; the single
  pillar for a single-pillar request) — never omit a pillar's score.
- The **Executive Summary pillar scorecard MUST list the numeric score for every
  pillar** (no blank/`X` placeholders in the actual output) and stay consistent with
  each pillar's own score line.
- Compute the **Overall Health Score** as a **weighted average** of the pillar scores
  and state the methodology. Default weights (match the fleet health-check report):
  Performance Efficiency 25%, Security 20%, Reliability 20%, Cost Optimization 20%,
  Operational Excellence 15%. Show the per-pillar weight, score, and weighted
  contribution. For a fleet review, each pillar score is the average across all
  in-scope resources (note when a resource is config-only, e.g. zero instances / no
  metrics).
- Map each score to a status band: **✅ ≥ 80 Good**, **⚠️ 50–79 Needs Work**,
  **❌ < 50 Poor** (reflect the same in the pillar's HEALTHY/WARNINGS/CRITICAL header).
  State scores are qualitative assessments informed by evidence, not algorithmic.
- For a **fleet review**, also emit a **Per-Cluster Health Summary** (per-resource
  score + one-line verdict) and per-cluster comparison columns in each pillar's tables.
- Do not emit a report that is missing any required pillar section, its findings
  table, or its score line.

### 8c. Follow the defined format
The report MUST follow the structure in 8d **exactly** — same section order, headings,
and tables inherited from the individual pillar skills. Each pillar section includes
both the AWS-managed findings and the database-internal (data-plane) findings for that
pillar. Cite specific evidence (metric values, config, catalog/view results, dollar
amounts) in every finding. For a full review, emit **all five pillar sections**; for a
single-pillar request, emit that pillar's section only. Replace every `<placeholder>`
and `X`/`Y` token with real values — never leave template placeholders in the output.

### 8c-bis. Findings completeness — nothing is dropped (mandatory)
**Every finding produced by any pillar's checks and instructions MUST appear in the
final report.** The report is the complete record of the review, not a curated subset.

- **Full coverage of every check.** For each pillar, walk its entire check list and
  data-plane checks (Reliability 3d/3e, Security 4d/4e, Operational Excellence 5e/5f,
  Performance 6d + 6a–6c, Cost 7d/7e) and the pillar's `references/*checklist`. Any
  check whose condition is met becomes a finding row in that pillar's Findings table.
- **Every severity is included** — CRITICAL, HIGH, MEDIUM, **and LOW/INFO**. Do not
  drop or silently roll up LOW/INFO. (LOW/INFO may be listed compactly, but each must
  still appear with its resource, check, severity, and evidence.)
- **Per-resource.** In a fleet review, a finding that applies to N resources is
  recorded for each affected resource (or one row that names every affected resource) —
  never collapsed to "some clusters".
- **Evidence required, never invented.** Each finding cites the observed value
  (metric, config/parameter value, catalog result, log pattern, or $ amount). If a
  check could not be run (e.g., RDS Data API unreachable, Performance Insights/Database
  Insights disabled, log exports off), record it under **Scope Covered → checks
  skipped and why** — do NOT omit it silently.
- **No finding without a home.** Every finding lands in exactly one pillar's Findings
  table AND is reflected in the **Consolidated Findings** table (ranked by severity)
  and in the pillar's severity counts / score rationale. The Executive Summary severity
  counts MUST equal the total rows across the five pillar Findings tables.
- **Reconciliation check before saving.** Confirm: (finding counts by severity in the
  Executive Summary) == (rows in Consolidated Findings) == (sum of rows in the five
  pillar Findings tables). If they don't match, fix the report before writing the
  artifact.
- Findings feed the **Implementation Roadmap**; every CRITICAL/HIGH finding must map to
  a roadmap item (or be explicitly noted as accepted risk).

### 8d. Report structure (follow the reference — mandatory)
Before writing the report, you MUST open **[`references/report-structure.md`](references/report-structure.md)** and
follow it **exactly** — same section order, headings, and tables. It is the
authoritative layout for the consolidated report: title/header, Executive Summary
(Overview, Resources in Scope, weighted Overall Health Score, Per-Cluster Health
Summary, Critical Findings, Top Cost Savings), Scope Covered, the five pillar sections
(each reproducing its source skill's full tables, Findings, Recommendations, and
`<Pillar> Pillar Score`), Consolidated Findings, Consolidated Recommendations, Overall
WAR Score, Implementation Roadmap, Appendix, and the PNG chart references. Do not
improvise the layout or drop any section or table.

The behavioral contracts in 8a (artifact saving), 8b (scoring + weighted methodology),
and 8c-bis (findings completeness + reconciliation) still apply and are not repeated in
the reference.

### 8e. Visualizations (PNG charts)
Produce the PNG charts described in the "Visualizations" section of
[`references/report-structure.md`](references/report-structure.md) (overall scorecard + findings-by-severity, and the
per-pillar metric/coverage/spend charts), save them alongside the report, embed each
with a markdown image link in the pillar section it belongs to, and list every `.png`
under the report's **Artifacts** line. Charts supplement — never replace — the detail
tables; if the plotting library or data is unavailable, note it in Scope Covered.

## Severity Definitions

Applies to all pillars. Where a pillar-specific nuance exists it is noted; the SLAs
are common.

Severity levels (CRITICAL / HIGH / MEDIUM / LOW / INFO), definitions and SLAs: [`references/severity-definitions.md`](references/severity-definitions.md). Use them consistently when scoring and ranking findings in Step 8.

## References

- [`references/reliability-checklist.md`](references/reliability-checklist.md) — Reliability pillar best-practices checklist
- [`references/security-checklist.md`](references/security-checklist.md) — Security pillar checklist + compliance mapping
- [`references/ops-excellence-checklist.md`](references/ops-excellence-checklist.md) — Operational Excellence checklist
- [`references/performance-metrics-thresholds.md`](references/performance-metrics-thresholds.md) — Performance metrics thresholds & config baselines
- [`references/cost-optimization-reference.md`](references/cost-optimization-reference.md) — Cost optimization reference tables
- [`references/database-internal-checks.md`](references/database-internal-checks.md) — per-engine database-internal check lists for Steps 3e, 4e and 5f
- [`references/parameter-lists.md`](references/parameter-lists.md) — parameter-group parameters to extract (Steps 2b, 5b)
- [`references/metric-lists.md`](references/metric-lists.md) — CloudWatch metrics per step (3b, 6a, 7b)
- [`references/cost-usage-types.md`](references/cost-usage-types.md) — Cost Explorer usage types (Step 7a)
- [`references/severity-definitions.md`](references/severity-definitions.md) — severity levels and SLAs
- [`references/check-tables.md`](references/check-tables.md) — best-practice check tables, alarm/log-pattern/performance thresholds, Logs Insights queries
- [`references/report-structure.md`](references/report-structure.md) — **authoritative combined report template** (Step 8 output) + PNG chart catalog

Database-internal (data-plane) checks are described inline within each pillar, each
naming its source — Database Insights / CloudWatch, parameter group, or (for a few
catalog-only residuals) the read-only RDS Data API. No separate data-plane reference
file or MCP server is used.
