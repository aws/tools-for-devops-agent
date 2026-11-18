# RDS / Aurora Performance Metrics Thresholds Reference

All metrics retrieved via `cloudwatch.GetMetricData` over a 15-day window with `Period=21600` (6h).
Severity reflects sustained values, not single spikes.

**Metric definitions are authoritative in the official AWS documentation — treat the
tables below as a curated *starting set* of thresholds, and confirm the exact metric
name, namespace, dimension, unit, and availability (engine/instance-class-specific)
against the current CloudWatch metrics references:**

- **Metrics reference for Amazon RDS (index):** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/metrics-reference.html
- **Amazon CloudWatch metrics for Amazon RDS (instance-level + usage):** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-metrics.html
- **Amazon CloudWatch dimensions for Amazon RDS:** https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/dimensions.html
- **Amazon CloudWatch metrics for Amazon Aurora (cluster-level + instance-level):** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/Aurora.AuroraMonitoring.Metrics.html
- **Viewing RDS/Aurora metrics (console & CLI):** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/metrics_dimensions.html

New metrics are added over time (and some are engine- or Serverless-v2-specific); when
a metric below is missing or renamed for the target, defer to the references above
rather than the static rows here. For DB-load and query-level analysis, prefer
**CloudWatch Database Insights** (see the Operational Excellence checklist).

## RDS Instance Metrics (Namespace: `AWS/RDS`, Dimension: `DBInstanceIdentifier`)

| Metric | Stat | Normal | Warning | Critical | Action |
|--------|------|--------|---------|----------|--------|
| CPUUtilization | Average | < 60% | > 70% | > 90% | Right-size instance or add read replica |
| CPUUtilization | Maximum | < 80% | > 90% sustained | 100% sustained | CPU saturation under peak |
| FreeableMemory | Minimum | > 20% of class | < 10% of class | < 5% of class | Upgrade class or tune buffer pool |
| SwapUsage | Average | 0 | > 0 sustained | > 100 MB sustained | Memory undersized — upgrade |
| FreeStorageSpace | Minimum | > 20% allocated | < 20% allocated | < 10% allocated | Increase storage / enable autoscaling |
| ReadIOPS | Average | < 70% provisioned | > 80% provisioned | > 95% provisioned | Storage I/O saturation |
| WriteIOPS | Average | < 70% provisioned | > 80% provisioned | > 95% provisioned | Storage I/O saturation |
| ReadLatency | Average | < 5 ms | > 10 ms | > 20 ms | Slow reads — check IOPS, working set |
| WriteLatency | Average | < 5 ms | > 10 ms | > 20 ms | Slow writes — check IOPS, sync |
| DatabaseConnections | Maximum | < 60% max_conn | > 80% | > 95% | Add pooling (RDS Proxy) |
| ReplicaLag | Maximum | < 10 s | > 30 s | > 300 s | Investigate write rate, replica class |
| DiskQueueDepth | Average | < 5 | > 10 | > 30 | I/O queueing — increase IOPS |
| NetworkReceiveThroughput | Average | < 80% bandwidth | > 80% | > 95% | Network saturation |
| NetworkTransmitThroughput | Average | < 80% bandwidth | > 80% | > 95% | Network saturation |

## Aurora Cluster Metrics (Namespace: `AWS/RDS`, Dimension: `DBClusterIdentifier`)

| Metric | Stat | Normal | Warning | Critical | Action |
|--------|------|--------|---------|----------|--------|
| CPUUtilization | Average | < 60% | > 70% | > 90% | Scale class or add reader |
| FreeableMemory | Minimum | > 20% | < 10% | < 5% | Memory pressure |
| DatabaseConnections | Maximum | < 60% | > 80% | > 95% | Add RDS Proxy / pooling |
| AuroraReplicaLag | Maximum | < 50 ms | > 100 ms | > 1000 ms | Check writer load |
| BufferCacheHitRatio | Average | > 99% | < 95% | < 90% | Working set doesn't fit — bigger class |
| CommitLatency | Average | < 10 ms | > 20 ms | > 50 ms | Write path latency |
| ReadLatency | Average | < 5 ms | > 10 ms | > 20 ms | Slow reads |
| WriteLatency | Average | < 5 ms | > 10 ms | > 20 ms | Slow writes |
| ServerlessDatabaseCapacity | Average | within min/max | hitting max | sustained at max | Raise ACU ceiling |
| Deadlocks | Sum | 0 | > 0 sustained | > 100/hour | Transaction/lock review |

## Database Insights — DB Load Thresholds (when enabled)

Use **CloudWatch Database Insights** for DB-load analysis (Standard mode by default;
Advanced mode for execution plans, lock/query analysis, on-demand analysis). The
values below are retrieved via the Performance Insights API, the metrics interface
Database Insights is built on. Standalone Performance Insights reaches EOL 2026-06-30 —
prefer Database Insights Advanced mode. References: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Database-Insights-Get-Started.html · RDS https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_DatabaseInsights.html · Aurora https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/USER_DatabaseInsights.html

| Metric | Source | Warning | Action |
|--------|--------|---------|--------|
| `db.load.avg` | `pi.GetResourceMetrics` | > vCPU count sustained | DB at or above CPU capacity |
| Top wait event | dominant wait type | > 50% of load | Targets tuning area (CPU, IO, Lock) |
| Top SQL | total_call_count | top 5 by load | Inputs for query optimization |

## PostgreSQL Configuration Baselines

| Parameter | Small (< 8 vCPU) | Medium (8-32 vCPU) | Large (> 32 vCPU) |
|-----------|-------------------|--------------------|--------------------|
| shared_buffers | 25% of memory | 25% of memory | 25% of memory |
| effective_cache_size | 75% of memory | 75% of memory | 75% of memory |
| work_mem | 64 MB | 128 MB | 256 MB |
| maintenance_work_mem | 512 MB | 1 GB | 2 GB |
| random_page_cost | 1.1 (SSD) | 1.1 (SSD) | 1.1 (SSD) |
| default_statistics_target | 100 | 200 | 500 |
| checkpoint_timeout | 15 min | 15 min | 15 min |

## MySQL/InnoDB Configuration Baselines

| Parameter | Small (< 8 vCPU) | Medium (8-32 vCPU) | Large (> 32 vCPU) |
|-----------|-------------------|--------------------|--------------------|
| innodb_buffer_pool_size | 75% of memory | 75% of memory | 75% of memory |
| innodb_log_file_size | 1 GB | 2 GB | 4 GB |
| max_connections | 150 | 500 | 2000 |
| table_open_cache | 4000 | 8000 | 16000 |
| innodb_io_capacity | 1000 (gp3) | 3000 (gp3) | IOPS provisioned |
