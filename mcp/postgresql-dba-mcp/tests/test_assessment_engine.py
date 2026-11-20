"""Focused contracts for deterministic Automated DBA Assessments."""

from __future__ import annotations

import copy
import os
import re
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.environ["STAGE_NAME"] = "test"
os.environ["SECRET_ARN"] = (
    "arn:aws:secretsmanager:us-west-2:111122223333:secret:test"
)
os.environ["ALLOWED_INSTANCES"] = "test-db-1"
os.environ["ALLOWED_DATABASES"] = "postgres"
os.environ["ALLOWED_ENDPOINTS"] = "test-db-1.example.rds.amazonaws.com"


def _section(title: str, rows: list[dict] | None = None, **extra) -> dict:
    section = {"title": title, "state": "Collected", "rows": rows or []}
    section.update(extra)
    return section


def test_assessments_have_exact_fields_and_are_order_independent():
    from assessment_engine import ASSESSMENT_FIELDS, attach_automated_assessments

    sections = [
        _section(
            "Top 10 Biggest Tables",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_database_name": "postgres",
                    "_assessment_total_user_table_count": 27,
                    "_assessment_relation_oid": 10,
                    "table_schema": "public",
                    "table_name": "orders",
                    "total_size": "600 GB",
                    "total_bytes": 600 * 1024**3,
                }
            ],
        ),
        _section(
            "Top 10 UPDATE/DELETE Tables",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 10,
                    "schemaname": "public",
                    "relname": "orders",
                    "update_pct": 70,
                    "delete_pct": 20,
                    "total_ops": 1000,
                    "n_dead_tup": 100,
                }
            ],
        ),
    ]
    forward = copy.deepcopy(sections)
    reverse = list(reversed(copy.deepcopy(sections)))
    attach_automated_assessments(forward)
    attach_automated_assessments(reverse)

    forward_by_title = {section["title"]: section["assessment"] for section in forward}
    reverse_by_title = {section["title"]: section["assessment"] for section in reverse}
    assert forward_by_title == reverse_by_title
    assert all(tuple(value) == ASSESSMENT_FIELDS for value in forward_by_title.values())
    assert forward_by_title["Top 10 Biggest Tables"]["Priority"] == "Medium"
    assert "Showing 1 of 27 user table(s) in database postgres" in forward_by_title["Top 10 Biggest Tables"]["Finding"]
    assert "500 GiB" in forward_by_title["Top 10 Biggest Tables"]["Finding"]


def test_index_metrics_deduplicate_bytes_and_report_overlap_by_oid():
    from assessment_engine import build_evidence_graph, calculate_index_metrics

    sections = [
        _section(
            "Potential Duplicate Index Candidates",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 10,
                    "table_schema": "public",
                    "table_name": "accounts",
                    "_assessment_candidate_index_oids": [101, 102],
                    "candidate_indexes": ["idx_accounts_1", "idx_accounts_2"],
                    "index_definitions": ["CREATE INDEX one", "CREATE INDEX two"],
                    "_assessment_candidate_index_bytes": [100, 200],
                    "candidate_count": 2,
                }
            ],
        ),
        _section(
            "Rarely Used Indexes",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 10,
                    "_assessment_index_oid": 101,
                    "_assessment_index_bytes": 100,
                    "schemaname": "public",
                    "table_name": "accounts",
                    "index_name": "idx_accounts_1",
                }
            ],
        ),
        _section(
            "Invalid Indexes",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 10,
                    "_assessment_index_oid": 102,
                    "_assessment_index_bytes": 200,
                    "schema_name": "public",
                    "table_name": "accounts",
                    "index_name": "idx_accounts_2",
                }
            ],
        ),
    ]
    metrics = calculate_index_metrics(build_evidence_graph(sections))

    assert metrics.evidence_occurrences == 4
    assert metrics.distinct_index_count == 2
    assert metrics.duplicate_occurrence_count == 2
    assert metrics.multi_signal_index_count == 2
    assert metrics.duplicate_rare_overlap == 1
    assert metrics.duplicate_invalid_overlap == 1
    assert metrics.rare_invalid_overlap == 0
    assert metrics.unique_candidate_bytes == 300
    assert metrics.duplicate_candidate_bytes == 300
    assert [name for name, _ in metrics.top_indexes] == [
        "public.idx_accounts_2",
        "public.idx_accounts_1",
    ]


def test_misaligned_duplicate_arrays_fail_closed_without_name_deduplication():
    from assessment_engine import build_evidence_graph, calculate_index_metrics

    graph = build_evidence_graph(
        [
            _section(
                "Potential Duplicate Index Candidates",
                [
                    {
                        "_assessment_database_oid": 5,
                        "_assessment_relation_oid": 10,
                        "_assessment_candidate_index_oids": [101, 102],
                        "candidate_indexes": ["same_name"],
                        "_assessment_candidate_index_bytes": [100, 200],
                        "candidate_count": 2,
                    }
                ],
            )
        ]
    )
    metrics = calculate_index_metrics(graph)

    assert metrics.distinct_index_count == 0
    assert metrics.unique_candidate_bytes == 0
    assert graph.identity_warnings == ["duplicate-index arrays were not aligned"]


def test_work_mem_requires_spill_evidence_and_proposes_only_scoped_benchmark():
    from assessment_engine import attach_automated_assessments

    sections = [
        _section(
            "Key PostgreSQL Parameters",
            [
                {"name": "work_mem", "setting": "1024", "unit": "kB"},
                {"name": "log_temp_files", "setting": "-1"},
                {"name": "log_min_duration_statement", "setting": "-1"},
            ],
        ),
        _section(
            "Top 10 Temporary Space Written Queries",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_user_oid": 20,
                    "query_fingerprint": 99,
                    "calls": 10,
                    "temp_blks_written": 50,
                }
            ],
            statement_statistics_window="pg_stat_statements counters observed since yesterday.",
        ),
        _section(
            "Top 10 Statements by Total Execution Time",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_user_oid": 20,
                    "query_fingerprint": 99,
                    "calls": 10,
                    "total_ms": 100,
                }
            ],
            statement_statistics_window="pg_stat_statements counters observed since yesterday.",
        ),
    ]
    attach_automated_assessments(sections)
    assessment = sections[0]["assessment"]

    assert assessment["Priority"] == "Medium"
    assert "50 temporary block" in assessment["Finding"]
    assert "4 MB as one test point" in assessment["Proposed changes"]
    assert assessment["Proposed changes"].startswith("Proposal only—not executed: ")
    assert "universal global minimum" in assessment["Recommendation"]


def test_write_and_maintenance_evidence_names_exact_autovacuum_candidate():
    from assessment_engine import attach_automated_assessments

    sections = [
        _section(
            "Top 10 Biggest Tables Last Vacuumed",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 88,
                    "schemaname": "public",
                    "table_name": "customer_orders",
                    "last_autovacuum": None,
                    "n_dead_tup": 500,
                }
            ],
        ),
        _section(
            "Top 10 UPDATE/DELETE Tables",
            [
                {
                    "_assessment_database_oid": 5,
                    "_assessment_relation_oid": 88,
                    "schemaname": "public",
                    "relname": "customer_orders",
                    "update_pct": 50,
                    "delete_pct": 40,
                    "total_ops": 10000,
                    "n_dead_tup": 500,
                }
            ],
        ),
    ]
    attach_automated_assessments(sections)

    assessment = sections[1]["assessment"]
    assert assessment["Priority"] == "Medium"
    assert "public.customer_orders" in assessment["Finding"]
    assert "per-table autovacuum" in assessment["Recommendation"]
    assert "test per-table autovacuum settings" in assessment["Proposed changes"]


def test_largest_table_scope_preserves_rank_and_fails_safe_without_total():
    from assessment_engine import attach_automated_assessments

    section = _section(
        "Top 10 Biggest Tables",
        [
            {
                "_assessment_database_oid": 5,
                "_assessment_relation_oid": 10,
                "table_schema": "public",
                "table_name": "z_largest",
                "total_size": "20 GB",
                "total_bytes": 20 * 1024**3,
            },
            {
                "_assessment_database_oid": 5,
                "_assessment_relation_oid": 11,
                "table_schema": "public",
                "table_name": "a_smaller",
                "total_size": "10 GB",
                "total_bytes": 10 * 1024**3,
            },
        ],
    )
    attach_automated_assessments([section])
    finding = section["assessment"]["Finding"]

    assert "total user-table count was not collected" in finding
    assert "does not imply that only these tables exist" in finding
    assert finding.index("public.z_largest") < finding.index("public.a_smaller")


def test_total_database_size_and_xid_findings_are_evidence_specific():
    from assessment_engine import attach_automated_assessments

    sections = [
        _section(
            "Total Size of All Databases",
            [{"database_count": 3, "total_bytes": 47_473_688_237, "total_size": "44 GB"}],
        ),
        _section(
            "Maximum Used Transaction IDs",
            [
                {
                    "datname": "template0",
                    "age": 29_570_552,
                    "remaining_until_wraparound": 2_117_913_095,
                }
            ],
        ),
    ]
    attach_automated_assessments(sections)
    assessments = {section["title"]: section["assessment"] for section in sections}

    total = assessments["Total Size of All Databases"]
    xid = assessments["Maximum Used Transaction IDs"]
    assert "3 non-template database(s) using 44 GB" in total["Finding"]
    assert "evidence row" not in total["Finding"]
    assert "29,570,552" in xid["Finding"]
    assert "1.38%" in xid["Finding"]
    assert "template0" in xid["Finding"]
    assert xid["Priority"] == "Informational"
    assert "Continue trending" in xid["Recommendation"]


def test_database_size_and_extension_findings_use_specific_objects():
    from assessment_engine import attach_automated_assessments

    sections = [
        _section(
            "Top 5 Databases Size",
            [
                {"_assessment_database_oid": 2, "datname": "bench", "size": "44 GB"},
                {"_assessment_database_oid": 3, "datname": "postgres", "size": "332 MB"},
            ],
        ),
        _section(
            "Extensions Installed",
            [
                {"name": "pg_stat_statements", "version": "1.10"},
                {"name": "plpgsql", "version": "1.0"},
            ],
        ),
    ]
    attach_automated_assessments(sections)
    assessments = {section["title"]: section["assessment"] for section in sections}

    database_finding = assessments["Top 5 Databases Size"]["Finding"]
    extension_finding = assessments["Extensions Installed"]["Finding"]
    assert "bench (44 GB)" in database_finding
    assert "postgres (332 MB)" in database_finding
    assert "evidence row" not in database_finding
    assert "pg_stat_statements 1.10" in extension_finding
    assert "plpgsql 1.0" in extension_finding


def test_renderers_emit_26_complete_assessments_and_hide_private_fields():
    from artifact_service import validate_complete_html
    from report_renderer import (
        ASSESSMENT_FIELDS,
        HEALTH_SECTION_TITLES,
        render_health_markdown,
        render_health_report,
    )

    report = {
        "report_name": "Assessment Contract",
        "sections": [
            {
                "title": "Top 10 Biggest Tables",
                "state": "Collected",
                "rows": [
                    {
                        "_assessment_database_oid": 5,
                        "_assessment_relation_oid": 10,
                        "table_schema": "public",
                        "table_name": "orders",
                        "total_size": "1 MB",
                        "total_bytes": 1024**2,
                    }
                ],
            }
        ],
    }
    html = render_health_report(report)
    markdown = render_health_markdown(report)

    assert html.count("<b>Automated DBA Assessment:</b>") == len(HEALTH_SECTION_TITLES)
    assert markdown.count("- **Automated DBA Assessment:**") == len(HEALTH_SECTION_TITLES)
    assert "Evidence-Based Insight" not in html
    assert "Evidence-Based Insight" not in markdown
    for field in ASSESSMENT_FIELDS:
        assert html.count(f'data-assessment-field="{field}"') == len(HEALTH_SECTION_TITLES)
        assert markdown.count(f"<!-- assessment:{field} -->") == len(HEALTH_SECTION_TITLES)
    first_html_assessment = html.split("<b>Automated DBA Assessment:</b> ", 1)[1].split(
        "</font></p>", 1
    )[0]
    assert "<br>" not in first_html_assessment
    assert 'data-assessment-field="Priority" style="display: none;"' in first_html_assessment
    assert 'data-assessment-field="Proposed changes" style="display: none;"' in first_html_assessment
    assert "No change is proposed from this snapshot." in first_html_assessment
    assert "None. No change" not in first_html_assessment
    assert not any(f"<b>{field}:" in first_html_assessment for field in ASSESSMENT_FIELDS)
    first_markdown_assessment = next(
        line for line in markdown.splitlines()
        if line.startswith("- **Automated DBA Assessment:**")
    )
    visible_markdown_assessment = re.sub(r"<!--.*?-->", "", first_markdown_assessment)
    assert "This requires review." not in visible_markdown_assessment
    assert "No change is proposed from this snapshot." not in visible_markdown_assessment
    assert not any(f"**{field}:**" in visible_markdown_assessment for field in ASSESSMENT_FIELDS)
    assert "_assessment_database_oid" not in html
    assert "_assessment_relation_oid" not in html
    assert "_assessment_database_oid" not in markdown
    assert "_assessment_relation_oid" not in markdown
    validate_complete_html(html, "health")


def test_zero_row_sections_suppress_visible_assessment_but_remain_complete():
    from artifact_service import validate_complete_html
    from report_renderer import (
        HEALTH_SECTION_TITLES,
        render_health_markdown,
        render_health_report,
    )
    import server

    title = "Top 10 Statements by Total Execution Time"
    next_title = "Top 10 Read I/O Queries"
    report = {
        "report_name": "Zero Row Contract",
        "sections": [
            {
                "title": title,
                "state": "Collected",
                "rows": [],
                "statement_statistics_window": "Counters observed since yesterday.",
            }
        ],
    }
    html = render_health_report(report)
    markdown = render_health_markdown(report)
    html_block = html.split(f">{title}: </font><br>", 1)[1].split(
        f">{next_title}: </font><br>", 1
    )[0]
    number = HEALTH_SECTION_TITLES.index(title) + 1
    next_number = number + 1
    markdown_block = markdown.split(f"### {number}. {title}", 1)[1].split(
        f"### {next_number}. {next_title}", 1
    )[0]

    assert "No rows returned." in html_block
    assert "Automated DBA Assessment" not in html_block
    assert "0 evidence row(s)" in markdown_block
    assert "Automated DBA Assessment" not in markdown_block
    validate_complete_html(html, "health")
    result = server._health_markdown_tool_result(markdown)
    assert result.is_error is False
    assert result.structured_content["represented_section_count"] == 26
    assert result.structured_content["validated_assessment_count"] == 25


def test_html_and_markdown_validators_reject_assessment_field_mutation():
    from artifact_service import validate_complete_html
    from report_renderer import render_health_markdown, render_health_report
    import server

    report = {"report_name": "Mutation Contract", "sections": []}
    html = render_health_report(report)
    markdown = render_health_markdown(report)

    broken_html = html.replace(
        'data-assessment-field="Finding"',
        'data-assessment-field="Removed finding"',
        1,
    )
    with pytest.raises(ValueError, match="assessment field"):
        validate_complete_html(broken_html, "health")

    broken_markdown = markdown.replace(
        "<!-- assessment:Finding -->",
        "<!-- assessment:Removed finding -->",
        1,
    )
    result = server._health_markdown_tool_result(broken_markdown)
    assert result.is_error is True
    assert result.structured_content["schema_version"] == "1.2"
    assert result.structured_content["validated_assessment_count"] == 25
    assert any("Finding" in error for error in result.structured_content["validation_errors"])
