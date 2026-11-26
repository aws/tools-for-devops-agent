# RDS / Aurora Operational Excellence Checklist

## Monitoring & Alerting Requirements

### Required CloudWatch Alarms

| Resource Type | Metric | Threshold | Period | Priority |
|--------------|--------|-----------|--------|----------|
| All RDS/Aurora | CPUUtilization | > 80% | 5 min | HIGH |
| All RDS/Aurora | FreeStorageSpace | < 10% allocated | 5 min | HIGH |
| All RDS/Aurora | FreeableMemory | < 256 MB or < 10% class | 5 min | HIGH |
| All RDS/Aurora | DatabaseConnections | > 80% max_connections | 5 min | MEDIUM |
| All RDS/Aurora | ReadLatency | > 20 ms | 5 min | MEDIUM |
| All RDS/Aurora | WriteLatency | > 20 ms | 5 min | MEDIUM |
| Read Replicas | ReplicaLag | > 60 s | 5 min | HIGH |
| Aurora | AuroraReplicaLag | > 100 ms | 5 min | MEDIUM |
| Aurora | BufferCacheHitRatio | < 95% | 5 min | MEDIUM |
| Aurora | Deadlocks | > 0 sustained | 5 min | MEDIUM |

### Observability Stack

Use **Amazon CloudWatch Database Insights** as the primary database observability tool
(it supersedes standalone Performance Insights and inherits its capabilities plus
fleet-level monitoring, recommended alarms, and application-to-database correlation).

| Component | Expected State | Severity if Missing |
|-----------|---------------|---------------------|
| CloudWatch Database Insights | Enabled — **Standard** mode at minimum; **Advanced** mode for execution plans, lock/query analysis, on-demand analysis, 15-month retention | MEDIUM |
| Enhanced Monitoring | Enabled, interval ≤ 60s | MEDIUM |
| CloudWatch Log exports | Engine-appropriate logs exported | MEDIUM |
| Event subscriptions | Resource covered by notification | MEDIUM |
| RDS Proxy metrics | Monitored (if Proxy in use) | LOW |

**Database Insights notes & references:**
- Standard mode is enabled by default for RDS and Aurora; Advanced mode is opt-in and has additional cost — see the CloudWatch pricing page.
- **Standalone Performance Insights reaches end of life on June 30, 2026.** Migrate to the **Advanced mode of Database Insights** before then; clusters not upgraded default to Standard mode and lose PI-only features (e.g., execution plans, on-demand analysis).
- Get started with CloudWatch Database Insights: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights-Get-Started.html
- Monitoring Amazon RDS databases with Database Insights: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.html
- Monitoring Amazon Aurora databases with Database Insights: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/USER_DatabaseInsights.html
- Turning on Advanced mode (RDS): https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.TurningOnAdvanced.html
- Turning on Advanced mode (Aurora): https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/USER_DatabaseInsights.TurningOnAdvanced.html
- DB engine/Region/instance-class support for Database Insights: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.Engines.html

## Logging Configuration

### PostgreSQL Required Parameters

| Parameter | Recommended Value | Purpose |
|-----------|------------------|---------|
| `log_connections` | `on` | Track connection events |
| `log_disconnections` | `on` | Track disconnection events |
| `log_checkpoints` | `on` | Monitor checkpoint frequency |
| `log_statement` | `ddl` (minimum) | Audit DDL changes |
| `log_min_duration_statement` | `1000` (ms) | Capture slow queries |
| `log_temp_files` | `0` | Log all temp file usage |
| `log_autovacuum_min_duration` | `0` | Track autovacuum runs |
| `log_lock_waits` | `on` | Track lock contention |

### PostgreSQL Required Extensions

| Extension | Purpose | Priority |
|-----------|---------|----------|
| `pg_stat_statements` | Query performance tracking | HIGH |
| `pgaudit` | Audit logging for compliance | MEDIUM |
| `auto_explain` | Automatic slow query plans | LOW |
| `pg_cron` | Scheduled maintenance tasks | LOW |

### MySQL Required Parameters

| Parameter | Recommended Value | Purpose |
|-----------|------------------|---------|
| `slow_query_log` | `1` | Capture slow queries |
| `long_query_time` | `1` (seconds) | Slow query threshold |
| `log_output` | `FILE` | Write to CloudWatch-exportable files |
| `general_log` | `0` (prod) / `1` (debug) | General query logging |
| `innodb_print_all_deadlocks` | `1` | Log all deadlocks |

## Autovacuum Configuration (PostgreSQL)

### Recommended Settings

| Parameter | Default | Small Tables | Large Tables | Assessment |
|-----------|---------|-------------|-------------|------------|
| `autovacuum` | `on` | `on` | `on` | CRITICAL if `off` |
| `autovacuum_max_workers` | `3` | `3` | `5-8` | Scale with table count |
| `autovacuum_naptime` | `60s` | `60s` | `30s` | Reduce for busy DBs |
| `autovacuum_vacuum_threshold` | `50` | `50` | `50` | Minimum tuples |
| `autovacuum_vacuum_scale_factor` | `0.2` | `0.2` | `0.01-0.05` | Reduce for large tables |
| `autovacuum_analyze_threshold` | `50` | `50` | `50` | Minimum tuples |
| `autovacuum_analyze_scale_factor` | `0.1` | `0.1` | `0.01-0.05` | Reduce for large tables |
| `autovacuum_vacuum_cost_delay` | `2ms` | `2ms` | `0-2ms` | Reduce for faster vacuum |
| `autovacuum_vacuum_cost_limit` | `200` | `200` | `1000-2000` | Increase for faster vacuum |

### Autovacuum Health Indicators

| Indicator | Warning | Critical |
|-----------|---------|----------|
| Tables never vacuumed | Any table > 1M rows | — |
| Last vacuum > 7 days | On tables with high update/delete rate | — |
| Transaction ID age | > 500M remaining | > 200M remaining |
| Dead tuple ratio | > 10% of live tuples | > 20% of live tuples |

## Maintenance Windows

| Best Practice | Recommendation |
|---------------|---------------|
| Schedule | Non-business hours, weekday preferred |
| Duration | Minimum 30 minutes |
| Frequency | Weekly (default is sufficient) |
| Overlap check | Should not overlap backup window |
| Business hours | Never schedule during peak traffic |

## Tagging Requirements

| Tag Key | Purpose | Severity if Missing |
|---------|---------|---------------------|
| `Environment` | Differentiate prod/dev/staging | LOW |
| `Owner` | Contact for operational issues | LOW |
| `Runbook` | Link to operational procedures | LOW |
| `OnCall` | On-call team/rotation | LOW |
| `CostCenter` | Finance attribution | LOW |
| `Application` | Application mapping | LOW |

## Change Management

| Aspect | Best Practice | Severity if Not Followed |
|--------|--------------|--------------------------|
| Parameter group | Custom (not `default.*`) | MEDIUM |
| Parameter changes | Applied via planned maintenance | LOW |
| Engine upgrades | Tested in non-prod first | HIGH |
| Major upgrades | Blue/green deployment | MEDIUM |
| Auto minor upgrade | Enabled for non-production | MEDIUM |
