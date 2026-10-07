"""Structured collection for customer-shareable health and upgrade reports."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from time import monotonic
from typing import Any, Callable

from assessment_engine import (
    NO_CHANGE,
    attach_automated_assessments,
    visible_columns,
)
from report_renderer import (
    HEALTH_NOTES,
    render_health_markdown,
    render_health_report,
    render_upgrade_report,
)


REFERENCE_KEY_PARAMETERS = (
    "max_connections",
    "shared_buffers",
    "checkpoint_timeout",
    "max_wal_size",
    "default_statistics_target",
    "work_mem",
    "maintenance_work_mem",
    "random_page_cost",
    "rds.logical_replication",
    "wal_keep_segments",
    "hot_standby_feedback",
)

QUERY_PREVIEW_TRANSFORM = "normalized_query_preview"
QUERY_PREVIEW_SOURCE_COLUMN = "_query_text"
QUERY_PREVIEW_COLUMN = "normalized_query_preview"
QUERY_PREVIEW_SOURCES_FIELD = "query_preview_sources"
QUERY_PREVIEW_MAX_CHARS = 240
QUERY_PREVIEW_WITHHELD = "[preview withheld]"
QUERY_PREVIEW_UNAVAILABLE = "[preview unavailable]"
_QUERY_PREVIEW_MAX_SOURCE_CHARS = 100_000
_QUERY_LITERAL_TOKENS = {
    "BCONST",
    "FCONST",
    "ICONST",
    "SCONST",
    "USCONST",
    "XCONST",
    "FALSE_P",
    "NULL_P",
    "PARAM",
    "TRUE_P",
}
_QUERY_COMMENT_TOKENS = {"C_COMMENT", "SQL_COMMENT"}


def normalize_instance_metadata(
    rds_client: Any, inst: dict[str, Any]
) -> dict[str, Any]:
    """Return platform-correct instance and cluster metadata for reporting."""
    engine = str(inst.get("Engine", ""))
    metadata: dict[str, Any] = {
        "engine": engine,
        "is_aurora": engine == "aurora-postgresql",
        "metadata_scope": "DB instance",
        "storage_allocation": (
            f"{inst['AllocatedStorage']} GB"
            if inst.get("AllocatedStorage") is not None
            else "Not collected"
        ),
        "storage_autoscaling": (
            f"{inst['MaxAllocatedStorage']} GB"
            if inst.get("MaxAllocatedStorage") is not None
            else "Not configured or not collected"
        ),
        "storage_type": inst.get("StorageType", "Not collected"),
        "availability": (
            "Multi-AZ enabled according to DB instance metadata"
            if inst.get("MultiAZ") is True
            else (
                "Single-AZ according to DB instance metadata"
                if inst.get("MultiAZ") is False
                else "Not collected"
            )
        ),
        "storage_encrypted": inst.get("StorageEncrypted", "Not collected"),
        "deletion_protection": inst.get("DeletionProtection", "Not collected"),
        "publicly_accessible": inst.get("PubliclyAccessible", "Not collected"),
        "backup_retention_period": inst.get(
            "BackupRetentionPeriod", "Not collected"
        ),
        "preferred_backup_window": inst.get(
            "PreferredBackupWindow", "Not collected"
        ),
        "cluster_id": "N/A",
        "cluster_parameter_group": "Not applicable",
        "cluster": None,
        "cluster_metadata_error": "",
    }
    if engine != "aurora-postgresql":
        return metadata

    metadata.update(
        {
            "metadata_scope": "Aurora DB cluster",
            "storage_allocation": (
                "Not applicable: Aurora cluster storage auto-scales; "
                "DBInstance.AllocatedStorage is not current used storage"
            ),
            "storage_autoscaling": "Aurora managed",
            "availability": "Not collected: Aurora cluster metadata unavailable",
            "storage_encrypted": "Not collected",
            "deletion_protection": "Not collected",
            "backup_retention_period": "Not collected",
            "preferred_backup_window": "Not collected",
        }
    )
    cluster_id = str(inst.get("DBClusterIdentifier", ""))
    metadata["cluster_id"] = cluster_id or "Not collected"
    if not cluster_id:
        metadata["cluster_metadata_error"] = (
            "Aurora instance did not include DBClusterIdentifier"
        )
        return metadata

    try:
        response = rds_client.describe_db_clusters(
            DBClusterIdentifier=cluster_id
        )
        clusters = response.get("DBClusters", [])
        if len(clusters) != 1:
            raise RuntimeError("Aurora cluster metadata was unavailable or ambiguous")
        cluster = clusters[0]
        availability_zones = sorted(
            str(zone) for zone in cluster.get("AvailabilityZones", []) if zone
        )
        members = cluster.get("DBClusterMembers", [])
        zone_evidence = (
            ", ".join(availability_zones)
            if availability_zones
            else "availability-zone names not returned"
        )
        metadata.update(
            {
                "cluster": cluster,
                "storage_type": cluster.get("StorageType", "aurora"),
                "availability": (
                    "Aurora cluster storage is distributed across multiple "
                    f"Availability Zones; reported zones: {zone_evidence}; "
                    f"DB cluster members: {len(members)}"
                ),
                "storage_encrypted": cluster.get(
                    "StorageEncrypted", "Not collected"
                ),
                "deletion_protection": cluster.get(
                    "DeletionProtection", "Not collected"
                ),
                "backup_retention_period": cluster.get(
                    "BackupRetentionPeriod", "Not collected"
                ),
                "preferred_backup_window": cluster.get(
                    "PreferredBackupWindow", "Not collected"
                ),
                "cluster_parameter_group": cluster.get(
                    "DBClusterParameterGroup", "Not collected"
                ),
            }
        )
    except Exception as exc:
        metadata["cluster_metadata_error"] = f"{type(exc).__name__}: {exc}"
    return metadata


def resolve_report_name(
    report_name: str,
    inst: dict[str, Any],
    instance_id: str,
    report_kind: str,
    target_major_version: int | None = None,
) -> str:
    """Derive a stable target label when the caller supplies no meaningful name."""
    normalized = str(report_name or "").strip()
    if normalized and normalized.casefold() not in {"customer", "auto"}:
        return normalized

    target_label = str(
        inst.get("DBClusterIdentifier")
        if inst.get("Engine") == "aurora-postgresql"
        else inst.get("DBInstanceIdentifier")
        or instance_id
    ).strip()
    if not target_label:
        target_label = instance_id.strip() or "PostgreSQL"

    if report_kind == "health":
        return target_label
    if report_kind == "pre-upgrade":
        if target_major_version is None:
            raise ValueError("target_major_version is required for pre-upgrade reports")
        return f"{target_label} to PostgreSQL {target_major_version}"
    raise ValueError(f"Unsupported report kind: {report_kind}")


def normalized_query_preview(query_text: Any) -> str:
    """Return a bounded DML preview with comments, literals, and binds removed."""
    if query_text is None:
        return QUERY_PREVIEW_UNAVAILABLE
    if not isinstance(query_text, str):
        return QUERY_PREVIEW_WITHHELD

    source = query_text.strip()
    if not source:
        return QUERY_PREVIEW_UNAVAILABLE
    if source == "<insufficient privilege>":
        return "[preview unavailable: insufficient privilege]"
    if len(source) > _QUERY_PREVIEW_MAX_SOURCE_CHARS:
        return QUERY_PREVIEW_WITHHELD

    try:
        from pglast import parse_sql, parser
        from pglast.ast import DeleteStmt, InsertStmt, MergeStmt, SelectStmt, UpdateStmt

        statements = parse_sql(source)
        if len(statements) != 1 or not isinstance(
            statements[0].stmt,
            (SelectStmt, InsertStmt, UpdateStmt, DeleteStmt, MergeStmt),
        ):
            return QUERY_PREVIEW_WITHHELD

        pieces: list[str] = []
        cursor = 0
        for token in parser.scan(source):
            if token.start < cursor or token.end < token.start:
                return QUERY_PREVIEW_WITHHELD
            pieces.append(source[cursor:token.start])
            if token.name in _QUERY_COMMENT_TOKENS:
                pieces.append(" ")
            elif token.name in _QUERY_LITERAL_TOKENS:
                pieces.append("?")
            else:
                pieces.append(source[token.start:token.end + 1])
            cursor = token.end + 1
        pieces.append(source[cursor:])
    except Exception:
        return QUERY_PREVIEW_WITHHELD

    preview = " ".join("".join(pieces).split())
    if not preview:
        return QUERY_PREVIEW_WITHHELD
    if len(preview) > QUERY_PREVIEW_MAX_CHARS:
        return preview[: QUERY_PREVIEW_MAX_CHARS - 1].rstrip() + "…"
    return preview


def transform_query_results(
    rows: list[dict], definition: dict[str, Any]
) -> list[dict]:
    """Apply a declared fail-closed result transform before serialization."""
    transform = definition.get("result_transform")
    if transform is None:
        return rows
    if transform != QUERY_PREVIEW_TRANSFORM:
        raise ValueError(f"Unsupported query result transform: {transform}")

    source_columns = definition.get(
        QUERY_PREVIEW_SOURCES_FIELD,
        {QUERY_PREVIEW_SOURCE_COLUMN: QUERY_PREVIEW_COLUMN},
    )
    if (
        not isinstance(source_columns, dict)
        or not source_columns
        or any(
            not isinstance(source, str)
            or not source
            or not isinstance(target, str)
            or not target
            for source, target in source_columns.items()
        )
        or len(set(source_columns.values())) != len(source_columns)
    ):
        raise ValueError("Invalid query preview source mapping")

    transformed_rows: list[dict] = []
    for row in rows:
        transformed: dict[str, Any] = {}
        sources_seen: set[str] = set()
        for column, value in row.items():
            if column in source_columns:
                transformed[source_columns[column]] = normalized_query_preview(value)
                sources_seen.add(column)
            else:
                transformed[column] = value
        for source, target in source_columns.items():
            if source not in sources_seen:
                transformed[target] = QUERY_PREVIEW_UNAVAILABLE
        transformed_rows.append(transformed)
    return transformed_rows


def install_report_queries(query_allowlist: dict[str, dict[str, dict]]) -> None:
    """Extend the existing allowlist with read-only report evidence queries."""
    query_allowlist["1"]["1.4"] = {
        "name": "Total Database Size and Count",
        "sql": (
            "SELECT count(*) AS database_count, "
            "sum(pg_database_size(datname)) AS total_bytes, "
            "pg_size_pretty(sum(pg_database_size(datname))) AS total_size "
            "FROM pg_database WHERE datistemplate = false"
        ),
    }
    query_allowlist["2"]["2.3"] = {
        "name": "Key, Logging, Autovacuum, and Aurora Parameter Inventory",
        "sql": (
            "SELECT CASE WHEN name LIKE 'autovacuum%' THEN 'autovacuum' "
            "WHEN name LIKE 'apg%' THEN 'aurora' "
            "WHEN name LIKE 'log%' THEN 'logging' ELSE 'key' END AS inventory, "
            "name, setting, unit, source AS pg_settings_source, "
            "context AS pg_settings_context, short_desc "
            "FROM pg_settings WHERE name IN ("
            "'max_connections','shared_buffers','effective_cache_size',"
            "'checkpoint_timeout','max_wal_size','min_wal_size','wal_buffers',"
            "'default_statistics_target','work_mem','maintenance_work_mem',"
            "'random_page_cost','seq_page_cost','effective_io_concurrency',"
            "'idle_in_transaction_session_timeout','statement_timeout',"
            "'lock_timeout','shared_preload_libraries','hot_standby_feedback',"
            "'rds.logical_replication','wal_keep_size','wal_keep_segments',"
            "'log_connections','log_disconnections','log_checkpoints',"
            "'log_min_duration_statement','log_statement','log_temp_files',"
            "'log_autovacuum_min_duration') OR name LIKE 'autovacuum%' "
            "OR name LIKE 'apg%' ORDER BY inventory, name"
        ),
    }
    query_allowlist["5"]["5.4"] = {
        "name": "Top 10 Tables by Total Size",
        "sql": (
            "SELECT current_database() AS _assessment_database_name, "
            "(SELECT oid::bigint FROM pg_database WHERE datname=current_database()) "
            "AS _assessment_database_oid, count(*) OVER ()::bigint "
            "AS _assessment_total_user_table_count, "
            "relid::bigint AS _assessment_relation_oid, "
            "schemaname AS table_schema, relname AS table_name, "
            "pg_size_pretty(pg_total_relation_size(relid)) AS total_size, "
            "pg_total_relation_size(relid) AS total_bytes, "
            "pg_size_pretty(pg_relation_size(relid)) AS data_size, "
            "pg_size_pretty(pg_total_relation_size(relid) - "
            "pg_relation_size(relid)) AS external_size "
            "FROM pg_catalog.pg_statio_user_tables "
            "ORDER BY pg_total_relation_size(relid) DESC, "
            "pg_relation_size(relid) DESC LIMIT 10"
        ),
    }
    query_allowlist["5"]["5.5"] = {
        "name": "Top 10 User Tables by Physical Bloat Estimate (Pinned Toolkit Heuristic)",
        "sql": """SELECT
  current_database() AS database_name,
  (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) AS _assessment_database_oid,
  relation_oid::bigint AS _assessment_relation_oid, schemaname, tablename,
  ROUND(MAX(CASE WHEN otta=0 THEN 0.0 ELSE sml.relpages::FLOAT/otta END)::NUMERIC,1) AS table_bloat_ratio,
  MAX(CASE WHEN relpages < otta THEN 0 ELSE bs*(sml.relpages-otta)::BIGINT END) AS estimated_table_wasted_bytes,
  COUNT(*) FILTER (WHERE iname <> '?') AS index_count,
  ROUND(MAX(CASE WHEN iotta=0 OR ipages=0 THEN 0.0 ELSE ipages::FLOAT/iotta END)::NUMERIC,1) AS max_index_bloat_ratio,
  SUM(CASE WHEN ipages < iotta THEN 0 ELSE bs*(ipages-iotta) END)::BIGINT AS estimated_index_wasted_bytes
FROM (
  SELECT
    cc.oid AS relation_oid, schemaname, tablename, cc.reltuples, cc.relpages, bs,
    CEIL((cc.reltuples*((datahdr+ma-
      (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::FLOAT)) AS otta,
    COALESCE(c2.relname,'?') AS iname, COALESCE(c2.reltuples,0) AS ituples,
    COALESCE(c2.relpages,0) AS ipages,
    COALESCE(CEIL((c2.reltuples*(datahdr-12))/(bs-20::FLOAT)),0) AS iotta
  FROM (
    SELECT
      ma, bs, schemaname, tablename,
      (datawidth+(hdr+ma-(CASE WHEN hdr%ma=0 THEN ma ELSE hdr%ma END)))::NUMERIC AS datahdr,
      (maxfracsum*(nullhdr+ma-(CASE WHEN nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
    FROM (
      SELECT
        schemaname, tablename, hdr, ma, bs,
        SUM((1-null_frac)*avg_width) AS datawidth,
        MAX(null_frac) AS maxfracsum,
        hdr+(
          SELECT 1+COUNT(*)/8
          FROM pg_stats s2
          WHERE null_frac<>0 AND s2.schemaname=s.schemaname
            AND s2.tablename=s.tablename
        ) AS nullhdr
      FROM pg_stats s, (
        SELECT
          current_setting('block_size')::NUMERIC AS bs,
          CASE WHEN SUBSTRING(v,12,3) IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
          CASE WHEN v ~ 'mingw32' THEN 8 ELSE 4 END AS ma
        FROM (SELECT version() AS v) AS foo
      ) AS constants
      WHERE s.schemaname NOT IN ('information_schema','pg_catalog','pg_toast')
      GROUP BY 1,2,3,4,5
    ) AS foo
  ) AS rs
  JOIN pg_class cc ON cc.relname=rs.tablename
  JOIN pg_namespace nn ON cc.relnamespace=nn.oid
    AND nn.nspname=rs.schemaname
    AND nn.nspname NOT IN ('information_schema','pg_catalog','pg_toast')
    AND cc.relkind IN ('r','m')
  LEFT JOIN pg_index i ON i.indrelid=cc.oid
  LEFT JOIN pg_class c2 ON c2.oid=i.indexrelid
) AS sml
GROUP BY relation_oid, schemaname, tablename
ORDER BY estimated_table_wasted_bytes DESC, estimated_index_wasted_bytes DESC
LIMIT 10""",
    }
    query_allowlist["6"]["6.5"] = {
        "name": "All-Database Cache Hit Ratio",
        "sql": (
            "SELECT datid::bigint AS _assessment_database_oid, "
            "datname AS database_name, blks_hit, blks_read, "
            "round((100.0 * blks_hit / NULLIF(blks_hit + blks_read, 0))::numeric, 2) "
            "AS cache_hit_ratio FROM pg_stat_database "
            "WHERE blks_hit + blks_read > 0 AND datname NOT IN ('template0','template1') "
            "ORDER BY cache_hit_ratio ASC"
        ),
    }
    diagnostic_role_filter = (
        "p.userid <> (SELECT oid FROM pg_roles WHERE rolname = current_user) "
    )
    query_allowlist["6"]["6.6"] = {
        "name": "Top 10 Queries by Shared Blocks Read",
        "result_transform": QUERY_PREVIEW_TRANSFORM,
        "sql": (
            "SELECT p.dbid::bigint AS _assessment_database_oid, "
            "p.userid::bigint AS _assessment_user_oid, "
            "p.queryid AS query_fingerprint, p.query AS _query_text, "
            "p.calls, p.shared_blks_read, "
            "p.shared_blks_hit, round((100.0 * p.shared_blks_hit / "
            "NULLIF(p.shared_blks_hit + p.shared_blks_read, 0))::numeric, 2) "
            "AS hit_percent FROM pg_stat_statements p JOIN pg_database d ON d.oid=p.dbid "
            "WHERE d.datname = current_database() AND "
            + diagnostic_role_filter
            + "ORDER BY p.shared_blks_read DESC LIMIT 10"
        ),
    }
    query_allowlist["6"]["6.7"] = {
        "name": "Top 10 Queries by Temporary Blocks Written",
        "result_transform": QUERY_PREVIEW_TRANSFORM,
        "sql": (
            "SELECT p.dbid::bigint AS _assessment_database_oid, "
            "p.userid::bigint AS _assessment_user_oid, "
            "p.queryid AS query_fingerprint, p.query AS _query_text, "
            "p.calls, round(p.total_exec_time::numeric, 2) AS total_exec_ms, "
            "p.temp_blks_written FROM pg_stat_statements p "
            "JOIN pg_database d ON d.oid=p.dbid "
            "WHERE d.datname = current_database() AND "
            + diagnostic_role_filter
            + "ORDER BY p.temp_blks_written DESC LIMIT 10"
        ),
    }
    query_allowlist["6"]["6.8"] = {
        "name": "Top 10 Queries by Temporary Blocks Read",
        "result_transform": QUERY_PREVIEW_TRANSFORM,
        "sql": (
            "SELECT p.dbid::bigint AS _assessment_database_oid, "
            "p.userid::bigint AS _assessment_user_oid, "
            "p.queryid AS query_fingerprint, p.query AS _query_text, "
            "p.calls, round(p.total_exec_time::numeric, 2) AS total_exec_ms, "
            "p.temp_blks_read FROM pg_stat_statements p "
            "JOIN pg_database d ON d.oid=p.dbid "
            "WHERE d.datname = current_database() AND "
            + diagnostic_role_filter
            + "ORDER BY p.temp_blks_read DESC LIMIT 10"
        ),
    }
    query_allowlist["6"]["6.9"] = {
        "name": "pg_stat_statements Statistics Window",
        "sql": "SELECT stats_reset FROM pg_stat_statements_info",
    }
    query_allowlist["7"]["7.4"] = {
        "name": "Top 10 Biggest Tables Last Vacuumed",
        "sql": (
            "SELECT (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) "
            "AS _assessment_database_oid, relid::bigint AS _assessment_relation_oid, "
            "schemaname, relname AS table_name, last_vacuum, last_autovacuum, "
            "last_analyze, last_autoanalyze, n_live_tup, n_dead_tup, "
            "vacuum_count, autovacuum_count, analyze_count, autoanalyze_count, "
            "pg_size_pretty(pg_total_relation_size(relid)) AS table_total_size, "
            "pg_total_relation_size(relid) AS total_bytes "
            "FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10"
        ),
    }
    query_allowlist["8"]["8.4"] = {
        "name": "Rarely Used Indexes (Fewer Than 10 Scans, Constraints Excluded)",
        "sql": (
            "SELECT (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) "
            "AS _assessment_database_oid, s.relid::bigint AS _assessment_relation_oid, "
            "s.indexrelid::bigint AS _assessment_index_oid, "
            "s.schemaname, s.relname AS table_name, "
            "s.indexrelname AS index_name, s.idx_scan AS index_scans, "
            "pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size, "
            "pg_relation_size(s.indexrelid) AS _assessment_index_bytes, "
            "pg_size_pretty(pg_relation_size(s.relid)) AS table_size, "
            "pg_relation_size(s.relid) AS table_bytes "
            "FROM pg_catalog.pg_stat_user_indexes s "
            "JOIN pg_catalog.pg_index i ON s.indexrelid=i.indexrelid "
            "WHERE s.idx_scan < 10 AND 0 <> ALL(i.indkey) AND NOT i.indisunique "
            "AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint c "
            "WHERE c.conindid=s.indexrelid) AND pg_relation_size(s.indexrelid) > 8192 "
            "ORDER BY s.idx_scan ASC, pg_relation_size(s.indexrelid) DESC LIMIT 10"
        ),
    }
    query_allowlist["11"]["11.7"] = {
        "name": "Top 10 Tables by Read I/O Activity",
        "sql": (
            "SELECT (SELECT oid::bigint FROM pg_database WHERE datname=current_database()) "
            "AS _assessment_database_oid, relid::bigint AS _assessment_relation_oid, "
            "schemaname, relname AS table_name, heap_blks_hit, heap_blks_read, "
            "round((100.0 * heap_blks_hit / NULLIF(heap_blks_hit + heap_blks_read, 0))::numeric, 2) "
            "AS hit_percent FROM pg_statio_user_tables "
            "WHERE heap_blks_hit + heap_blks_read > 0 "
            "ORDER BY heap_blks_read DESC, heap_blks_hit DESC LIMIT 10"
        ),
    }
    query_allowlist["10"]["10.9"] = {
        "name": "GiST Index Inventory",
        "sql": (
            "SELECT n.nspname AS schema_name, c.relname AS index_name "
            "FROM pg_index i JOIN pg_class c ON i.indexrelid=c.oid "
            "JOIN pg_namespace n ON c.relnamespace=n.oid "
            "JOIN pg_am am ON c.relam=am.oid WHERE am.amname='gist' "
            "AND n.nspname NOT IN ('pg_catalog','information_schema') "
            "ORDER BY n.nspname, c.relname"
        ),
    }
    query_allowlist["10"]["10.10"] = {
        "name": "User-Created ICU Collation Inventory",
        "sql": (
            "SELECT n.nspname AS schema_name, c.collname, c.collprovider, "
            "c.collisdeterministic, c.collversion "
            "FROM pg_collation c JOIN pg_namespace n ON n.oid=c.collnamespace "
            "WHERE c.collprovider='i' AND c.oid >= 16384 "
            "ORDER BY n.nspname, c.collname LIMIT 100"
        ),
    }
    query_allowlist["10"]["10.11"] = {
        "name": "PostgreSQL 17 Reserved-Name Review Inventory",
        "sql": (
            "SELECT n.nspname AS schema_name, c.relname AS object_name, "
            "CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'view' "
            "WHEN 'i' THEN 'index' WHEN 'S' THEN 'sequence' "
            "WHEN 'm' THEN 'materialized view' ELSE c.relkind::text END AS object_type "
            "FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
            "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
            "AND lower(c.relname) IN ('checkpoint','subscription','publication') "
            "ORDER BY n.nspname, c.relname"
        ),
    }
    query_allowlist["10"]["10.12"] = {
        "name": "Pending Restart Parameter Inventory",
        "sql": (
            "SELECT name, setting, reset_val, source AS pg_settings_source, context "
            "FROM pg_settings WHERE pending_restart=true ORDER BY name"
        ),
    }


def cloudwatch_period_seconds(period_minutes: int) -> int:
    """Choose a retention-valid period with no more than 1,440 datapoints."""
    seconds = period_minutes * 60
    if seconds < 63 * 24 * 60 * 60:
        retention_granularity = 300
    else:
        retention_granularity = 3600
    minimum = max(retention_granularity, ceil(seconds / 1440))
    return int(ceil(minimum / retention_granularity) * retention_granularity)


def _query_evidence(
    conn: Any,
    query_allowlist: dict[str, dict[str, dict]],
    query_ids: list[str],
    execute_query: Callable[[Any, str], list[dict]],
    deadline: float | None = None,
) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    supports_savepoints = callable(getattr(conn, "run", None))
    for index, query_id in enumerate(query_ids):
        remaining_ms: int | None = None
        if deadline is not None:
            remaining_ms = int((deadline - monotonic()) * 1000)
            if remaining_ms <= 0:
                evidence[query_id] = {
                    "state": "Not collected",
                    "message": "The report collection time budget was exhausted before this query started.",
                }
                continue
        category = query_id.split(".", 1)[0]
        definition = query_allowlist[category][query_id]
        savepoint = f"report_query_{index}"
        try:
            if supports_savepoints:
                if remaining_ms is not None:
                    conn.run(
                        "SET LOCAL statement_timeout = "
                        f"'{max(1, min(60000, remaining_ms))}ms'"
                    )
                conn.run(f"SAVEPOINT {savepoint}")
            rows = execute_query(conn, definition["sql"])
            rows = transform_query_results(rows, definition)
            if supports_savepoints:
                conn.run(f"RELEASE SAVEPOINT {savepoint}")
            evidence[query_id] = {"state": "Collected", "rows": rows}
        except Exception as exc:
            if supports_savepoints:
                try:
                    conn.run(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    conn.run(f"RELEASE SAVEPOINT {savepoint}")
                except Exception:
                    pass
            evidence[query_id] = {
                "state": "Error",
                "message": f"Query {query_id} could not be collected: {exc}",
            }
    return evidence


def _query_section(
    title: str,
    evidence: dict[str, dict[str, Any]],
    query_id: str,
    limit: int | None = None,
) -> dict[str, Any]:
    result = evidence[query_id]
    if result["state"] != "Collected":
        return {
            "title": title,
            "query_id": query_id,
            "state": result["state"],
            "message": result["message"],
        }
    rows = result.get("rows", [])
    selected_rows = rows[:limit] if limit else rows
    columns = visible_columns(selected_rows[0]) if selected_rows else []
    return {
        "title": title,
        "query_id": query_id,
        "state": "Collected",
        "rows": selected_rows,
        "columns": columns,
    }


def _statement_section(
    title: str,
    evidence: dict[str, dict[str, Any]],
    query_id: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Build a statement section with explicit counter-window evidence."""
    section = _query_section(title, evidence, query_id, limit)
    reset_evidence = evidence.get("6.9", {})
    if reset_evidence.get("state") == "Collected":
        rows = reset_evidence.get("rows", [])
        reset_value = rows[0].get("stats_reset") if rows else None
        if reset_value:
            window = f"pg_stat_statements counters observed since {reset_value}."
        else:
            window = "pg_stat_statements reset time was returned without a value."
    else:
        state = reset_evidence.get("state", "Not collected")
        message = reset_evidence.get("message", "reset time unavailable")
        window = f"pg_stat_statements reset evidence is {state}: {message}."
    section["statement_statistics_window"] = (
        f"{window} Statements issued by the current dedicated diagnostic role are "
        "excluded to reduce self-observation; this also omits application traffic if "
        "that role is reused."
    )
    return section


def _describe_log_total(
    rds_client: Any,
    instance_id: str,
    deadline: float | None = None,
) -> dict[str, Any]:
    if deadline is not None and monotonic() >= deadline:
        return {
            "title": "Total Size of Log Files",
            "state": "Not collected",
            "message": "The report collection time budget was exhausted before log metadata collection.",
        }
    try:
        files: list[dict[str, Any]] = []
        marker = ""
        while True:
            if deadline is not None and monotonic() >= deadline:
                return {
                    "title": "Total Size of Log Files",
                    "state": "Not collected",
                    "message": "The report collection time budget was exhausted during log metadata pagination.",
                }
            request: dict[str, Any] = {"DBInstanceIdentifier": instance_id}
            if marker:
                request["Marker"] = marker
            response = rds_client.describe_db_log_files(**request)
            files.extend(response.get("DescribeDBLogFiles", []))
            marker = str(response.get("Marker", ""))
            if not marker:
                break
        total = sum(int(item.get("Size", 0)) for item in files)
        return {
            "title": "Total Size of Log Files",
            "state": "Collected",
            "rows": [{"Log file count": len(files), "Total bytes": total}],
        }
    except Exception as exc:
        return {
            "title": "Total Size of Log Files",
            "state": "Error",
            "message": f"Log metadata could not be collected: {exc}",
        }


def _metric_average(
    cloudwatch_client: Any,
    instance_id: str,
    metric_name: str,
    minutes: int,
    now: datetime,
) -> Any:
    response = cloudwatch_client.get_metric_statistics(
        Namespace="AWS/RDS",
        MetricName=metric_name,
        Dimensions=[{"Name": "DBInstanceIdentifier", "Value": instance_id}],
        StartTime=now - timedelta(minutes=minutes),
        EndTime=now,
        Period=cloudwatch_period_seconds(minutes),
        Statistics=["Average"],
    )
    points = response.get("Datapoints", [])
    if not points:
        return "No data"
    return round(sum(float(point["Average"]) for point in points) / len(points), 2)


def _health_metrics(
    cloudwatch_client: Any,
    instance_id: str,
    now: datetime,
    deadline: float | None = None,
) -> dict[str, Any]:
    metric_names = (
        "CPUUtilization",
        "FreeableMemory",
        "ReadIOPS",
        "WriteIOPS",
        "DatabaseConnections",
    )
    windows = ((1440, "Last 1 Day (Avg)"), (21600, "Last 15 Days (Avg)"), (50400, "Last 35 Days (Avg)"))
    rows = []
    successful_windows = 0
    error_windows = 0
    unavailable_windows = 0
    for metric_name in metric_names:
        row: dict[str, Any] = {"Metric": metric_name}
        for minutes, label in windows:
            if deadline is not None and monotonic() >= deadline:
                row[label] = "Not collected: report collection time budget exhausted"
                unavailable_windows += 1
                continue
            try:
                value = _metric_average(cloudwatch_client, instance_id, metric_name, minutes, now)
                if metric_name == "FreeableMemory" and isinstance(value, (int, float)):
                    value = f"{value / (1024 ** 2):.2f} MiB"
                elif metric_name == "CPUUtilization" and isinstance(value, (int, float)):
                    value = f"{value:.2f}%"
                row[label] = value
                if value == "No data":
                    unavailable_windows += 1
                else:
                    successful_windows += 1
            except Exception as exc:
                row[label] = f"Error: {exc}"
                error_windows += 1
        rows.append(row)
    total_windows = len(metric_names) * len(windows)
    if successful_windows == 0:
        state = "Error" if error_windows else "Not collected"
        message = (
            f"No CloudWatch metric window was collected: {error_windows} error(s), "
            f"{unavailable_windows} unavailable/no-data window(s) out of {total_windows}."
        )
        return {
            "title": "Infrastructure Metrics (CloudWatch)",
            "state": state,
            "message": message,
            "rows": rows,
            "collection_summary": {
                "successful": successful_windows,
                "errors": error_windows,
                "unavailable": unavailable_windows,
                "total": total_windows,
            },
        }
    return {
        "title": "Infrastructure Metrics (CloudWatch)",
        "state": "Collected",
        "rows": rows,
        "collection_summary": {
            "successful": successful_windows,
            "errors": error_windows,
            "unavailable": unavailable_windows,
            "total": total_windows,
        },
    }


def _focused_parameter_section(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Expose only the key-parameter list pinned by the reference toolkit."""
    section = _query_section("Key PostgreSQL Parameters", evidence, "2.3")
    if section.get("state") != "Collected":
        return section
    by_name = {
        str(row.get("name")): row
        for row in section.get("rows") or []
        if row.get("name") is not None
    }
    section["rows"] = [
        by_name.get(
            name,
            {
                "name": name,
                "setting": "Not available on this engine/version",
                "unit": "",
                "pg_settings_source": "Not available",
                "pg_settings_context": "Not available",
                "short_desc": "The reference parameter is not exposed by this engine/version.",
            },
        )
        for name in REFERENCE_KEY_PARAMETERS
    ]
    section["columns"] = [
        "name",
        "setting",
        "unit",
        "pg_settings_source",
        "pg_settings_context",
        "short_desc",
    ]
    return section


def _evidence_note(section: dict[str, Any]) -> str:
    """Build one deterministic, object-aware evidence insight per section."""
    title = str(section.get("title", "Evidence"))
    state = str(section.get("state", "Collected"))
    base_note = HEALTH_NOTES.get(
        title,
        "Interpret this evidence with workload history and recent changes before proposing action.",
    )
    if state != "Collected":
        return (
            f"{title} evidence is {state}: {section.get('message') or state}. "
            "Collect the missing evidence before drawing a conclusion or proposing a change."
        )

    rows = section.get("rows") if "rows" in section else None
    if rows is None:
        return base_note
    rows = rows or []
    if not rows:
        empty_messages = {
            "Invalid Indexes": "No invalid indexes were observed in this snapshot.",
            "Sequences Nearing Exhaustion": "No sequences met the exhaustion-review threshold in this snapshot.",
            "Potential Duplicate Index Candidates": "No potential duplicate-index groups were observed in this snapshot.",
        }
        return f"{empty_messages.get(title, 'No matching objects were observed in this snapshot.')} {base_note}"

    def qualified(row: dict[str, Any]) -> str:
        schema = row.get("table_schema") or row.get("schema_name") or row.get("schemaname")
        name = row.get("table_name") or row.get("tablename") or row.get("relname")
        return f"{schema}.{name}" if schema and name else str(name or schema or "unknown object")

    def bytes_text(value: Any) -> str:
        try:
            amount = float(value)
        except (TypeError, ValueError):
            return str(value)
        units = ("bytes", "KiB", "MiB", "GiB", "TiB")
        unit = units[0]
        for unit in units:
            if abs(amount) < 1024 or unit == units[-1]:
                break
            amount /= 1024
        return f"{amount:.1f} {unit}"

    if title == "Infrastructure Metrics (CloudWatch)":
        summary = section.get("collection_summary") or {}
        return (
            f"CloudWatch returned {summary.get('successful', 0)} of {summary.get('total', 0)} "
            f"requested metric windows; {summary.get('errors', 0)} failed and "
            f"{summary.get('unavailable', 0)} had no data. {base_note}"
        )
    if title == "Extensions Installed":
        names = ", ".join(str(row.get("name")) for row in rows[:5])
        return f"Installed extensions include {names}. {base_note}"
    if title == "Top 5 Databases Size":
        items = ", ".join(f"{row.get('datname')} ({row.get('size')})" for row in rows[:5])
        return f"Largest returned databases: {items}. {base_note}"
    if title == "Top 10 Biggest Tables":
        items = ", ".join(f"{qualified(row)} ({row.get('total_size')})" for row in rows[:5])
        large = [row for row in rows if float(row.get("total_bytes") or 0) >= 500 * 1024**3]
        priority = [row for row in large if float(row.get("total_bytes") or 0) >= 1024**4]
        if priority:
            names = ", ".join(f"{qualified(row)} ({row.get('total_size')})" for row in priority)
            threshold = (
                f"Priority large-table architecture review: {names} exceed 1 TiB. "
                "Assess partition-key alignment, pruning, retention, vacuum/index maintenance, "
                "constraints, growth, WAL, storage headroom, and migration impact. "
            )
        elif large:
            names = ", ".join(f"{qualified(row)} ({row.get('total_size')})" for row in large)
            threshold = (
                f"Large-table operational review: {names} exceed 500 GiB. Consider a "
                "partitioning assessment only when pruning, retention, or maintenance evidence supports it; "
                "partitioning does not guarantee lower IOPS. "
            )
        else:
            threshold = "No returned table crossed the 500 GiB large-table review threshold. "
        return f"Largest returned tables: {items}. {threshold}{base_note}"
    if title == "Tables Without Primary Key":
        items = ", ".join(f"{qualified(row)} ({row.get('table_size')})" for row in rows[:10])
        return f"Tables without primary keys: {items}. {base_note}"
    if title == "Potential Duplicate Index Candidates":
        groups = []
        for row in rows[:5]:
            indexes = row.get("candidate_indexes")
            index_text = ", ".join(map(str, indexes)) if isinstance(indexes, (list, tuple)) else str(indexes)
            groups.append(f"{qualified(row)}: {index_text}")
        return f"Potential duplicate-index groups: {'; '.join(groups)}. {base_note}"
    if title == "Rarely Used Indexes":
        items = ", ".join(
            f"{row.get('schemaname')}.{row.get('index_name')} ({row.get('index_scans')} scans, {row.get('index_size')})"
            for row in rows[:5]
        )
        return f"Rarely used index candidates: {items}. {base_note}"
    if title == "Top 10 Most Bloated Tables":
        items = ", ".join(
            f"{qualified(row)} (ratio {row.get('table_bloat_ratio')}, estimated waste {bytes_text(row.get('estimated_table_wasted_bytes'))})"
            for row in rows[:5]
        )
        return f"Highest heuristic table-bloat estimates: {items}. {base_note}"
    if title == "Top 10 Biggest Tables Last Vacuumed":
        items = ", ".join(
            f"{qualified(row)} (autovacuum {row.get('last_autovacuum')}, autoanalyze {row.get('last_autoanalyze')})"
            for row in rows[:5]
        )
        return f"Largest-table maintenance evidence: {items}. {base_note}"
    if title == "Top 10 UPDATE/DELETE Tables":
        items = ", ".join(
            f"{qualified(row)} ({row.get('update_pct')}% updates, {row.get('delete_pct')}% deletes, {row.get('total_ops')} operations)"
            for row in rows[:5]
        )
        return f"Highest returned write-activity tables: {items}. {base_note}"
    if title == "Top 10 Read IO Tables":
        items = ", ".join(
            f"{qualified(row)} ({row.get('heap_blks_read')} blocks read, {row.get('hit_percent')}% hit)"
            for row in rows[:5]
        )
        return f"Highest returned table read-I/O objects: {items}. {base_note}"
    if title == "Database Cache Hit Ratio":
        items = ", ".join(
            f"{row.get('database_name')} ({row.get('cache_hit_ratio')}%)" for row in rows[:5]
        )
        return f"Database cache-hit observations: {items}. {base_note}"
    if (title.startswith("Top 10 ") and "Queries" in title) or title == "Top 10 Statements by Total Execution Time":
        items = ", ".join(
            f"fingerprint {row.get('query_fingerprint')} ({row.get('calls')} calls)" for row in rows[:5]
        )
        return f"Highest returned statement candidates: {items}. {base_note}"
    if title == "Key PostgreSQL Parameters":
        unavailable = sum(
            1 for row in rows if str(row.get("setting", "")).startswith("Not available")
        )
        return (
            f"Collected {len(rows) - unavailable} of {len(REFERENCE_KEY_PARAMETERS)} reference settings; "
            f"{unavailable} were unavailable on this engine/version. {base_note}"
        )
    return base_note


def _build_remediations(
    metadata: dict[str, Any], sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Prioritize only findings supported by platform-correct metadata."""
    by_title = {str(section.get("title")): section for section in sections}
    remediations: list[dict[str, Any]] = []
    is_aurora = bool(metadata.get("is_aurora"))
    metadata_scope = str(metadata.get("metadata_scope", "RDS metadata"))

    def add(
        priority: str,
        issue: str,
        evidence: str,
        so_what: str,
        steps: list[str],
        example_command: str,
        validation: str,
        risk_and_approval: str,
        rollback: str,
    ) -> None:
        remediations.append(
            {
                "priority": priority,
                "issue": issue,
                "evidence": evidence,
                "so_what": so_what,
                "steps": steps,
                "example_command": example_command,
                "validation": validation,
                "risk_and_approval": risk_and_approval,
                "rollback": rollback,
            }
        )

    if metadata.get("storage_encrypted") is False:
        snapshot_kind = "cluster snapshot" if is_aurora else "DB snapshot"
        command = (
            "aws rds copy-db-cluster-snapshot --source-db-cluster-snapshot-identifier <snapshot> "
            "--target-db-cluster-snapshot-identifier <encrypted-snapshot> --kms-key-id <kms-key-arn>"
            if is_aurora
            else "aws rds copy-db-snapshot --source-db-snapshot-identifier <snapshot> "
            "--target-db-snapshot-identifier <encrypted-snapshot> --kms-key-id <kms-key-arn>"
        )
        add(
            "High",
            "Storage encryption is disabled",
            f"{metadata_scope} metadata reports StorageEncrypted=False.",
            "Data at rest is not protected by RDS storage encryption, and encryption cannot be enabled in place.",
            [
                f"1) Confirm data classification and KMS requirements. 2) Create a tested {snapshot_kind}. ",
                "3) Copy it with encryption, restore into non-production, validate, and plan a controlled cutover.",
            ],
            command,
            "Confirm StorageEncrypted=True on the restored target and run application/data-integrity checks.",
            "Requires security, data-owner, KMS, outage/cutover, backup-retention, and cost review.",
            "Keep the original database and snapshot unchanged until validation and rollback windows expire.",
        )

    if metadata.get("deletion_protection") is False:
        command = (
            "aws rds modify-db-cluster --db-cluster-identifier <db-cluster-id> --deletion-protection"
            if is_aurora
            else "aws rds modify-db-instance --db-instance-identifier <db-instance-id> --deletion-protection"
        )
        add(
            "High",
            "Deletion protection is disabled",
            f"{metadata_scope} metadata reports DeletionProtection=False.",
            "An authorized but accidental delete operation has fewer safeguards against service interruption and data loss.",
            ["1) Confirm lifecycle automation compatibility. 2) Enable protection through the approved change process."],
            command,
            "Re-read RDS metadata and confirm DeletionProtection=True.",
            "Obtain service-owner approval; automation that intentionally replaces resources may fail while protection is enabled.",
            "Disable deletion protection only through a separately approved lifecycle change.",
        )

    if metadata.get("publicly_accessible") is True:
        add(
            "High",
            "Database instance is publicly accessible",
            "RDS metadata reports PubliclyAccessible=True.",
            "Network exposure increases the attack surface even when security groups restrict current access.",
            [
                "1) Inventory legitimate client paths. 2) Establish private routing and DNS. ",
                "3) Test connectivity in non-production before changing the instance setting.",
            ],
            "aws rds modify-db-instance --db-instance-identifier <db-instance-id> --no-publicly-accessible",
            "Confirm private clients connect successfully and RDS metadata reports PubliclyAccessible=False.",
            "Network, application, and security-owner approval is required because incorrect routing can cause an outage.",
            "Restore the prior connectivity design only under an approved incident/change plan; retain tested private paths.",
        )

    backup_retention = metadata.get("backup_retention_period")
    if isinstance(backup_retention, int) and backup_retention == 0:
        command = (
            "aws rds modify-db-cluster --db-cluster-identifier <db-cluster-id> --backup-retention-period <days>"
            if is_aurora
            else "aws rds modify-db-instance --db-instance-identifier <db-instance-id> --backup-retention-period <days>"
        )
        add(
            "High",
            "Automated backups are disabled",
            "RDS metadata reports BackupRetentionPeriod=0.",
            "Point-in-time recovery is unavailable, increasing recovery risk after corruption or operator error.",
            ["1) Confirm recovery objectives and retention policy. 2) Select an approved retention period and backup window."],
            command,
            "Confirm retention metadata, observe a successful automated backup, and test restore procedures.",
            "Data-owner approval, storage-cost review, and backup-window impact assessment are required.",
            "Reverting retention removes future recovery coverage; do so only under an approved policy exception.",
        )

    candidate_actions = (
        (
            "Invalid Indexes",
            "Medium",
            "Invalid indexes require investigation",
            "Invalid indexes may not support queries or constraints as intended.",
            "SELECT n.nspname, c.relname FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE NOT i.indisvalid;",
            "Confirm index ownership, constraint dependencies, build history, storage, and workload before choosing a concurrent rebuild strategy.",
            "Re-run the invalid-index query and verify representative query plans after an approved repair.",
            "A rebuild consumes I/O, CPU, storage, and can still require locks; obtain DBA/application approval and a change window.",
            "Retain the original definition and use the approved index-recovery plan; do not drop the original until replacement validation succeeds.",
        ),
        (
            "Sequences Nearing Exhaustion",
            "Medium",
            "Sequence utilization requires capacity review",
            "The source query reports sequences above 30% utilization; this is an early-review signal, not proof of imminent exhaustion without growth-rate evidence.",
            "SELECT schemaname AS schema_name, sequencename AS sequence_name, data_type, last_value, max_value, ROUND(100.0 * last_value / max_value, 2) AS pct_used FROM pg_sequences WHERE last_value IS NOT NULL AND ROUND(100.0 * last_value / max_value, 2) > 30 ORDER BY pct_used DESC LIMIT 10;",
            "Map each sequence to its column and application contract, measure growth rate and headroom, then test a bigint/type migration or replacement only when projected exhaustion justifies it.",
            "Re-run the same sequence-headroom query and exercise insert paths in non-production.",
            "Schema and application-owner approval is required; type changes may lock tables or break clients.",
            "Preserve the previous schema definition and use a tested migration rollback or restore plan.",
        ),
        (
            "Tables Without Primary Key",
            "Medium",
            "Tables without primary keys require design review",
            "Missing stable row identity can complicate logical replication and deterministic updates.",
            "SELECT n.nspname AS schema_name, c.relname AS table_name, pg_size_pretty(pg_total_relation_size(c.oid)) AS table_size FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid=c.oid AND contype='p') ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 15;",
            "Confirm application uniqueness semantics and duplicate data, design the key, and test lock/duration behavior before adding a constraint.",
            "Validate uniqueness, application writes, replicas, and query plans after the approved change.",
            "Adding a key can scan or lock a large table; application and DBA approval plus rollback planning are required.",
            "Retain the prior schema and use a tested constraint-removal path only if application validation fails.",
        ),
    )
    for title, priority, issue, so_what, command, steps, validation, risk, rollback in candidate_actions:
        rows = by_title.get(title, {}).get("rows") or []
        if rows:
            add(
                priority,
                issue,
                f"The {title} section returned {len(rows)} candidate row(s).",
                so_what,
                [steps],
                command,
                validation,
                risk,
                rollback,
            )

    priority_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Review": 4}
    return sorted(
        remediations,
        key=lambda item: (
            priority_rank.get(str(item.get("priority")), 5),
            str(item.get("issue", "")),
        ),
    )[:5]


def _build_assessment_remediations(
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project the highest-priority inert assessments into the legacy summary."""
    priority_rank = {
        "Critical": 0,
        "High": 1,
        "Medium": 2,
        "Low": 3,
        "Review": 4,
        "Informational": 5,
    }
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for section_number, section in enumerate(sections):
        assessment = section.get("assessment") or {}
        priority = str(assessment.get("Priority", "Informational"))
        proposed = str(assessment.get("Proposed changes", NO_CHANGE))
        if priority not in {"Critical", "High", "Medium"} or proposed == NO_CHANGE:
            continue
        title = str(section.get("title") or "Finding requires review")
        candidates.append(
            (
                priority_rank[priority],
                section_number,
                {
                    "priority": priority,
                    "issue": title,
                    "evidence": str(assessment.get("Finding")),
                    "so_what": str(assessment.get("Why it matters")),
                    "steps": [str(assessment.get("Recommendation")), proposed],
                    "example_command": (
                        "No command proposed; implement only through an approved change plan"
                    ),
                    "validation": str(assessment.get("Validation required")),
                    "risk_and_approval": (
                        f"{assessment.get('Limitations')} Owner approval, non-production "
                        "validation, and an approved change window are required."
                    ),
                    "rollback": (
                        "Define and test an object-specific rollback before implementation; "
                        "no change was executed by this report."
                    ),
                },
            )
        )
    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    return [candidate[2] for candidate in candidates[:5]]


def build_health_report(
    *,
    conn: Any,
    query_allowlist: dict[str, dict[str, dict]],
    execute_query: Callable[[Any, str], list[dict]],
    rds_client: Any,
    cloudwatch_client: Any,
    instance_id: str,
    instance_endpoint: str,
    database: str,
    report_name: str,
    deadline: float | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Collect the complete health plan into one shared structured model."""
    current_time = now or datetime.now(timezone.utc)
    collection_deadline = deadline or (monotonic() + 90)
    if monotonic() >= collection_deadline:
        raise TimeoutError("The report deadline expired before instance metadata collection.")
    instance_response = rds_client.describe_db_instances(DBInstanceIdentifier=instance_id)
    inst = instance_response["DBInstances"][0]
    metadata = normalize_instance_metadata(rds_client, inst)
    effective_report_name = resolve_report_name(
        report_name, inst, instance_id, "health"
    )
    query_ids = [
        "1.2", "1.3", "1.4", "2.3", "3.1", "5.4", "5.5", "6.1",
        "6.5", "6.6", "6.7", "6.8", "6.9", "7.4", "8.2", "8.4", "10.6",
        "11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7",
    ]
    evidence = _query_evidence(
        conn,
        query_allowlist,
        query_ids,
        execute_query,
        deadline=collection_deadline,
    )

    def collected_rows(query_id: str) -> list[dict[str, Any]]:
        result = evidence[query_id]
        return result.get("rows", []) if result.get("state") == "Collected" else []

    settings = {
        str(row.get("name")): row.get("setting")
        for row in collected_rows("2.3")
        if row.get("name") is not None
    }
    uptime_rows = collected_rows("1.2")
    uptime = uptime_rows[0].get("uptime", "Not collected") if uptime_rows else "Not collected"
    connection_rows = collected_rows("3.1")
    try:
        current_connections: Any = sum(int(row.get("count", 0)) for row in connection_rows)
        idle_connections: Any = sum(
            int(row.get("count", 0))
            for row in connection_rows
            if str(row.get("state", "")).lower() == "idle"
        )
    except (TypeError, ValueError):
        current_connections = "Error interpreting connection evidence"
        idle_connections = "Error interpreting connection evidence"

    encryption_label = (
        "Storage Encrypted (Aurora DB cluster)"
        if metadata["is_aurora"]
        else "Storage Encrypted (DB instance)"
    )
    deletion_label = (
        "Deletion Protection (Aurora DB cluster)"
        if metadata["is_aurora"]
        else "Deletion Protection (DB instance)"
    )
    instance_rows = [
        {"Property": "Instance ID", "Value": instance_id},
        {"Property": "Postgres Endpoint URL", "Value": instance_endpoint},
        {"Property": "Database Name", "Value": database},
        {"Property": "PostgreSQL Engine Version", "Value": f"{inst.get('Engine', 'Unknown')} {inst.get('EngineVersion', '')}".strip()},
        {"Property": "Server Uptime", "Value": uptime},
        {"Property": "Maximum Connections", "Value": settings.get("max_connections", "Not collected")},
        {"Property": "Current Total Connections", "Value": current_connections},
        {"Property": "Idle Connections", "Value": idle_connections},
        {"Property": "DB Instance Class", "Value": inst.get("DBInstanceClass", "Not collected")},
        {"Property": "Storage Allocation", "Value": metadata["storage_allocation"]},
        {"Property": "Storage Autoscaling", "Value": metadata["storage_autoscaling"]},
        {"Property": "Storage Type", "Value": metadata["storage_type"]},
        {"Property": "Backup Retention Period", "Value": metadata["backup_retention_period"]},
        {"Property": "Preferred Backup Window", "Value": metadata["preferred_backup_window"]},
        {"Property": "EM Monitoring Interval", "Value": inst.get("MonitoringInterval", "Not collected")},
        {"Property": "Availability / Multi-AZ", "Value": metadata["availability"]},
        {"Property": "Publicly Accessible (DB instance)", "Value": inst.get("PubliclyAccessible", "Not collected")},
        {"Property": encryption_label, "Value": metadata["storage_encrypted"]},
        {"Property": deletion_label, "Value": metadata["deletion_protection"]},
        {"Property": "Infrastructure Metadata Scope", "Value": metadata["metadata_scope"]},
    ]

    sections = [
        {"title": "Date", "state": "Collected", "value": current_time.strftime("%b %d, %Y %H:%M UTC")},
        {"title": "Instance Details", "state": "Collected", "rows": instance_rows, "layout": "lines"},
        _health_metrics(
            cloudwatch_client,
            instance_id,
            current_time,
            deadline=collection_deadline,
        ),
        _query_section("Extensions Installed", evidence, "10.6"),
        _describe_log_total(
            rds_client,
            instance_id,
            deadline=collection_deadline,
        ),
        _query_section("Maximum Used Transaction IDs", evidence, "11.4", 1),
        _query_section("Total Size of All Databases", evidence, "1.4"),
        _query_section("Top 5 Databases Size", evidence, "1.3", 5),
        _query_section("Top 10 Biggest Tables", evidence, "5.4"),
        _query_section("Tables Without Primary Key", evidence, "11.1"),
        _query_section("Potential Duplicate Index Candidates", evidence, "8.2"),
        _query_section("Rarely Used Indexes", evidence, "8.4"),
        _query_section("Invalid Indexes", evidence, "11.2"),
        _query_section("Top 5 Database Age", evidence, "11.4", 5),
        _query_section("Top 5 Table age", evidence, "11.5", 5),
        _query_section("Sequences Nearing Exhaustion", evidence, "11.3"),
        _query_section("Top 10 Most Bloated Tables", evidence, "5.5"),
        _query_section("Top 10 Biggest Tables Last Vacuumed", evidence, "7.4"),
        _query_section("Top 10 UPDATE/DELETE Tables", evidence, "11.6"),
        _focused_parameter_section(evidence),
        _query_section("Top 10 Read IO Tables", evidence, "11.7"),
        _query_section("Database Cache Hit Ratio", evidence, "6.5"),
        _statement_section("Top 10 Statements by Total Execution Time", evidence, "6.1", 10),
        _statement_section("Top 10 Read I/O Queries", evidence, "6.6"),
        _statement_section("Top 10 Temporary Space Written Queries", evidence, "6.7"),
        _statement_section("Top 10 Temporary Space Read Queries", evidence, "6.8"),
    ]
    for section in sections:
        section["note"] = _evidence_note(section)
        statistics_window = section.get("statement_statistics_window")
        if statistics_window:
            section["note"] = f"{section['note']} {statistics_window}"
    assessment_metrics = attach_automated_assessments(sections)
    return {
        "report_name": effective_report_name,
        "sections": sections,
        "assessment_metrics": assessment_metrics,
        "remediations": _build_assessment_remediations(sections),
    }


def build_health_html(**kwargs: Any) -> str:
    """Collect once and render the complete health report as HTML."""
    return render_health_report(build_health_report(**kwargs))


def build_health_markdown(**kwargs: Any) -> str:
    """Collect once and render concise complete health coverage for chat."""
    return render_health_markdown(build_health_report(**kwargs))


def _result_check(
    number: int,
    result: dict[str, Any],
    *,
    empty_state: str = "Pass",
    populated_state: str = "Manual review",
    empty_message: str = "No rows returned.",
    populated_message: str = "Evidence rows require manual review.",
) -> dict[str, Any]:
    if result["state"] != "Collected":
        return {"number": number, "state": result["state"], "message": result["message"]}
    rows = result.get("rows", [])
    check = {
        "number": number,
        "state": populated_state if rows else empty_state,
        "message": populated_message if rows else empty_message,
    }
    if rows:
        check["rows"] = rows
    return check


def build_upgrade_html(
    *,
    conn: Any,
    query_allowlist: dict[str, dict[str, dict]],
    execute_query: Callable[[Any, str], list[dict]],
    rds_client: Any,
    cloudwatch_client: Any,
    inst: dict[str, Any],
    instance_id: str,
    instance_endpoint: str,
    database: str,
    allowed_databases: set[str],
    target_major_version: int,
    report_name: str,
    target_versions: list[str],
    valid_upgrade_versions: list[str],
    target_discovery_error: str,
    instance_class_orderable: bool | None,
    pending_actions: list[str] | None,
    deadline: float | None = None,
    now: datetime | None = None,
) -> str:
    """Collect category-10 evidence in one connection and render all 18 checks."""
    current_time = now or datetime.now(timezone.utc)
    collection_deadline = deadline or (monotonic() + 90)
    effective_report_name = resolve_report_name(
        report_name,
        inst,
        instance_id,
        "pre-upgrade",
        target_major_version,
    )
    query_ids = [
        "1.4", "2.1", "10.1", "10.2", "10.3", "10.4", "10.5", "10.6",
        "10.7", "10.8", "10.9", "10.10", "10.11", "10.12",
    ]
    evidence = _query_evidence(
        conn,
        query_allowlist,
        query_ids,
        execute_query,
        deadline=collection_deadline,
    )
    current_version = str(inst.get("EngineVersion", "Unknown"))
    current_major = int(current_version.split(".")[0]) if current_version[:1].isdigit() else 0

    exact_targets = ", ".join(target_versions) or "none"
    all_targets = ", ".join(valid_upgrade_versions) or "none returned"
    if target_discovery_error:
        check1 = {
            "number": 1,
            "state": "Not collected",
            "message": (
                "Target-version availability could not be verified: "
                f"{target_discovery_error}."
            ),
        }
    elif target_versions:
        check1 = {
            "number": 1,
            "state": "Pass",
            "message": (
                f"Exact valid RDS upgrade targets for major {target_major_version}: "
                f"{exact_targets}."
            ),
        }
    else:
        check1 = {
            "number": 1,
            "state": "Fail",
            "message": (
                f"Major {target_major_version} was not listed as a valid RDS upgrade "
                f"target. RDS returned these exact targets: {all_targets}."
            ),
        }

    instance_class = inst.get("DBInstanceClass", "Unknown")
    if instance_class_orderable is True:
        check2 = {
            "number": 2,
            "state": "Pass",
            "message": f"Current class {instance_class} is orderable for at least one exact target engine version returned by RDS in this Region.",
        }
    elif instance_class_orderable is False:
        check2 = {
            "number": 2,
            "state": "Fail",
            "message": f"Current class {instance_class} was not orderable for the exact target engine versions returned by RDS in this Region.",
        }
    else:
        check2 = {
            "number": 2,
            "state": "Not collected",
            "message": f"Current class {instance_class} was observed, but exact target-version orderability could not be verified.",
        }
    checks = [
        check1,
        check2,
        _result_check(3, evidence["10.1"], populated_state="Fail", populated_message="Open prepared transactions were observed; coordinate owner-reviewed resolution before upgrade."),
        _result_check(4, evidence["10.2"], populated_state="Fail", populated_message="Unsupported reg* columns were observed in the connected database."),
        _result_check(5, evidence["10.3"], populated_state="Fail", populated_message="Logical replication slots were observed. Confirm ownership and an approved migration plan; no slot action is automatic."),
    ]

    total_size = evidence["1.4"]
    storage_rows = total_size.get("rows", []) if total_size["state"] == "Collected" else []
    if monotonic() >= collection_deadline:
        check6 = {
            "number": 6,
            "state": "Not collected",
            "message": "The report collection time budget was exhausted before storage metrics collection.",
            "rows": storage_rows,
        }
    else:
        try:
            if inst.get("Engine") == "aurora-postgresql":
                cluster_id = str(inst.get("DBClusterIdentifier", ""))
                if not cluster_id:
                    raise ValueError("Aurora DBClusterIdentifier was unavailable")
                metric = cloudwatch_client.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="VolumeBytesUsed",
                    Dimensions=[
                        {"Name": "DBClusterIdentifier", "Value": cluster_id}
                    ],
                    StartTime=current_time - timedelta(minutes=5),
                    EndTime=current_time,
                    Period=300,
                    Statistics=["Average"],
                )
                points = sorted(
                    metric.get("Datapoints", []),
                    key=lambda point: point.get("Timestamp", current_time),
                )
                volume_used = points[-1]["Average"] if points else "No data"
                row = {
                    "aurora_cluster": cluster_id,
                    "volume_bytes_used": volume_used,
                    "storage_allocation": "Aurora managed; instance FreeStorageSpace percentage is not applicable",
                }
                storage_rows = [dict(storage_rows[0], **row)] if storage_rows else [row]
                check6 = {
                    "number": 6,
                    "state": "Manual review",
                    "message": (
                        "Aurora VolumeBytesUsed evidence was requested at cluster scope. "
                        "Review current Aurora volume limits and exact upgrade-path "
                        "requirements; no instance allocated-storage percentage is inferred."
                    ),
                    "rows": storage_rows,
                }
            else:
                metric = cloudwatch_client.get_metric_statistics(
                    Namespace="AWS/RDS",
                    MetricName="FreeStorageSpace",
                    Dimensions=[
                        {"Name": "DBInstanceIdentifier", "Value": instance_id}
                    ],
                    StartTime=current_time - timedelta(minutes=5),
                    EndTime=current_time,
                    Period=300,
                    Statistics=["Average"],
                )
                points = metric.get("Datapoints", [])
                free_storage = points[-1]["Average"] if points else "No data"
                row = {"free_storage_bytes": free_storage}
                storage_rows = [dict(storage_rows[0], **row)] if storage_rows else [row]
                check6 = {
                    "number": 6,
                    "state": "Manual review",
                    "message": (
                        "RDS instance storage evidence was collected; validate required "
                        "headroom for the exact upgrade path."
                    ),
                    "rows": storage_rows,
                }
        except Exception as exc:
            check6 = {
                "number": 6,
                "state": "Error",
                "message": f"Storage evidence could not be completed: {exc}",
                "rows": storage_rows,
            }
    checks.append(check6)

    settings = evidence["2.1"]
    checks.append({
        "number": 7,
        "state": "Manual review" if settings["state"] == "Collected" else settings["state"],
        "message": (
            "Effective live settings were collected, but they do not prove AWS parameter provenance or engine defaults. "
            "No shared_buffers percentage, target, reset, or reboot action is inferred."
            if settings["state"] == "Collected" else settings["message"]
        ),
    })
    checks.extend([
        _result_check(8, evidence["10.4"], populated_state="Fail", populated_message="Unknown data types were observed in the connected database."),
    ])

    if inst.get("Engine") == "aurora-postgresql":
        check9 = {"number": 9, "state": "Manual review", "message": "Aurora reader topology requires coordinated upgrade planning. No reader action is automatic."}
    else:
        check9 = {
            "number": 9,
            "state": "Manual review" if inst.get("ReadReplicaDBInstanceIdentifiers") else "Pass",
            "message": "Read replicas require coordinated upgrade planning; non-allowlisted identifiers are omitted." if inst.get("ReadReplicaDBInstanceIdentifiers") else "No read replicas were reported.",
        }
    checks.append(check9)
    checks.extend([
        _result_check(10, evidence["10.6"], empty_state="Pass", populated_state="Manual review", populated_message="Installed extensions require target-version compatibility review."),
        _result_check(11, evidence["10.8"], empty_state="Not collected", populated_state="Manual review", populated_message="Current-role evidence was collected; object-level access still requires manual validation."),
        _result_check(12, evidence["10.5"], populated_state="Fail", populated_message="sql_identifier usage was observed in the connected database."),
        _result_check(13, evidence["10.7"], empty_state="Pass", populated_state="Manual review", populated_message="Visible user views require manual dependency review; inventory alone does not prove a catalog dependency."),
    ])
    primary_user = str(inst.get("MasterUsername", ""))
    checks.append({
        "number": 14,
        "state": "Fail" if primary_user.startswith("pg_") else ("Pass" if primary_user else "Not collected"),
        "message": "The configured primary username starts with pg_." if primary_user.startswith("pg_") else ("The configured primary username does not start with pg_." if primary_user else "Primary username was unavailable."),
    })
    checks.append(_result_check(15, evidence["10.9"], populated_state="Manual review", populated_message="GiST indexes were observed and require version-pair compatibility review."))
    if target_major_version >= 16:
        checks.append(_result_check(16, evidence["10.10"], populated_state="Manual review", populated_message="User-created ICU collations were observed and require version-specific review."))
    else:
        checks.append({"number": 16, "state": "Not applicable", "message": "The selected target is earlier than PostgreSQL 16."})
    if target_major_version >= 17:
        checks.append(_result_check(17, evidence["10.11"], populated_state="Manual review", populated_message="Objects matching the pinned sample's PostgreSQL 17 reserved-name review list were observed."))
    else:
        checks.append({"number": 17, "state": "Not applicable", "message": "The selected target is earlier than PostgreSQL 17."})
    if pending_actions is None:
        checks.append({"number": 18, "state": "Not collected", "message": "Pending maintenance actions could not be queried."})
    elif pending_actions:
        checks.append({"number": 18, "state": "Manual review", "message": "Pending maintenance actions were observed and should be reviewed separately.", "rows": [{"Action": action} for action in pending_actions]})
    else:
        checks.append({"number": 18, "state": "Pass", "message": "No pending maintenance actions were reported."})

    database_summary = [
        {
            "Database": name,
            "Evidence state": "Collected" if name.lower() == database.lower() else "Not collected",
            "Scope": (
                "Database-local checks for this connection plus cluster-wide catalog "
                "checks where explicitly identified"
                if name.lower() == database.lower()
                else "Database-local checks not collected; cluster-wide evidence may still apply"
            ),
        }
        for name in sorted(allowed_databases)
    ]
    live_settings = {
        str(row.get("name")): row.get("setting")
        for row in evidence["2.1"].get("rows", [])
        if row.get("name") is not None
    }

    def setting_observation(name: str) -> str:
        value = live_settings.get(name)
        return f"Observed live value: {value}." if value is not None else "Live value was not collected."

    considerations = [
        {
            "Pinned section": "Release-note scope",
            "Evidence state": "Manual review",
            "Consideration": f"Review PostgreSQL release notes for every major version from {current_major} through {target_major_version}.",
        }
    ]
    if current_major <= 13 and target_major_version >= 14:
        considerations.extend([
            {
                "Pinned section": "18a. password_encryption default changes (md5 → scram-sha-256 in PG14)",
                "Evidence state": "Manual review",
                "Consideration": f"Review authentication and client compatibility. {setting_observation('password_encryption')}",
            },
            {
                "Pinned section": "18b. Removed parameter: vacuum_cleanup_index_scale_factor (removed in PG14)",
                "Evidence state": "Manual review",
                "Consideration": f"Review parameter-family migration behavior. {setting_observation('vacuum_cleanup_index_scale_factor')}",
            },
        ])
    if current_major <= 14 and target_major_version >= 15:
        considerations.append({
            "Pinned section": "18c. hash_mem_multiplier default changes (1.0 → 2.0 in PG15)",
            "Evidence state": "Manual review",
            "Consideration": f"Review workload-sensitive memory behavior without applying a universal target. {setting_observation('hash_mem_multiplier')}",
        })
    if current_major <= 17 and target_major_version >= 18:
        considerations.append({
            "Pinned section": "18d. PostgreSQL 18 parallel-query behavior review",
            "Evidence state": "Manual review",
            "Consideration": f"Verify target-engine defaults and review parallel-query plans on a clone; no default value is assumed. {setting_observation('max_parallel_workers_per_gather')}",
        })
    if current_major <= 15 and target_major_version >= 16:
        considerations.extend([
            {
                "Pinned section": "18d-i. PostgreSQL 16 ICU collation version tracking",
                "Evidence state": "Manual review",
                "Consideration": "Review indexes using ICU collations and validate collation versions after clone testing.",
            },
            {
                "Pinned section": "18d-ii. New parameter in PG16: vacuum_buffer_usage_limit (default 256kB)",
                "Evidence state": "Manual review",
                "Consideration": f"Review existing vacuum tuning in workload context. {setting_observation('vacuum_buffer_usage_limit')}",
            },
        ])
    if target_major_version >= 16:
        logical_slot_evidence = evidence["10.3"]
        logical_slots = logical_slot_evidence.get("rows", [])
        if logical_slot_evidence["state"] != "Collected":
            logical_state = logical_slot_evidence["state"]
            logical_message = logical_slot_evidence.get("message", "Logical-slot evidence was not collected.")
        elif logical_slots:
            logical_state = "Manual review"
            logical_message = "Logical slots were observed; coordinate subscriber and slot health validation."
        else:
            logical_state = "Pass"
            logical_message = "No logical replication slots were observed in the connected evidence."
        considerations.append({
            "Pinned section": "18d-iii. Logical replication behavior change in PG16",
            "Evidence state": logical_state,
            "Consideration": logical_message,
        })
    if current_major <= 16 and target_major_version >= 17:
        considerations.append({
            "Pinned section": "18d-iv. PostgreSQL 17 behavioral changes",
            "Evidence state": "Manual review",
            "Consideration": "Review PostgreSQL 17 I/O, incremental-backup, WAL-summary, and query-identifier changes against monitoring and workload baselines.",
        })
    pending_restart_evidence = evidence["10.12"]
    pending_restart_rows = pending_restart_evidence.get("rows", [])
    if pending_restart_evidence["state"] != "Collected":
        pending_restart_state = pending_restart_evidence["state"]
        pending_restart_message = pending_restart_evidence.get(
            "message", "Pending-restart evidence was not collected."
        )
    elif pending_restart_rows:
        pending_restart_state = "Manual review"
        pending_restart_message = "Pending-restart settings were observed and require review."
    else:
        pending_restart_state = "Pass"
        pending_restart_message = "No pending-restart settings were observed in the connected database."
    considerations.extend([
        {
            "Pinned section": "18d-v. Parameter review opportunity (post-upgrade best practice)",
            "Evidence state": "Manual review",
            "Consideration": (
                "Review random_page_cost and effective_io_concurrency against measured workload evidence; "
                f"no fixed target is inferred. {setting_observation('random_page_cost')} "
                f"{setting_observation('effective_io_concurrency')}"
            ),
        },
        {
            "Pinned section": "18e. pg_stat_statements data will be cleared",
            "Evidence state": "Manual review",
            "Consideration": "Capture approved query-performance baselines before upgrade and validate monitoring continuity afterward.",
        },
        {
            "Pinned section": "18f. Check for pending parameter changes (applied during upgrade restart)",
            "Evidence state": pending_restart_state,
            "Consideration": pending_restart_message,
        },
    ])
    details = [{
        "Instance": instance_id,
        "Endpoint": instance_endpoint,
        "Connected database": database,
        "Current version": current_version,
        "Target major version": target_major_version,
        "Exact valid targets for requested major": exact_targets,
        "All valid targets returned by RDS": all_targets,
        "Target discovery error": target_discovery_error or "None",
        "Report date": current_time.strftime("%b %d, %Y %H:%M UTC"),
        "Scope": (
            "Database-local checks cover the connected allowlisted database; "
            "cluster-wide catalog checks are identified separately."
        ),
    }]
    return render_upgrade_report({
        "report_name": effective_report_name,
        "report_details": details,
        "checks": checks,
        "database_summary": database_summary,
        "version_considerations": considerations,
    })
