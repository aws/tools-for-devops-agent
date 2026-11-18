---
name: rds-war
description: >-
  Well-Architected Review (WAR) for Amazon RDS and Aurora across all five pillars —
  Reliability, Security, Operational Excellence, Performance Efficiency, and Cost
  Optimization. Each pillar combines AWS control-plane, CloudWatch, and CloudWatch
  Database Insights checks with parameter-group configuration; a few catalog-only
  checks use the read-only RDS Data API where no API source exists. Use for a full
  RDS/Aurora WAR, a multi-pillar assessment, or any single-pillar review (HA/backup/DR;
  security/encryption/network; monitoring/logging/alarms; performance/query/index
  tuning; cost/right-sizing/RI-SP), and for database-internal health checks (buffer
  pool, connections, locks, replication, storage, index efficiency, autovacuum,
  transaction-ID wraparound). Triggers on "RDS Well-Architected Review", "RDS WAR",
  "Aurora WAR", "database HA/DR audit", "RDS security review", "RDS ops excellence
  check", "RDS performance review", "RDS cost optimization", "check RDS buffer pool /
  locks / connections".
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
  - Do NOT hardcode Database Savings Plans terms, payment options, coverage, or savings percentages — verify the current values from the authoritative docs referenced in `references/cost-optimization-reference.md` (these change over time and differ by service/engine/Region).
  - Savings percentages vary by instance type. Do NOT assume a flat percentage — look up actual savings for the specific instance type/Region.
  - All cost savings must be quantified with dollar amounts or percentages where data permits.
  - Scope cost analysis to the specific cluster/instance being reviewed.

---

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
- **PostgreSQL:** `rds.force_ssl`, `ssl_min_protocol_version`, `password_encryption`, `log_connections`, `log_disconnections`, `log_checkpoints`, `log_statement`, `log_min_duration_statement`, `log_autovacuum_min_duration`, `shared_preload_libraries` (pg_stat_statements/pgaudit/auto_explain), the `autovacuum*` family, `max_connections`, memory/planner params (`shared_buffers`, `work_mem`, `effective_cache_size`).
- **MySQL/MariaDB:** `require_secure_transport`, `slow_query_log`, `long_query_time`, `general_log`, `log_output`, `innodb_print_all_deadlocks`, `innodb_buffer_pool_size`, `max_connections`, `innodb_flush_log_at_trx_commit`, audit plugin params.
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
**RDS Instances** (dim `DBInstanceIdentifier`): DatabaseConnections (Max), FreeStorageSpace (Min), ReplicaLag (Max), MaximumUsedTransactionIDs (Maximum — PostgreSQL XID wraparound signal).
**Aurora Clusters** (dim `DBClusterIdentifier`): AuroraReplicaLag (Max), DatabaseConnections (Max), Deadlocks (Sum), EngineUptime (Min), MaximumUsedTransactionIDs (Maximum — Aurora PostgreSQL), TransactionAgeMaximum (Maximum — oldest active transaction age, Aurora MySQL 3.08+) and/or RollbackSegmentHistoryListLength (Maximum — InnoDB purge backlog, Aurora MySQL).

### 3c. Version lifecycle assessment
- Check current engine version against the AWS RDS/Aurora release calendar.
- Determine standard support end date, extended support start date; flag versions approaching/past end of standard support; identify extended support charges.
- Use `rds.DescribeDBEngineVersions` to compare current vs latest available.

### 3d. Reliability best-practice checks
| Check | Condition | Severity |
|-------|-----------|----------|
| Multi-AZ (production) | Single-AZ production instance | HIGH |
| Aurora readers | Cluster with no reader in different AZ | MEDIUM |
| Backup retention | `BackupRetentionPeriod=0` | CRITICAL |
| Backup retention | < 7 days for production | HIGH |
| Deletion protection | Production with `DeletionProtection=false` | HIGH |
| Subnet AZ spread | Subnets span < 2 AZs | HIGH |
| Auto minor upgrade | `AutoMinorVersionUpgrade=false` (non-prod) | MEDIUM |
| Custom parameter group | Using `default.*` parameter group | MEDIUM |
| Pending maintenance | Required actions not applied within window | MEDIUM |
| Replication lag | `ReplicaLag` 7-day max > 30s | HIGH |
| Replication lag | `ReplicaLag` 7-day max > 300s | CRITICAL |
| Cross-region DR | No cross-region replica or Global DB for tier-1 | MEDIUM |
| Engine version | Major version within 6 months of EOL | HIGH |
| Engine version | Minor version not latest | LOW |
| Transaction ID wraparound | Database age > 1 billion transactions remaining | HIGH |
| Connection capacity | `max_connections` utilization > 80% | HIGH |

Full checklist: `references/reliability-checklist.md`.

> Record **every** matched check (any severity, per resource) as a row in the
> Reliability Findings table — see the completeness contract in Step 8c-bis.

### 3e. Database-internal checks (Database Insights / CloudWatch; parameter group; Data API only for catalog-only residuals)
Each check names its source. Prefer the stated source exactly; only the checks marked
**RDS Data API (catalog-only)** need `rds-data execute-statement`, and those are marked
**NOT VERIFIED** if the Data API is unavailable.

**PostgreSQL:**
- **Connection capacity** — **CloudWatch only:** `DatabaseConnections` vs `max_connections` (from the parameter group, Step 2b). Look for utilization > 80%. Active/idle-in-transaction session mix comes from **Database Insights** active sessions.
- **Replication health** — **CloudWatch only:** `AuroraReplicaLag` (Aurora) / `ReplicaLag` (RDS) per reader (dim `DBInstanceIdentifier`); look for lag growing or a replica not streaming.
- **Transaction ID wraparound** — **CloudWatch only:** `MaximumUsedTransactionIDs` (namespace `AWS/RDS`, dimension `DBInstanceIdentifier`). This is a **per-instance** metric that already reports the maximum transaction-ID age across all databases on the instance — the correct, sufficient wraparound signal (risk is instance-level; the engine shuts down near 2^31). Warn > 1B, critical > 1.5B. No per-database query is needed.
- **Autovacuum keeping frozen xids in check** — **RDS Data API (catalog-only):** `pg_stat_user_tables` `last_autovacuum` and dead-vs-live tuples for aged tables. No DBI/CloudWatch equivalent — mark **NOT VERIFIED** if the Data API is unavailable.

**MySQL / Aurora MySQL:**
- **Connection capacity** — **CloudWatch only:** `DatabaseConnections` vs `max_connections` (parameter group); look for utilization > 80%. Active sessions from **Database Insights**.
- **Aurora replica lag** — **CloudWatch only:** `AuroraReplicaLag` per reader (dim `DBInstanceIdentifier`); warn > 100 ms, critical > 1000 ms.
- **Long-running transactions** — **Database Insights + CloudWatch only:** long-running statements / active sessions from DBI top-SQL, corroborated by `TransactionAgeMaximum` / `RollbackSegmentHistoryListLength`. This is the actionable signal (a long transaction blocking purge / extending failover); exact locked-row counts are not needed.
- **Transaction age / purge backlog** — **CloudWatch only:** `TransactionAgeMaximum` (oldest active transaction age, Aurora MySQL 3.08+) and `RollbackSegmentHistoryListLength` (InnoDB undo/purge backlog). InnoDB has no PostgreSQL-style XID wraparound; a rising oldest-transaction age / HLL indicates purge is blocked by long transactions (bloat, replica lag, storage growth). Alarm on sustained growth.

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

| Engine | Expected Log Exports |
|--------|---------------------|
| PostgreSQL | `postgresql` (error/slow), `upgrade` |
| MySQL/MariaDB | `audit`, `error`, `general`, `slowquery` |
| Oracle | `alert`, `audit`, `listener`, `trace` |
| SQL Server | `agent`, `error` |

```
logs.DescribeLogGroups  # prefix: /aws/rds/instance/<name>/ or /aws/rds/cluster/<name>/
```

### 4c. Log-event security patterns (`logs.FilterLogEvents`, 7-day window)
| Pattern | Indicates |
|---------|-----------|
| `authentication failed` | Credential issues or brute-force attempts |
| `password authentication failed` | Failed login attempts |
| `connection refused` | Network/access issues |
| `SSL connection required` | Non-SSL connection attempts |
| `permission denied` | Unauthorized access attempts |

Record occurrence counts per pattern.

### 4d. Security best-practice checks
| Check | Condition | Severity |
|-------|-----------|----------|
| Public access | `PubliclyAccessible=true` | CRITICAL |
| Open security groups | `0.0.0.0/0` ingress on DB port | CRITICAL |
| Encryption at rest | `StorageEncrypted=false` | HIGH |
| Encryption in transit | `rds.force_ssl` / `require_secure_transport` not enabled | MEDIUM |
| IAM authentication | `IAMDatabaseAuthenticationEnabled=false` | MEDIUM |
| Audit logging | Engine audit logs not in `EnabledCloudwatchLogsExports` | MEDIUM |
| KMS key type | AWS-managed key instead of CMK | LOW |
| CMK rotation | KMS key without automatic rotation | LOW |
| Secrets Manager | Master password not managed by Secrets Manager | MEDIUM |
| Password encryption | Using MD5 instead of SCRAM-SHA-256 (PostgreSQL) | MEDIUM |

Full checklist and compliance mapping (PCI-DSS, HIPAA, SOC 2, GDPR): `references/security-checklist.md`.

> Record **every** matched check (any severity, per resource) as a row in the
> Security Findings table — see the completeness contract in Step 8c-bis.

### 4e. Database-internal checks (parameter group for config; Data API only for catalog-only residuals)
Security data-plane checks split into config (read from the parameter group, Step 2b —
no Data API) and catalog-only checks (RDS Data API; **NOT VERIFIED** if unavailable).
There is no Database Insights equivalent for these.

**PostgreSQL:**
- **TLS / encryption in transit** — **parameter group:** `ssl`, `ssl_min_protocol_version`, `ssl_max_protocol_version`, `ssl_ciphers`, `rds.force_ssl`; flag SSL off, TLS < 1.2, weak ciphers.
- **Password storage** — **parameter group:** `password_encryption`; flag `md5` (should be `scram-sha-256`).
- **Security logging** — **parameter group:** `log_connections`, `log_disconnections`, `log_statement`; confirm `pgaudit` in `shared_preload_libraries`.
- **Roles & privileges** — **RDS Data API (catalog-only):** `pg_roles`; flag app roles with `rolsuper`/`rds_superuser`, `CREATEROLE`/`CREATEDB`, or broad membership.
- **Authentication rules** — **RDS Data API (catalog-only):** `pg_hba_file_rules`; flag `trust`/`password` methods or overly broad address rules.

**MySQL / Aurora MySQL:**
- **TLS enforcement** — **parameter group:** `require_secure_transport` (should be `ON`).
- **Audit plugin** — **parameter group:** audit plugin params.
- **Users & privileges** — **RDS Data API (catalog-only):** `mysql.user` accounts/grants; flag `%` host wildcards, `SUPER`/`ALL PRIVILEGES`, weak auth.

---

## Step 5: Operational Excellence Pillar

### 5a. Monitoring & alerting
Use `cloudwatch.DescribeAlarmsForMetric` for each resource:

| Metric | Expected Alarm Threshold |
|--------|-------------------------|
| CPUUtilization | > 80% for 5 minutes |
| FreeStorageSpace | < 10% allocated |
| FreeableMemory | < 256 MB or < 10% of class |
| DatabaseConnections | > 80% of `max_connections` |
| ReadLatency / WriteLatency | > 20 ms |
| ReplicaLag (read replicas) | > 60 s |
| AuroraReplicaLag (Aurora) | > 100 ms |
| BufferCacheHitRatio (Aurora) | < 95% |
| Deadlocks | > 0 sustained |

```
rds.DescribeEventSubscriptions   # verify resource is covered
```

### 5b. Logging configuration
**PostgreSQL** — from the **parameter group** (Step 2b): `log_connections`, `log_disconnections`, `log_checkpoints`, `log_statement`, `log_min_duration_statement`, `log_temp_files`, `log_autovacuum_min_duration`; `shared_preload_libraries` (verify `pg_stat_statements`, `auto_explain`).
**MySQL** — from the **parameter group**: `general_log`, `slow_query_log`, `log_output`, `long_query_time`, audit plugin status.
Verify expected log exports (same engine matrix as Step 4b) and log groups.

### 5c. Log-event operational patterns (`logs.FilterLogEvents`, 7-day window)
| Pattern | Indicates |
|---------|-----------|
| `ERROR` / `FATAL` | Engine errors |
| `Out of memory` / `OOM` | Memory pressure |
| `too many connections` | Connection saturation |
| `deadlock` / `lock wait timeout` | Contention |
| `slow query` / `duration:` (Postgres) | Query performance |
| `aborted connection` (MySQL) | Client/network issues |
| `checkpoint` warnings | I/O / WAL issues |
| `autovacuum` warnings | Maintenance issues |

#### CloudWatch Logs Insights example queries (deeper analysis)
Beyond `FilterLogEvents` pattern counts, run these against the resource's log groups
(`logs:StartQuery` / `logs:GetQueryResults`) for correlation. Adjust the log group and
7-day time range.

**Top slow queries by time (MySQL slow-query log):**
```
fields @timestamp, @message
| filter @message like /Query_time/
| parse @message "# Query_time: * Lock_time: * Rows_sent: * Rows_examined: *" as qt, lt, rs, re
| filter qt > 5
| sort qt desc
| limit 20
```

**Slow / long-duration statements (PostgreSQL log):**
```
fields @timestamp, @message
| filter @message like /duration:/
| parse @message "duration: * ms" as dur_ms
| filter dur_ms > 1000
| sort dur_ms desc
| limit 20
```

**Error rate by hour (both engines):**
```
fields @timestamp, @message
| filter @message like /ERROR|FATAL|Warning/
| stats count(*) as errors by bin(1h)
| sort errors desc
```

**Deadlock frequency (MySQL error log):**
```
fields @timestamp, @message
| filter @message like /Deadlock found/
| stats count(*) as deadlocks by bin(1h)
```

**Connection / auth failures (both engines):**
```
fields @timestamp, @message
| filter @message like /Too many connections|Aborted connection|Access denied|authentication failed/
| stats count(*) by bin(15m)
```

Cross-reference spikes with the CloudWatch metrics at the same timestamp (CPU, IOPS,
connections) to confirm cause.

### 5d. Maintenance configuration
**PostgreSQL autovacuum (parameter group):** `autovacuum`, `autovacuum_max_workers`, `autovacuum_naptime`, `autovacuum_vacuum_threshold`, `autovacuum_vacuum_scale_factor`, `autovacuum_analyze_threshold`, `autovacuum_analyze_scale_factor`, `autovacuum_vacuum_cost_delay`, `autovacuum_vacuum_cost_limit`. Effectiveness (tables with old `last_autovacuum`) is catalog-only — see 5f. Instance-level wraparound risk is the CloudWatch `MaximumUsedTransactionIDs` metric (Reliability 3b/3e).
**MySQL InnoDB (parameter group):** `innodb_stats_auto_recalc`, `innodb_stats_persistent`; event scheduler status.
**Engine version currency:** `rds.DescribeDBEngineVersions` (minor not latest → LOW; major EOL/within 6 months → HIGH).

### 5e. Operational Excellence best-practice checks
| Check | Condition | Severity |
|-------|-----------|----------|
| Missing CloudWatch alarms | No alarm on CPU, Storage, Memory, Connections, or Latency | MEDIUM (each) |
| No event subscriptions | Resource not covered by any event subscription | MEDIUM |
| Engine version outdated | Major version approaching EOL | HIGH |
| Engine version outdated | Minor version not latest | LOW |
| Log exports missing | Engine logs not exported to CloudWatch | MEDIUM |
| Database Insights | Standard mode not enabled, or Advanced mode not enabled where deeper analysis is needed | MEDIUM |
| Performance Insights migration | Still relying on standalone Performance Insights (EOL 2026-06-30) instead of Database Insights Advanced mode | MEDIUM |
| Enhanced Monitoring | Disabled or interval > 60s for production | MEDIUM |
| Maintenance window | Overlaps business hours | LOW |
| Maintenance window | Not configured (uses default) | LOW |
| Operational tags | Missing `Environment`, `Owner`, `Runbook`, `OnCall` | LOW |
| Default parameter group | Using `default.*` parameter group | MEDIUM |
| pg_stat_statements | Not in `shared_preload_libraries` (PostgreSQL) | MEDIUM |
| Autovacuum disabled | `autovacuum=off` | HIGH |
| Slow query log | Not enabled (MySQL) | MEDIUM |

Full checklist: `references/ops-excellence-checklist.md`.

> Record **every** matched check (any severity, per resource) as a row in the
> Operational Excellence Findings table — see the completeness contract in Step 8c-bis.

### 5f. Database-internal checks (CloudWatch for context; parameter group for config; Data API only for catalog-only residuals)
Context/uptime from CloudWatch, all configuration from the parameter group (Step 2b),
and only autovacuum effectiveness needs the RDS Data API (**NOT VERIFIED** if
unavailable).

**PostgreSQL:**
- **Server/environment context** — **CloudWatch only:** `EngineUptime` (short uptime + recent issues → restart/failover); engine version from `rds.DescribeDBClusters`.
- **Logging configuration** — **parameter group:** `log_connections`, `log_disconnections`, `log_checkpoints`, `log_statement`, `log_min_duration_statement`, `log_temp_files`, `log_autovacuum_min_duration`, `log_lock_waits`.
- **Instrumentation** — **parameter group:** `shared_preload_libraries` includes `pg_stat_statements` (and optionally `auto_explain`); Database Insights enablement/mode from `rds.DescribeDBInstances`.
- **Autovacuum tuning** — **parameter group:** the `autovacuum*` family (workers, naptime, thresholds/scale factors, cost delay/limit); flag `autovacuum=off` (critical) or defaults on large tables.
- **Autovacuum effectiveness** — **RDS Data API (catalog-only):** `pg_stat_user_tables` `last_autovacuum`/`last_autoanalyze` and dead-tuple ratios for aged tables.

**MySQL / Aurora MySQL:**
- **Server/environment context** — **CloudWatch only:** `EngineUptime`; engine + Aurora/RDS from `rds.DescribeDBClusters`/`DescribeDBInstances`.
- **Logging configuration** — **parameter group:** `slow_query_log`, `long_query_time`, `log_output`, `general_log`, `innodb_print_all_deadlocks`.
- **Instrumentation** — **parameter group:** `performance_schema` = ON.
- **Critical / maintenance variables** — **parameter group:** `max_connections`, `innodb_flush_log_at_trx_commit`, `sync_binlog`, `innodb_file_per_table`, character set/collation, `innodb_stats_auto_recalc`, `innodb_stats_persistent`, event-scheduler.

---

## Step 6: Performance Efficiency Pillar

### 6a. CloudWatch metrics (15-day window, `Period=21600` / 6h)
**RDS Instances** (dim `DBInstanceIdentifier`): CPUUtilization (Avg), FreeableMemory (Min), FreeStorageSpace (Min), ReadIOPS (Avg), WriteIOPS (Avg), ReadLatency (Avg), WriteLatency (Avg), DatabaseConnections (Max), SwapUsage (Avg), NetworkReceiveThroughput (Avg), NetworkTransmitThroughput (Avg).
**Aurora Clusters** (dim `DBClusterIdentifier`): CPUUtilization (Avg), FreeableMemory (Min), DatabaseConnections (Max), AuroraReplicaLag (Max), BufferCacheHitRatio (Avg), CommitLatency (Avg), ReadLatency (Avg), WriteLatency (Avg), VolumeReadIOPs (Sum), VolumeWriteIOPs (Sum), ServerlessDatabaseCapacity (Avg).

### 6b. Database Insights — DB load analysis (if enabled)
Use **Amazon CloudWatch Database Insights** for database load (DB Load) analysis
(Standard mode by default; Advanced mode adds execution plans, lock/query analysis,
and on-demand analysis). Programmatically retrieve DB-load data via the Performance
Insights API (the metrics interface Database Insights is built on):
```
pi.GetResourceMetrics     # db.load.avg vs vCPU count
pi.DescribeDimensionKeys  # top wait events by category, top SQL by DB load
```
Focus on: DB load vs vCPU (overloaded if load > vCPU sustained), top wait events (CPU/IO/Lock/Network), top SQL by average active sessions, queries with high db.load or frequent I/O waits. Note: standalone Performance Insights reaches EOL 2026-06-30 — prefer Database Insights (Advanced mode) going forward. See the Observability Stack references in `references/ops-excellence-checklist.md`.

### 6c. Database-internal checks (Database Insights / CloudWatch; parameter group for config; Data API only for catalog-only residuals)
Load, activity, top SQL and cache come from Database Insights / CloudWatch;
configuration from the parameter group (Step 2b); only bloat, per-table sizes, and
index inventory need the RDS Data API (**NOT VERIFIED** if unavailable).

**PostgreSQL:**
- **Top queries** — **Database Insights only:** DBI / PI `DescribeDimensionKeys` for top SQL by DB load (and top wait events); this replaces `pg_stat_statements`.
- **DB load & wait events** — **Database Insights only:** `pi.GetResourceMetrics` `db.load.avg` vs vCPU; top wait categories (CPU/IO/Lock).
- **Lock contention** — **Database Insights (Advanced mode) only:** DBI SQL lock analysis (blocking vs waiting sessions, lock tree, 15-month retention) — PostgreSQL only. Fully replaces catalog lock-wait queries; no Data API needed.
- **Connections / activity** — **CloudWatch + Database Insights:** `DatabaseConnections` and DBI active sessions (active vs idle-in-transaction, long-running).
- **Buffer cache efficiency** — **CloudWatch only:** `BufferCacheHitRatio` (Aurora); look for < ~99%.
- **Config baselines** — **parameter group:** `shared_buffers`, `effective_cache_size`, `work_mem`, `maintenance_work_mem`, `random_page_cost`, `checkpoint_timeout`, `max_wal_size`, `default_statistics_target`, `log_temp_files`, and Aurora `apg_*`/`aurora_*`.
- **Table bloat** — **RDS Data API (catalog-only):** `pg_stat_user_tables` dead-vs-live tuple ratio + `last_autovacuum`.
- **Indexes (unused/duplicate)** — **RDS Data API (catalog-only):** `pg_stat_user_indexes`/`pg_index`.
- **Object sizes** — **RDS Data API (catalog-only):** `pg_relation_size`/`pg_total_relation_size` for largest DBs/tables (volume totals available via CloudWatch `VolumeBytesUsed`/`FreeStorageSpace`).

**MySQL / Aurora MySQL:**
- **Top queries** — **Database Insights only:** DBI / PI top SQL by load; replaces `events_statements_summary_by_digest`.
- **DB load & wait events** — **Database Insights only:** `db.load.avg` vs vCPU, top waits.
- **Connections / activity** — **CloudWatch + Database Insights:** `DatabaseConnections` and DBI active sessions / thread states.
- **InnoDB buffer pool** — **CloudWatch only:** `BufferCacheHitRatio` (Aurora MySQL); look for < ~99%.
- **Config baselines** — **parameter group:** `innodb_buffer_pool_size`, `innodb_log_file_size`, `max_connections`, `table_open_cache` (avoid deprecated `query_cache_type` on 8.0+).
- **Active transactions & lock waits** — **Database Insights + CloudWatch only:** DBI top-SQL / active sessions identify the blocking or long-running statement, corroborated by `TransactionAgeMaximum` / `RollbackSegmentHistoryListLength`. (DBI SQL lock analysis is PostgreSQL-only, so for MySQL there is no blocking-vs-waiting lock graph — the exact `innodb_lock_waits` chain is not needed; the hotspot statement is the actionable signal.)
- **Index usage (unused/redundant)** — **RDS Data API (catalog-only):** `table_io_waits_summary_by_index_usage` + `mysql.innodb_index_stats`; `sys.schema_redundant_indexes`.
- **Storage / fragmentation** — **RDS Data API (catalog-only):** `information_schema.tables` sizes + `data_free` (> ~20% fragmentation); volume totals via CloudWatch.

Compare parameter-group baselines against `references/performance-metrics-thresholds.md`
sizing guidance.

### 6d. Performance thresholds
| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPUUtilization avg | > 70% | > 90% | Right-size or add read replica |
| FreeableMemory min | < 10% class memory | < 5% class memory | Upgrade instance class |
| SwapUsage avg | > 0 sustained | > 100 MB sustained | Memory undersized |
| FreeStorageSpace min | < 20% allocated | < 10% allocated | Enable autoscaling |
| ReadLatency avg | > 10 ms | > 20 ms | Check IOPS, working set |
| WriteLatency avg | > 10 ms | > 20 ms | Check IOPS, sync settings |
| DatabaseConnections max | > 80% max_connections | > 95% | Add pooling (RDS Proxy) |
| BufferCacheHitRatio avg (Aurora) | < 95% | < 90% | Larger instance class |
| ReplicaLag max | > 30 s | > 300 s | Investigate write rate |
| Database Insights | not enabled | — | Enable (Standard default; Advanced for deep analysis) |
| Enhanced Monitoring | disabled or > 60s | — | Enable for production |

Full thresholds & config baselines: `references/performance-metrics-thresholds.md`.

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
Relevant usage types: `Aurora:ServerlessV2Usage`, `Aurora:StorageIOUsage`, `Aurora:StorageUsage`, `Aurora:BackupUsage`, `RDS:ChargedBackupUsage`, `RDS:GP3-Storage`, `RDS:GP3-PIOPS`, `RDS:Multi-AZUsage`, `InstanceUsage`, `Multi-AZUsage`.

**Commitment coverage:**
```
costexplorer.GetReservationCoverage     # RI coverage
costexplorer.GetSavingsPlansCoverage    # SP coverage
rds.DescribeReservedDBInstances         # RI inventory
```
Check for expiring RIs or underutilized Savings Plans.

### 7b. CloudWatch metrics (15-day window)
CPUUtilization (Avg), FreeableMemory (Min), DatabaseConnections (Max), ReadIOPS/WriteIOPS (Avg), VolumeBytesUsed (Avg), ServerlessDatabaseCapacity (Avg).

### 7c. I/O cost optimization
1. Get ACTUAL monthly Read/Write I/O counts from Cost Explorer or CloudWatch.
2. Determine current storage tier (`standard` vs `aurora-iopt1`).
3. Look up actual I/O pricing for the engine and region.
- **Standard storage:** if I/O cost > 25% of total RDS cost → recommend I/O-Optimized (show cost comparison).
- **I/O-Optimized (`aurora-iopt1`):** if equivalent standard I/O would be < 25% of total → recommend switching back.

### 7d. Cost Optimization best-practice checks
| Check | Condition | Severity |
|-------|-----------|----------|
| Stopped instances | `DBInstanceStatus=stopped` (still pays storage) | HIGH |
| Previous-gen classes | `db.m4`, `db.r4`, `db.t2` | MEDIUM |
| gp2 storage | `StorageType=gp2` (gp3 is ~20% cheaper) | MEDIUM |
| Over-provisioned IOPS | io1/io2 with avg IOPS used < 50% provisioned | MEDIUM |
| No RI coverage | Production On-Demand without RIs | MEDIUM |
| Storage autoscaling | `MaxAllocatedStorage` not set | LOW |
| Idle databases | Connections max < 5 + CPU avg < 5% (7 days) | MEDIUM |
| Old manual snapshots | Snapshots > 90 days old | LOW |
| Missing cost tags | No `Environment`, `Owner`, `CostCenter` tags | LOW |
| Graviton eligible | x86 (`db.r5`, `db.m5`, `db.t3`) where Graviton available | MEDIUM |
| Serverless v2 ACU | Sustained at max ACU ceiling | MEDIUM |

Full reference (instance-gen/storage comparison, Savings Plans details, right-sizing, backup cost): `references/cost-optimization-reference.md`.

> Record **every** matched check (any severity, per resource) as a row in the Cost
> Findings table, each with its cost impact / potential savings — see the completeness
> contract in Step 8c-bis.

### 7e. Database-internal checks (CloudWatch / Database Insights only — no Data API)
- **Idle-database confirmation** — **CloudWatch + Database Insights only:** `DatabaseConnections` (max < 5) + `CPUUtilization` (avg < 5%) over 7 days, corroborated by DBI near-zero active sessions → supports stop/downsize/remove.
- **Over-sized capacity signals** — **CloudWatch only:** low `CPUUtilization`/`DatabaseConnections`/`ServerlessDatabaseCapacity` vs class/ACU ceiling → right-size or reduce Serverless v2 min ACU.
- **Storage growth & reclaim signal** — **CloudWatch only:** volume totals and trend from `VolumeBytesUsed` / `FreeStorageSpace` (and `AuroraVolumeBytesLeftTotal` where applicable) → project growth and flag reclaim/archiving candidates at the instance/cluster level. Note Aurora storage does not auto-shrink.

---

## Step 8: Generate the Combined WAR Report

### 8a. Save the report as an artifact (mandatory)
You MUST persist the report to a file — do not only print it in the chat. Write the
full markdown report to an artifact.

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

- **Single resource:** name it `rds-war-review-<resource-name>-<YYYY-MM-DD>.md`.
- **Multiple resources / whole account (fleet review):** produce **one consolidated
  report** covering all in-scope resources named
  `rds-war-<scope-label>-<YYYY-MM-DD>.md` (e.g. `AllClusters`), with per-cluster
  comparison tables in each pillar (one column per resource) — do NOT emit a separate
  file per cluster. This matches the fleet health-check format.

Also generate the PNG charts described in 8e and save them alongside the report
(referenced from the markdown), so the deliverable includes the same visual output the
individual pillar skills' runs produce. Use the available file-writing / plotting
capability to create these files (e.g., write to the working directory / artifacts
location), then confirm every saved path (the `.md` and each `.png`) to the user.
After saving, you may also summarize the Executive Summary inline, but the
authoritative deliverable is the saved `.md` report plus its `.png` charts.

**Format adaptivity:** the `.md` + `.png` deliverable above is the default (and the
format for file-artifact runtimes like AWS DevOps Agent). On a runtime that composes
**structured artifacts** instead of files, render the equivalent native elements
(`text` for narrative, `data_table` for every table, `chart` for the visualizations) in
the same order — do NOT force a markdown file if the runtime doesn't support one. Either
way, preserve the section order in `references/report-structure.md`, every table and
finding, and the 8c-bis reconciliation. See "Format adaptivity" in
`references/report-structure.md`.

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
Before writing the report, you MUST open **`references/report-structure.md`** and
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
`references/report-structure.md` (overall scorecard + findings-by-severity, and the
per-pillar metric/coverage/spend charts), save them alongside the report, embed each
with a markdown image link in the pillar section it belongs to, and list every `.png`
under the report's **Artifacts** line. Charts supplement — never replace — the detail
tables; if the plotting library or data is unavailable, note it in Scope Covered.

## Severity Definitions

Applies to all pillars. Where a pillar-specific nuance exists it is noted; the SLAs
are common.

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, data integrity, or security; or major cost waste (> 50% savings available) | 24–48 hours |
| HIGH | Significant gap that could lead to outages, exploitation, delayed incident response, or overspend > 30% | 1 week |
| MEDIUM | Notable improvement opportunity (operational maturity, performance, cost 10–30%) | 30 days |
| LOW | Minor hardening / optimization (< 10%) | When convenient |
| INFO | Observation, no action required | N/A |

## References

- `references/reliability-checklist.md` — Reliability pillar best-practices checklist
- `references/security-checklist.md` — Security pillar checklist + compliance mapping
- `references/ops-excellence-checklist.md` — Operational Excellence checklist
- `references/performance-metrics-thresholds.md` — Performance metrics thresholds & config baselines
- `references/cost-optimization-reference.md` — Cost optimization reference tables
- `references/report-structure.md` — **authoritative combined report template** (Step 8 output) + PNG chart catalog

Database-internal (data-plane) checks are described inline within each pillar, each
naming its source — Database Insights / CloudWatch, parameter group, or (for a few
catalog-only residuals) the read-only RDS Data API. No separate data-plane reference
file or MCP server is used.
