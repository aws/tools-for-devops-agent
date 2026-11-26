# RDS WAR — Check Tables and Query Reference

Lookup tables and example queries moved out of `SKILL.md`. Load the section named by the
relevant step. Content is unchanged.

## Reliability best-practice checks (Step 3d)

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

## Expected audit log exports by engine (Step 4b)

| Engine | Expected Log Exports |
|--------|---------------------|
| PostgreSQL | `postgresql` (error/slow), `upgrade` |
| MySQL/MariaDB | `audit`, `error`, `general`, `slowquery` |
| Oracle | `alert`, `audit`, `listener`, `trace` |
| SQL Server | `agent`, `error` |

## Security log-event patterns (Step 4c)

| Pattern | Indicates |
|---------|-----------|
| `authentication failed` | Credential issues or brute-force attempts |
| `password authentication failed` | Failed login attempts |
| `connection refused` | Network/access issues |
| `SSL connection required` | Non-SSL connection attempts |
| `permission denied` | Unauthorized access attempts |

## Security best-practice checks (Step 4d)

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

## Expected CloudWatch alarm thresholds (Step 5a)

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

## Operational log-event patterns (Step 5c)

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

## Operational Excellence best-practice checks (Step 5e)

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

## Performance thresholds (Step 6d)

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

## Cost Optimization best-practice checks (Step 7d)

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

## CloudWatch Logs Insights example queries (Step 5c)

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
