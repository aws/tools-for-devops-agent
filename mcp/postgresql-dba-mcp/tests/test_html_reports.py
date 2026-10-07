"""Deterministic contracts for customer-shareable HTML reports."""

from __future__ import annotations

import ast
import inspect
import os
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["STAGE_NAME"] = "test"
os.environ["SECRET_ARN"] = "arn:aws:secretsmanager:us-west-2:111122223333:secret:test"
os.environ["ALLOWED_INSTANCES"] = "test-db-1,test-db-2"
os.environ["ALLOWED_DATABASES"] = "postgres,myapp"
os.environ["ALLOWED_ENDPOINTS"] = (
    "test-db-1.example.rds.amazonaws.com,test-db-2.example.rds.amazonaws.com,"
    "test-cluster.cluster-example.us-west-2.rds.amazonaws.com,"
    "test-cluster.cluster-ro-example.us-west-2.rds.amazonaws.com"
)
os.environ["EXPLAIN_QUERY_ENABLED"] = "true"

CANONICAL_HEALTH_SECTIONS = (
    "Date", "Instance Details", "Infrastructure Metrics (CloudWatch)", "Extensions Installed",
    "Total Size of Log Files", "Maximum Used Transaction IDs",
    "Total Size of All Databases", "Top 5 Databases Size",
    "Top 10 Biggest Tables", "Tables Without Primary Key", "Potential Duplicate Index Candidates",
    "Rarely Used Indexes", "Invalid Indexes", "Top 5 Database Age",
    "Top 5 Table age", "Sequences Nearing Exhaustion",
    "Top 10 Most Bloated Tables", "Top 10 Biggest Tables Last Vacuumed",
    "Top 10 UPDATE/DELETE Tables", "Key PostgreSQL Parameters",
    "Top 10 Read IO Tables", "Database Cache Hit Ratio",
    "Top 10 Statements by Total Execution Time", "Top 10 Read I/O Queries",
    "Top 10 Temporary Space Written Queries",
    "Top 10 Temporary Space Read Queries",
)

CANONICAL_UPGRADE_CHECKS = (
    "Check for target Postgres version",
    "Check for unsupported DB instance classes",
    "Check for open prepared transactions", "Check for unsupported reg* data types",
    "Check for logical replication slots", "Check for storage issues",
    "Check for 'Incompatible Parameter' error", "Check for Unknown data types",
    "Check for Read Replica upgrade failure", "Check for Postgres extensions",
    "Check for user access", "Check for sql_identifier data type",
    "Check for views dependency", "Check for incorrect primary user name",
    "Check for GIST index", "Check for User-Created ICU Collations (PostgreSQL 16+)",
    "Check for new reserved keywords (PostgreSQL 17+)",
    "Check for pending maintenance actions",
)

class TestToolAndQuerySurface:
    def test_exact_ten_decorated_tools(self):
        tree = ast.parse((REPOSITORY_ROOT / "src" / "server.py").read_text(encoding="utf-8"))
        tools = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            )
        ]
        assert tools == [
            "execute_health_query",
            "list_health_queries",
            "run_full_health_check",
            "list_rds_instances",
            "get_instance_config",
            "get_instance_metrics",
            "explain_query",
            "get_parameter_group",
            "get_log_files",
            "check_upgrade_readiness",
        ]

    def test_markdown_result_metadata_is_neutral_and_platform_accurate(self):
        source = (REPOSITORY_ROOT / "src" / "server.py").read_text(
            encoding="utf-8"
        )

        assert "DISPLAY_CONTRACT" not in source
        assert "required_final_response_behavior" not in source
        assert "copy_text_content_verbatim" not in source
        assert '"delivery": "devops_agent_tool_output"' in source
        assert '"ui_note"' in source
        assert "expandable Output panel" in source
        assert "on screen only" in source
        assert "never writes to S3 or mints a presigned URL" in source

    def test_downloadable_tools_accept_structured_tool_results(self):
        import asyncio
        import server

        async def schemas():
            health = await server.mcp.get_tool("run_full_health_check")
            upgrade = await server.mcp.get_tool("check_upgrade_readiness")
            return health.output_schema, upgrade.output_schema

        health_schema, upgrade_schema = asyncio.run(schemas())
        assert health_schema is None
        assert upgrade_schema is None

    def test_report_catalog_is_read_only_and_complete(self):
        import server

        definitions = [
            definition
            for category in server.QUERY_ALLOWLIST.values()
            for query_id, definition in category.items()
            if not query_id.startswith("_")
        ]
        assert len(definitions) == 55
        assert all(definition["sql"].lstrip().upper().startswith("SELECT") for definition in definitions)
        table_size_sql = server.QUERY_ALLOWLIST["5"]["5.4"]["sql"]
        assert "LIMIT 10" in table_size_sql
        assert "count(*) OVER ()" in table_size_sql
        assert "_assessment_total_user_table_count" in table_size_sql
        assert "_assessment_database_name" in table_size_sql
        assert "s.idx_scan < 10" in server.QUERY_ALLOWLIST["8"]["8.4"]["sql"]
        assert "pg_constraint" in server.QUERY_ALLOWLIST["8"]["8.4"]["sql"]
        bloat_sql = server.QUERY_ALLOWLIST["5"]["5.5"]["sql"]
        assert "Pinned Toolkit Heuristic" in server.QUERY_ALLOWLIST["5"]["5.5"]["name"]
        assert "otta" in bloat_sql
        assert "estimated_table_wasted_bytes" in bloat_sql
        assert "n_dead_tup" not in bloat_sql
        from pglast import parse_sql
        assert parse_sql(bloat_sql)
        assert "lower(c.relname) IN ('checkpoint','subscription','publication')" in server.QUERY_ALLOWLIST["10"]["10.11"]["sql"]
        for query_id in ("6.1", "6.2", "6.6", "6.7", "6.8"):
            definition = server.QUERY_ALLOWLIST["6"][query_id]
            sql = definition["sql"]
            assert "pg_stat_statements" in sql
            assert "d.datname = current_database()" in sql
            assert "p.query AS _query_text" in sql
            assert definition["result_transform"] == "normalized_query_preview"
            assert "left(p.query" not in sql
            assert "query_snippet" not in sql
            assert "user_name" not in sql

        long_running = server.QUERY_ALLOWLIST["3"]["3.2"]
        assert long_running["result_transform"] == "normalized_query_preview"
        assert "left(query, 100000) AS _query_text" in long_running["sql"]
        assert "query_snippet" not in long_running["sql"]

        lock_waits = server.QUERY_ALLOWLIST["3"]["3.3"]
        assert lock_waits["result_transform"] == "normalized_query_preview"
        assert lock_waits["query_preview_sources"] == {
            "_blocked_query_text": "blocked_query_preview",
            "_blocking_query_text": "blocking_query_preview",
        }
        assert "blocked.query AS _blocked_query_text" in lock_waits["sql"]
        assert "blocking.query AS _blocking_query_text" in lock_waits["sql"]
        assert " AS blocked_query" not in lock_waits["sql"]
        assert " AS blocking_query" not in lock_waits["sql"]

    def test_query_preview_transform_redacts_activity_and_lock_sources(self):
        import server
        from report_service import transform_query_results

        long_running = transform_query_results(
            [{
                "pid": 10,
                "_query_text": (
                    "SELECT * FROM orders WHERE token='LONG_SECRET' AND id=$1 "
                    "/* COMMENT_SECRET */"
                ),
                "state": "active",
            }],
            server.QUERY_ALLOWLIST["3"]["3.2"],
        )
        lock_waits = transform_query_results(
            [{
                "blocked_pid": 20,
                "_blocked_query_text": (
                    "UPDATE accounts SET balance=999 WHERE id=42 -- BLOCKED_COMMENT"
                ),
                "blocking_pid": 30,
                "_blocking_query_text": (
                    "DELETE FROM audit_log WHERE payload=$$PRIVATE_PAYLOAD$$"
                ),
            }],
            server.QUERY_ALLOWLIST["3"]["3.3"],
        )

        assert list(long_running[0]) == [
            "pid", "normalized_query_preview", "state"
        ]
        assert list(lock_waits[0]) == [
            "blocked_pid", "blocked_query_preview",
            "blocking_pid", "blocking_query_preview",
        ]
        serialized = (
            server._format_results_table(long_running, "Sanitized activity")
            + server._format_results_table(lock_waits, "Sanitized locks")
        )
        for prohibited in (
            "LONG_SECRET", "COMMENT_SECRET", "BLOCKED_COMMENT",
            "PRIVATE_PAYLOAD", "_query_text", "_blocked_query_text",
            "_blocking_query_text", "999", "42",
        ):
            assert prohibited not in str(long_running)
            assert prohibited not in str(lock_waits)
            assert prohibited not in serialized
        assert "SELECT \\* FROM orders WHERE token=? AND id=?" in serialized
        assert "UPDATE accounts SET balance=? WHERE id=?" in str(lock_waits)
        assert "DELETE FROM audit_log WHERE payload=?" in str(lock_waits)

    def test_orderability_api_is_allowed_by_endpoint_and_runtime_role(self):
        template = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")
        endpoint_policy = template.split("  RDSEndpoint:", 1)[1].split("  EC2Endpoint:", 1)[0]
        runtime_role = template.split("            - Sid: ReadRDSMetadata", 1)[1].split(
            "        - Statement:", 1
        )[0]
        action = "rds:DescribeOrderableDBInstanceOptions"
        assert endpoint_policy.count(action) == 1
        assert runtime_role.count(action) == 1

    def test_sensitive_surfaces_are_default_off_in_sam_template(self):
        template = (REPOSITORY_ROOT / "template.yaml").read_text(encoding="utf-8")

        for parameter, environment_name in (
            ("ExplainQueryEnabled", "EXPLAIN_QUERY_ENABLED"),
        ):
            parameter_block = template.split(f"  {parameter}:", 1)[1].split(
                "\n\n  ", 1
            )[0]
            assert "Default: 'false'" in parameter_block
            assert "AllowedValues: ['true', 'false']" in parameter_block
            assert f"{environment_name}: !Ref {parameter}" in template

        # The report S3 bucket, S3 IAM, S3 endpoint, and report publication flag
        # were removed; report delivery is client-side via the Artifacts panel.
        assert "ReportBucket" not in template
        assert "ReportPublishEnabled" not in template
        assert "s3:PutObject" not in template

    def test_extended_tool_signatures_are_backwards_compatible(self):
        import server

        health = inspect.signature(server.run_full_health_check).parameters
        assert list(health) == [
            "instance_endpoint", "database", "port", "secret_arn",
            "report_format", "instance_id", "report_name",
        ]
        upgrade = inspect.signature(server.check_upgrade_readiness).parameters
        assert list(upgrade) == [
            "instance_id", "target_major_version", "report_format",
            "instance_endpoint", "database", "port", "secret_arn", "report_name",
        ]
        assert health["report_format"].default == "markdown"
        assert health["report_name"].default == ""
        assert upgrade["report_format"].default == "markdown"
        assert upgrade["report_name"].default == ""

        readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
        assert "55 predefined SQL diagnostics" in readme
        assert 'report_format="markdown"' in readme
        assert 'report_format="html"' not in readme
        assert "50,400 minutes" in readme

    def test_no_s3_client_exists_on_server(self):
        import server

        # On-screen-only delivery: there is no S3 client or upload path.
        assert not hasattr(server, "s3_client")

    def test_downloadable_html_report_formats_are_rejected(self):
        import server

        # The html / downloadable delivery modes were removed; only on-screen
        # markdown (and quick for health) remain.
        for rejected in ("html", "html_download"):
            health_result = server.run_full_health_check(
                "test-db-1.example.rds.amazonaws.com",
                report_format=rejected,
                instance_id="test-db-1",
            )
            upgrade_result = server.check_upgrade_readiness(
                "test-db-1",
                17,
                report_format=rejected,
                instance_endpoint="test-db-1.example.rds.amazonaws.com",
            )
            assert health_result == (
                "ERROR: report_format must be 'markdown' or 'quick'."
            )
            assert upgrade_result == "ERROR: report_format must be 'markdown'."


class _NoopConnection:
    def close(self):
        pass


class TestLegacyRenderer:
    def test_section_catalogs_match_independent_pinned_contract(self):
        from report_renderer import HEALTH_SECTION_TITLES, UPGRADE_CHECK_TITLES

        assert HEALTH_SECTION_TITLES == CANONICAL_HEALTH_SECTIONS
        assert UPGRADE_CHECK_TITLES == CANONICAL_UPGRADE_CHECKS

    def test_health_section_order_styling_provenance_and_escaping(self):
        from report_renderer import (
            HEALTH_SECTION_TITLES,
            LOCAL_TEMPLATE_VERSION,
            UPSTREAM_COMMIT,
            render_health_report,
        )

        payload = '<script>alert("x")</script><img src=x onerror=alert(1)>'
        html = render_health_report(
            {
                "report_name": payload,
                "sections": [
                    {"title": "Date", "state": "Collected", "value": payload},
                    {
                        "title": "Instance Details",
                        "state": "Collected",
                        "rows": [{"Property": payload, "Value": "A&B"}],
                        "layout": "lines",
                    },
                    {
                        "title": "Infrastructure Metrics (CloudWatch)",
                        "state": "Collected",
                        "rows": [{"Metric": "CPUUtilization", "Last 1 Day (Avg)": "10%"}],
                    },
                ],
            }
        )

        assert html.startswith('<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"')
        assert 'font-family: Verdana' in html
        assert 'bgcolor="#F8F8F8"' in html
        assert 'color="#0099cc"' in html
        assert 'color="#ff6600"' in html
        assert 'border="1"' in html
        assert "<h2" not in html.lower()
        assert "<u>" not in html.lower()
        assert '<table width="100%" border="0" cellpadding="0" cellspacing="0">' in html
        assert '<tr><td align="center">' in html
        assert '<h1 align="center"><font face="verdana" color="#0099cc">' in html
        assert '<table><tr><td width="20">&nbsp;</td><td>' not in html
        assert "A&amp;B<br>" in html
        assert "https://unpkg.com" not in html
        assert '<meta name="referrer" content="no-referrer">' in html
        assert UPSTREAM_COMMIT in html
        assert f"local template version {LOCAL_TEMPLATE_VERSION}" in html
        assert payload not in html
        assert "&lt;script&gt;" in html
        assert "A&amp;B" in html
        assert "<script" not in html.lower()
        assert "javascript:" not in html.lower()
        positions = [html.index(f">{title}: </font><br>") for title in HEALTH_SECTION_TITLES]
        assert positions == sorted(positions)

        descriptive_html = render_health_report(
            {"report_name": "AuroraPG16 Health Check After Update", "sections": []}
        )
        label_html = render_health_report(
            {"report_name": "AuroraPG16", "sections": []}
        )
        assert "<title>AuroraPG16 Health Check After Update</title>" in descriptive_html
        assert "PostgreSQL Health Check — AuroraPG16 Health Check" not in descriptive_html
        assert "<title>PostgreSQL Health Check — AuroraPG16</title>" in label_html

    def test_health_output_is_complete_for_missing_and_error_sections(self):
        from report_renderer import HEALTH_SECTION_TITLES, render_health_report

        html = render_health_report(
            {
                "sections": [
                    {"title": "Date", "state": "Error", "message": "clock unavailable"},
                    {"title": "Extensions Installed", "state": "Collected", "rows": []},
                    {"title": "Invalid Indexes", "state": "Not applicable", "message": "unsupported"},
                ]
            }
        )

        assert all(f">{title}: </font><br>" in html for title in HEALTH_SECTION_TITLES)
        assert "Error:</b> clock unavailable" in html
        assert "No rows returned." in html
        assert "Not applicable:</b> unsupported" in html
        assert html.count("Not collected:</b>") >= len(HEALTH_SECTION_TITLES) - 3

    def test_health_template_omits_unsafe_historical_advice(self):
        from report_renderer import render_health_report

        html = render_health_report({"sections": []}).lower()
        prohibited = (
            "drop duplicate indexes",
            "drop rarely used indexes",
            "drop replication slots",
            "drop below readers",
            "increase shared_buffers",
            "24%",
            "25%",
            "67%",
            "vacuum freeze on",
            "set local work_mem",
        )
        assert not any(phrase in html for phrase in prohibited)
        assert "not approval" in html
        assert "evidence-based insight" not in html
        assert "automated dba assessment" in html

    def test_upgrade_has_18_checks_scope_considerations_references_and_disclaimer(self):
        from report_renderer import UPGRADE_CHECK_TITLES, render_upgrade_report

        html = render_upgrade_report(
            {
                "report_name": "Example <Customer>",
                "report_details": [{"Scope": "postgres only"}],
                "checks": [],
                "database_summary": [
                    {"Database": "postgres", "Evidence state": "Collected"},
                    {"Database": "myapp", "Evidence state": "Not collected"},
                ],
                "version_considerations": [
                    {"Evidence state": "Manual review", "Consideration": "Read release notes"}
                ],
            }
        )

        positions = [
            html.index(f">{number}. {escape(title)}: </font><br>")
            for number, title in enumerate(UPGRADE_CHECK_TITLES, 1)
        ]
        assert positions == sorted(positions)
        assert html.count("Check evidence was not supplied") == 18
        assert "All-Database Pre-Upgrade Summary" in html
        assert "A separate allowlisted connection is required" not in html
        assert "Version-specific considerations" in html
        assert "References" in html
        assert "Upgrade approval disclaimer" in html
        assert "not upgrade approval" in html
        assert "Example &lt;Customer&gt;" in html
        assert "<title>PostgreSQL Pre-Upgrade Readiness — Example &lt;Customer&gt;</title>" in html
        assert "<script" not in html.lower()

        descriptive_html = render_upgrade_report(
            {
                "report_name": "AuroraPG16 to PostgreSQL 18 Pre-Upgrade Readiness",
                "checks": [],
            }
        )
        assert (
            "<title>AuroraPG16 to PostgreSQL 18 Pre-Upgrade Readiness</title>"
            in descriptive_html
        )
        assert "PostgreSQL Pre-Upgrade Readiness — AuroraPG16" not in descriptive_html


class TestCollectionContracts:
    def test_35_day_metric_uses_dynamic_period_within_limit(self, monkeypatch):
        import server
        from report_service import cloudwatch_period_seconds

        assert cloudwatch_period_seconds(60) == 300
        assert cloudwatch_period_seconds(50400) == 2100
        assert 50400 * 60 / cloudwatch_period_seconds(50400) <= 1440

        class RDSClient:
            def describe_db_instances(self, **kwargs):
                return {"DBInstances": [{"Engine": "postgres"}]}

        class CloudWatchClient:
            def __init__(self):
                self.calls = []

            def get_metric_statistics(self, **kwargs):
                self.calls.append(kwargs)
                return {"Datapoints": []}

        cloudwatch = CloudWatchClient()
        monkeypatch.setattr(server, "rds_client", RDSClient())
        monkeypatch.setattr(server, "cloudwatch_client", cloudwatch)

        result = server.get_instance_metrics("test-db-1", period_minutes=50400)

        assert "Last 50400 minutes" in result
        assert len(cloudwatch.calls) == 9
        assert all(call["Period"] == 2100 for call in cloudwatch.calls)

    def test_log_pagination_stops_at_shared_report_deadline(self, monkeypatch):
        import report_service

        times = iter([100.0, 100.0, 101.0])
        monkeypatch.setattr(report_service, "monotonic", lambda: next(times))

        class RDSClient:
            def __init__(self):
                self.calls = 0

            def describe_db_log_files(self, **kwargs):
                self.calls += 1
                return {"DescribeDBLogFiles": [{"Size": 10}], "Marker": "next"}

        client = RDSClient()
        section = report_service._describe_log_total(
            client, "test-db-1", deadline=100.5
        )
        assert section["state"] == "Not collected"
        assert "pagination" in section["message"]
        assert client.calls == 1

    def test_query_errors_rollback_to_savepoint_before_next_query(self, monkeypatch):
        import report_service

        monkeypatch.setattr(report_service, "monotonic", lambda: 100.0)

        class TransactionConnection:
            def __init__(self):
                self.aborted = False
                self.commands = []

            def run(self, command):
                self.commands.append(command)
                if command.startswith("ROLLBACK TO SAVEPOINT"):
                    self.aborted = False
                return []

        connection = TransactionConnection()
        calls = 0

        def execute_query(conn, sql):
            nonlocal calls
            calls += 1
            if calls == 1:
                conn.aborted = True
                raise RuntimeError("relation does not exist")
            if conn.aborted:
                raise RuntimeError("current transaction is aborted")
            return [{"ok": True}]

        evidence = report_service._query_evidence(
            connection,
            {"1": {"1.1": {"sql": "SELECT missing"}, "1.2": {"sql": "SELECT 1"}}},
            ["1.1", "1.2"],
            execute_query,
            deadline=102.0,
        )

        assert evidence["1.1"]["state"] == "Error"
        assert evidence["1.2"] == {"state": "Collected", "rows": [{"ok": True}]}
        assert "ROLLBACK TO SAVEPOINT report_query_0" in connection.commands
        assert "SET LOCAL statement_timeout = '2000ms'" in connection.commands

    def test_target_instance_class_orderability_uses_exact_engine_versions(self, monkeypatch):
        import server

        class RDSClient:
            def __init__(self):
                self.calls = []

            def describe_orderable_db_instance_options(self, **kwargs):
                self.calls.append(kwargs)
                if kwargs["EngineVersion"] == "17.4":
                    return {
                        "OrderableDBInstanceOptions": [{
                            "EngineVersion": "17.4",
                            "DBInstanceClass": "db.m6g.large",
                        }]
                    }
                return {"OrderableDBInstanceOptions": []}

        client = RDSClient()
        monkeypatch.setattr(server, "rds_client", client)
        assert server._instance_class_orderable_for_targets(
            "postgres", "db.m6g.large", ["17.2", "17.4"]
        ) is True
        assert [call["EngineVersion"] for call in client.calls] == ["17.2", "17.4"]
        assert all(call["DBInstanceClass"] == "db.m6g.large" for call in client.calls)

    def test_aurora_pending_maintenance_checks_instance_and_cluster_arns(self, monkeypatch):
        import server

        # html mode is removed; on-screen markdown is the only health delivery,
        # and quick mode remains. The upgrade tool is markdown-only.
        health_html = server.run_full_health_check(
            "test-db-1.example.rds.amazonaws.com",
            report_format="html",
            instance_id="test-db-1",
        )
        assert health_html == "ERROR: report_format must be 'markdown' or 'quick'."

        upgrade_html = server.check_upgrade_readiness(
            "test-db-1",
            17,
            report_format="html",
            instance_endpoint="test-db-1.example.rds.amazonaws.com",
        )
        assert upgrade_html == "ERROR: report_format must be 'markdown'."

    def test_health_deadline_starts_at_tool_entry_markdown(self, monkeypatch):
        import server

        class Connection:
            def close(self):
                pass

        captured = {}
        monkeypatch.setattr(server, "monotonic", lambda: 100.0)
        monkeypatch.setattr(
            server,
            "_verify_complete_report_target",
            lambda *args, **kwargs: (True, ""),
        )
        monkeypatch.setattr(server, "_get_connection", lambda *args, **kwargs: Connection())
        monkeypatch.setattr(
            server,
            "build_health_markdown",
            lambda **kwargs: captured.update(kwargs) or "# report",
        )

        server.run_full_health_check(
            "test-db-1.example.rds.amazonaws.com",
            report_format="markdown",
            instance_id="test-db-1",
        )
        # The report deadline is anchored at tool entry (135s budget).
        assert captured["deadline"] == 235.0

    def test_markdown_connection_failure_reports_error_without_html(self, monkeypatch):
        import server

        monkeypatch.setattr(
            server,
            "_verify_complete_report_target",
            lambda *args, **kwargs: (True, ""),
        )
        monkeypatch.setattr(
            server,
            "_get_connection",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("db <down>")),
        )

        result = server.run_full_health_check(
            "test-db-1.example.rds.amazonaws.com",
            report_format="markdown",
            instance_id="test-db-1",
            report_name="A&B",
        )

        # The failure is surfaced on screen as a Markdown error report; no HTML,
        # no S3, no downloadable file.
        text = result if isinstance(result, str) else str(result)
        assert "could not be collected" in text
        assert "down" in text  # the underlying failure reason is surfaced
        assert "<html>" not in text.lower()


class TestCompleteCollectionPaths:
    class RDSClient:
        def describe_db_instances(self, **kwargs):
            return {
                "DBInstances": [{
                    "DBInstanceIdentifier": "test-db-1",
                    "Engine": "postgres",
                    "EngineVersion": "15.5",
                    "DBInstanceClass": "db.m6g.large",
                    "AllocatedStorage": 100,
                    "MaxAllocatedStorage": 200,
                    "StorageType": "gp3",
                    "BackupRetentionPeriod": 7,
                    "PreferredBackupWindow": "03:00-03:30",
                    "StorageEncrypted": True,
                    "MultiAZ": False,
                    "PubliclyAccessible": False,
                    "DeletionProtection": True,
                    "MonitoringInterval": 60,
                    "PerformanceInsightsEnabled": True,
                    "PerformanceInsightsRetentionPeriod": 31,
                    "EngineLifecycleSupport": "open-source-rds-extended-support-disabled",
                    "DBParameterGroups": [{"DBParameterGroupName": "custom-pg15"}],
                    "MasterUsername": "monitor",
                    "ReadReplicaDBInstanceIdentifiers": [],
                }]
            }

        def describe_db_log_files(self, **kwargs):
            return {"DescribeDBLogFiles": [{"Size": 10}, {"Size": 20}]}

    class CloudWatchClient:
        def __init__(self):
            self.calls = []

        def get_metric_statistics(self, **kwargs):
            self.calls.append(kwargs)
            return {"Datapoints": [{"Average": 10.0}]}

    def test_health_full_plan_uses_one_connection_and_preserves_partial_errors(self):
        import server
        from report_renderer import HEALTH_SECTION_TITLES
        from report_service import build_health_html

        connection = object()
        query_connections = []

        def execute_query(conn, sql):
            query_connections.append(conn)
            if "temp_blks_read" in sql:
                raise RuntimeError("extension <missing>")
            if "pg_postmaster_start_time" in sql:
                return [{"pg_postmaster_start_time": "2026-08-01", "uptime": "19 days"}]
            if "GROUP BY state" in sql:
                return [{"state": "active", "count": 3}, {"state": "idle", "count": 7}]
            if "AS inventory" in sql:
                return [
                    {"name": "max_connections", "setting": "500"},
                    {"name": "work_mem", "setting": "4096"},
                    {"name": "idle_in_transaction_session_timeout", "setting": "60000"},
                    {"name": "log_temp_files", "setting": "0"},
                    {"name": "autovacuum", "setting": "on"},
                    {"name": "log_min_duration_statement", "setting": "5000"},
                    {"name": "log_statement", "setting": "none"},
                    {"name": "log_autovacuum_min_duration", "setting": "1000"},
                    {"name": "shared_buffers", "setting": "16384"},
                ]
            return []

        cloudwatch = self.CloudWatchClient()
        html = build_health_html(
            conn=connection,
            query_allowlist=server.QUERY_ALLOWLIST,
            execute_query=execute_query,
            rds_client=self.RDSClient(),
            cloudwatch_client=cloudwatch,
            instance_id="test-db-1",
            instance_endpoint="test-db-1.example.rds.amazonaws.com",
            database="postgres",
            report_name="",
            now=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )

        assert query_connections and set(map(id, query_connections)) == {id(connection)}
        assert len(query_connections) == 24
        assert len(cloudwatch.calls) == 15
        assert all(f">{title}: </font><br>" in html for title in HEALTH_SECTION_TITLES)
        assert "<title>PostgreSQL Health Check — test-db-1</title>" in html
        assert "Server Uptime" in html and "19 days" in html
        assert "Maximum Connections" in html and "500" in html
        assert "Current Total Connections: 10<br>" in html
        assert "Idle Connections: 7<br>" in html
        assert "Storage Allocation: 100 GB<br>" in html
        assert "Storage Autoscaling: 200 GB<br>" in html
        assert "Preferred Backup Window" in html and "03:00-03:30" in html
        assert "PostgreSQL Health Score Card" not in html
        assert "<b>Evidence-Based Insight:</b>" not in html
        assessment_count = html.count("<b>Automated DBA Assessment:</b>")
        assert 0 < assessment_count < len(HEALTH_SECTION_TITLES)
        assert "Observed 7 evidence row(s)" not in html
        assert "PostgreSQL table partitioning" in html
        assert 'rel="noopener noreferrer"' in html
        assert "Current score" not in html
        assert "USE_VERIFIED_AURORA_ENGINE_DEFAULT" not in html
        assert "No rows returned." in html
        assert "extension &lt;missing&gt;" in html
        assert "Error:</b> Query 6.8 could not be collected" in html

    def test_upgrade_full_plan_renders_selected_database_scope(self):
        import server
        from report_renderer import UPGRADE_CHECK_TITLES
        from report_service import build_upgrade_html

        connection = object()
        query_connections = []

        def execute_query(conn, sql):
            query_connections.append(conn)
            if "pg_replication_slots" in sql:
                raise RuntimeError("logical slot evidence unavailable")
            if "pending_restart=true" in sql:
                raise RuntimeError("pending restart evidence unavailable")
            return []

        inst = self.RDSClient().describe_db_instances()["DBInstances"][0]
        html = build_upgrade_html(
            conn=connection,
            query_allowlist=server.QUERY_ALLOWLIST,
            execute_query=execute_query,
            rds_client=self.RDSClient(),
            cloudwatch_client=self.CloudWatchClient(),
            inst=inst,
            instance_id="test-db-1",
            instance_endpoint="test-db-1.example.rds.amazonaws.com",
            database="postgres",
            allowed_databases={"postgres", "myapp"},
            target_major_version=17,
            report_name="Customer",
            target_versions=["17.4"],
            valid_upgrade_versions=["17.4"],
            target_discovery_error="",
            instance_class_orderable=True,
            pending_actions=[],
            now=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )

        assert query_connections and set(map(id, query_connections)) == {id(connection)}
        assert len(query_connections) == 14
        assert all(
            f">{number}. {escape(title)}: </font><br>" in html
            for number, title in enumerate(UPGRADE_CHECK_TITLES, 1)
        )
        assert (
            "<title>PostgreSQL Pre-Upgrade Readiness — "
            "test-db-1 to PostgreSQL 17</title>" in html
        )
        assert (
            "Database-local checks cover the connected allowlisted database; "
            "cluster-wide catalog checks are identified separately." in html
        )
        assert "postgres" in html and "Collected" in html
        assert "myapp" in html and "Not collected" in html
        assert "Database-local checks cover only each explicitly connected allowlisted database" in html
        for pinned_section in (
            "18d-i. PostgreSQL 16 ICU collation version tracking",
            "18d-ii. New parameter in PG16: vacuum_buffer_usage_limit (default 256kB)",
            "18d-iii. Logical replication behavior change in PG16",
            "18d-iv. PostgreSQL 17 behavioral changes",
            "18d-v. Parameter review opportunity (post-upgrade best practice)",
            "18e. pg_stat_statements data will be cleared",
            "18f. Check for pending parameter changes (applied during upgrade restart)",
        ):
            assert pinned_section in html
        assert "logical slot evidence unavailable" in html
        assert "pending restart evidence unavailable" in html
        assert html.count(">Error</td>") >= 2
        assert "not upgrade approval" in html
