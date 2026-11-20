# RDS WAR — Database-Internal Check Details

Per-engine check lists moved out of `SKILL.md`. Each check names its source; use that
source exactly. Checks marked **RDS Data API (catalog-only)** are read-only and are
**NOT VERIFIED** if the Data API is unavailable. Content is unchanged.

## Reliability database-internal checks (Step 3e)

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

## Security database-internal checks (Step 4e)

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

## Operational Excellence database-internal checks (Step 5f)

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

## Performance Efficiency database-internal checks (Step 6c)

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

Compare parameter-group baselines against `references/performance-metrics-thresholds.md` sizing guidance.
