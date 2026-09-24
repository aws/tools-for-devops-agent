# Operational Review — Live Data Collection Queries

These read-only queries collect the data the Detailed Operational Review needs
directly from the cluster or workgroup via the connected `execute_query` tool —
no CSV upload required. Run each block, then evaluate the results against
`assets/config/thresholds.yaml` and map findings using
`references/operational-review-signals.md`.

Notes:
- All queries are read-only SELECTs and run inside the read-only transaction.
- SVV_* and SYS_* views work on both provisioned and Serverless. STL/STV views
  are provisioned-only; for Serverless, skip the STV-based storage query and use
  the SYS_SERVERLESS_USAGE query instead.
- If a view or column is not available on the target's Redshift version/type,
  report that section as "not available" and continue with the others. Do not
  guess values.
- Default lookback is 7 days; adjust the DATEADD interval as needed.

---

## Section 1 — Storage Utilization

Provisioned (STV_PARTITIONS):

```sql
SELECT SUM(capacity) / 1024.0 AS capacity_gb,
       SUM(used) / 1024.0 AS used_gb,
       ROUND(100.0 * SUM(used) / NULLIF(SUM(capacity), 0), 1) AS storage_utilization_pct
FROM stv_partitions
WHERE part_begin = 0;
```

Serverless (SYS_SERVERLESS_USAGE, last 24h):

```sql
SELECT MAX(storage_capacity_used) / 1024.0 AS storage_used_gb,
       AVG(compute_capacity) AS avg_rpu,
       MAX(compute_capacity) AS max_rpu
FROM sys_serverless_usage
WHERE start_time >= DATEADD(day, -1, GETDATE());
```

Signal: storage_utilization_pct > 70 → WARN (recommendation #5/#6/#4/#2).

Storage skew across partitions (provisioned only — STV_PARTITIONS is not
available on Serverless; report storage_skew_ratio as "not available" there):

```sql
SELECT ROUND(MAX(used)::numeric / NULLIF(MIN(used), 0), 2) AS storage_skew_ratio
FROM stv_partitions
WHERE part_begin = 0;
```

Slice count (provisioned only — Serverless has no fixed slice count; report as
"not applicable" there):

```sql
SELECT COUNT(*) AS slice_count
FROM stv_slices;
```

Signal: storage_skew_ratio > 1.1 → WARN (uneven disk usage across nodes/partitions,
often a sign of a poor distribution key at the cluster level).

---

## Section 2 — Usage Pattern (hourly workload, last 7 days)

```sql
SELECT DATE_TRUNC('hour', start_time) AS hour,
       COUNT(*) AS query_count,
       SUM(CASE WHEN query_type = 'COPY' THEN 1 ELSE 0 END) AS copy_count,
       SUM(CASE WHEN query_type = 'INSERT' THEN 1 ELSE 0 END) AS insert_count,
       SUM(CASE WHEN query_type = 'DDL' THEN 1 ELSE 0 END) AS ddl_count,
       SUM(CASE WHEN query_type = 'CTAS' THEN 1 ELSE 0 END) AS ctas_count,
       SUM(CASE WHEN result_cache_hit THEN 1 ELSE 0 END) AS result_cache_hits,
       SUM(CASE WHEN queue_time > 0 THEN 1 ELSE 0 END) AS queued_queries,
       SUM(CASE WHEN compile_time > 0 THEN 1 ELSE 0 END) AS compiled_queries,
       ROUND(100.0 * SUM(queue_time) / NULLIF(SUM(elapsed_time), 0), 2) AS pct_wlm_queue_time
FROM sys_query_history
WHERE start_time >= DATEADD(day, -7, GETDATE())
  AND user_id > 1
GROUP BY 1
ORDER BY 1 DESC;
```

Small single-row inserts (last 7 days):

```sql
SELECT COUNT(*) AS small_insert_count
FROM sys_query_history
WHERE start_time >= DATEADD(day, -7, GETDATE())
  AND query_type = 'INSERT'
  AND returned_rows BETWEEN 1 AND 100
  AND user_id > 1;
```

Disk spill counts (last 7 days, from step detail):

```sql
-- spilled_block_local_disk / spilled_block_remote_disk are block counts,
-- not bytes. Redshift blocks are a fixed 1 MB, so a block count already
-- equals megabytes -- no byte-to-MB division needed.
SELECT COUNT(DISTINCT d.query_id) AS total_disk_spill_count,
       SUM(d.spilled_block_local_disk) AS total_local_spill_mb,
       SUM(d.spilled_block_remote_disk) AS total_remote_spill_mb
FROM sys_query_detail d
JOIN sys_query_history h ON d.query_id = h.query_id
WHERE h.start_time >= DATEADD(day, -7, GETDATE())
  AND (d.spilled_block_local_disk > 0 OR d.spilled_block_remote_disk > 0);
```

Signals: pct_wlm_queue_time > 5, copy_count > 100, ddl_count > 10, ctas_count > 10,
compiled_queries > 100, small_insert_count > 100, total_disk_spill_count > 10 → WARN.

---

## Section 3 — Table Info (design health)

```sql
SELECT "schema",
       "table",
       tbl_rows,
       diststyle,
       sortkey1,
       sortkey_num,
       sortkey1_enc,
       skew_rows,
       stats_off,
       unsorted,
       vacuum_sort_benefit,
       max_varchar,
       encoded,
       size AS size_mb,
       pct_used
FROM svv_table_info
WHERE "schema" NOT IN ('pg_catalog', 'information_schema', 'pg_internal')
ORDER BY size DESC
LIMIT 200;
```

Signals (per row): skew_rows >= 4 → FAIL; vacuum_sort_benefit >= 10, stats_off > 10,
max_varchar > 1000 → WARN; large tables (> 5M rows) without sortkey1 or with EVEN/date
DISTKEY → WARN. See operational-review-signals.md for the full population filters and
recommendation IDs.

Note: `SVV_TABLE_INFO.empty` is documented by AWS as "for internal use... no longer
used" -- it is not a reliable deleted-row percentage and is intentionally not
collected here. `unsorted` and `stats_off` are still valid columns for staleness
checks.

---

## Section 3b — WLM Configuration (provisioned only)

STV_WLM_* views are provisioned-only. Redshift Serverless uses Auto WLM with no
user-configurable queues — for Serverless, report WLM Mode as "Auto (Serverless)"
and skip the per-queue tables below.

Current WLM mode and slot/queue counts:

```sql
SELECT CASE WHEN MIN(num_query_tasks) = -1 THEN 'Auto' ELSE 'Manual' END AS wlm_mode,
       COUNT(*) AS user_queue_count,
       SUM(CASE WHEN num_query_tasks = -1 THEN 0 ELSE num_query_tasks END) AS total_wlm_slots
FROM stv_wlm_service_class_config
WHERE service_class > 4;
```

Per-queue configuration (see `assets/queries/wlm-analysis.md` #3 for the
canonical version of this query):

```sql
SELECT service_class,
       num_query_tasks AS concurrency,
       query_working_mem / 1024 AS working_mem_mb,
       max_execution_time / 1000000 AS max_exec_sec,
       priority
FROM stv_wlm_service_class_config
WHERE service_class > 4
ORDER BY service_class;
```

QMR rule actions taken in the last 7 days (rule *thresholds* are set in the WLM
parameter group/console/API, not exposed by a queryable system view — report
threshold values as "not available via MCP tools" and use this action history
as the closest live signal instead; see `assets/queries/wlm-analysis.md` #5 for
the canonical version):

```sql
SELECT rule,
       action,
       service_class,
       COUNT(*) AS action_count
FROM stl_wlm_rule_action
WHERE record_time >= DATEADD(day, -7, GETDATE())
GROUP BY rule, action, service_class
ORDER BY action_count DESC;
```

Signal: any QMR `action_count` > 0 for `action = 'abort'` → WARN (queries are
being killed by monitoring rules — review the offending queue's workload).

---

## Section 4 — Advisor (Alter Table) Recommendations

```sql
SELECT type,
       ddl,
       auto_eligible
FROM svv_alter_table_recommendations;
```

Signals: type in (encode, sortkey, diststyle) with auto_eligible = 'f' → surface the
DDL as a recommendation (#4/#7/#8).

---

## Section 5 — Materialized Views

```sql
SELECT database_name,
       schema_name,
       name,
       is_stale,
       state,
       autorefresh,
       autorewrite
FROM svv_mv_info;
```

Recent refresh history:

```sql
SELECT db_name,
       schema_name,
       mv_name,
       status,
       refresh_type,
       duration / 1000000.0 AS refresh_duration_sec,
       start_time
FROM sys_mv_refresh_history
WHERE start_time >= DATEADD(day, -7, GETDATE())
ORDER BY start_time DESC;
```

Signals: state = 0 (full refresh) → recommend incremental MV (#30); is_stale = 't' → (#40);
broken + stale + autorefresh → recreate (#31).

---

## Section 6 — Top Queries by Run Time

Use the existing template in `assets/queries/top50-queries.md` (SYS_QUERY_HISTORY).
For per-query spill, join SYS_QUERY_DETAIL and sum `spilled_block_local_disk` +
`spilled_block_remote_disk` per query_id (each block = 1 MB, so the summed block
count is already the spill size in MB); flag total spill > 100 (MB).

---

## Section 7 — COPY / Load Performance

Use the existing template in `assets/queries/copy-performance.md`
(SYS_LOAD_HISTORY / SYS_LOAD_DETAIL). Signals: avg_files_per_copy < 4, avg_file_size_mb < 10.

---

## Section 8 — Auto Table Optimization actions (last 30 days)

```sql
SELECT table_id,
       type AS alter_table_type,
       status,
       start_time
FROM sys_auto_table_optimization
WHERE start_time >= DATEADD(day, -30, GETDATE())
ORDER BY start_time DESC;
```

Signal: encode/distkey/sortkey actions not in ('Complete','already recommended') → review (#4/#7/#8).
If SYS_AUTO_TABLE_OPTIMIZATION is not present on the target, report this section as not available.

---

## Section 9 — Workload Evaluation (by scan size, last 7 days)

```sql
WITH q AS (
    -- input_bytes is the per-step input size on sys_query_detail; sum across
    -- a query's steps to approximate total bytes scanned (there is no
    -- single scan-total column on this view).
    SELECT h.query_id,
           h.elapsed_time / 1000000.0 AS elapsed_sec,
           COALESCE(SUM(d.input_bytes), 0) / (1024*1024.0) AS scan_mb
    FROM sys_query_history h
    LEFT JOIN sys_query_detail d ON h.query_id = d.query_id
    WHERE h.start_time >= DATEADD(day, -7, GETDATE())
      AND h.user_id > 1
    GROUP BY h.query_id, h.elapsed_time
)
SELECT CASE
           WHEN scan_mb < 100 THEN 'small'
           WHEN scan_mb < 500000 THEN 'medium'
           ELSE 'large'
       END AS workload_type,
       COUNT(*) AS query_cnt,
       ROUND(AVG(scan_mb), 1) AS scan_mb_avg,
       ROUND(AVG(elapsed_sec), 2) AS exec_sec_avg,
       ROUND(MAX(elapsed_sec), 2) AS exec_sec_max
FROM q
GROUP BY 1
ORDER BY query_cnt DESC;
```

Use to describe the dominant workload and support cost/serverless-sizing discussion.

---

## Section 10 — Spectrum / External Query Performance (if used)

Per-table breakdown (the report template lists one row per external table, so
group by table_name/file_location rather than returning a single aggregate row;
`partition_count` here is the table's total partition count, matching the
report template's "Partitions" column):

```sql
SELECT table_name,
       file_format,
       MAX(file_location) AS file_location,
       COUNT(*) AS external_query_count,
       AVG(elapsed_time) / 1000000.0 AS avg_elapsed_sec,
       SUM(total_partitions) AS partition_count,
       ROUND(100.0 * SUM(qualified_partitions) / NULLIF(SUM(total_partitions), 0), 1) AS partition_pruning_pct
FROM sys_external_query_detail
WHERE start_time >= DATEADD(day, -7, GETDATE())
GROUP BY table_name, file_format
ORDER BY external_query_count DESC;
```

Cluster-wide summary (for the section's opening line —
"N external tables queried, M with poor pruning"):

```sql
SELECT COUNT(DISTINCT table_name) AS spectrum_table_count,
       COUNT(DISTINCT CASE
           WHEN qualified_partitions_pct < 95 THEN table_name
       END) AS spectrum_poor_pruning_count
FROM (
    SELECT table_name,
           ROUND(100.0 * SUM(qualified_partitions) / NULLIF(SUM(total_partitions), 0), 1) AS qualified_partitions_pct
    FROM sys_external_query_detail
    WHERE start_time >= DATEADD(day, -7, GETDATE())
    GROUP BY table_name
) t;
```

Signal: partition_pruning_pct < 95 (per table) → optimize partitioning (#27). If the
target has no external/Spectrum queries or the view is unavailable, report this
section as not available.

---

## Section 11 — Data Sharing (if used)

Per-share object counts (the report template lists one row per data share, so
group by share_name rather than returning a single aggregate row):

```sql
SELECT btrim(share_name)::varchar(128) AS share_name,
       share_type,
       COUNT(*) AS share_object_count
FROM svv_datashare_objects
GROUP BY share_name, share_type
ORDER BY share_name;
```

Consumer request activity (SYS_DATASHARE_USAGE_CONSUMER has no `duration` or
`share_name` column — it only carries a request-level status/error, not
latency or which share was involved, so this stays a cluster-wide count of
recent requests and errors rather than a per-share latency metric):

```sql
SELECT COUNT(*) AS request_count,
       SUM(CASE WHEN status <> 0 THEN 1 ELSE 0 END) AS error_count
FROM sys_datashare_usage_consumer
WHERE record_time >= DATEADD(day, -7, GETDATE());
```

Signal: error_count > 0 → investigate the quoted `error` text on the failing
`request_type` rows (#34). If not a datashare consumer/producer or the views
are unavailable, report this section as not available.
