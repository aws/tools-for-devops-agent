"""Deterministic, dependency-free legacy HTML report rendering.

The visual contract is derived from the public MIT-0 AWS sample pinned below.
Only structured values are accepted; every dynamic value is HTML escaped.
"""

from __future__ import annotations

from html import escape
from typing import Any

from assessment_engine import (
    ASSESSMENT_FIELDS,
    NO_CHANGE,
    assessment_narrative_value,
    attach_automated_assessments,
    validate_assessment,
    visible_columns,
)

UPSTREAM_REPOSITORY = (
    "https://github.com/aws-samples/sample-rds-aurora-postgres-dba-toolkit"
)
UPSTREAM_COMMIT = "5172525155139b455c25cd7f879bfdda38c13bf3"
LOCAL_TEMPLATE_VERSION = "1.5"

HEALTH_SECTION_TITLES = (
    "Date",
    "Instance Details",
    "Infrastructure Metrics (CloudWatch)",
    "Extensions Installed",
    "Total Size of Log Files",
    "Maximum Used Transaction IDs",
    "Total Size of All Databases",
    "Top 5 Databases Size",
    "Top 10 Biggest Tables",
    "Tables Without Primary Key",
    "Potential Duplicate Index Candidates",
    "Rarely Used Indexes",
    "Invalid Indexes",
    "Top 5 Database Age",
    "Top 5 Table age",
    "Sequences Nearing Exhaustion",
    "Top 10 Most Bloated Tables",
    "Top 10 Biggest Tables Last Vacuumed",
    "Top 10 UPDATE/DELETE Tables",
    "Key PostgreSQL Parameters",
    "Top 10 Read IO Tables",
    "Database Cache Hit Ratio",
    "Top 10 Statements by Total Execution Time",
    "Top 10 Read I/O Queries",
    "Top 10 Temporary Space Written Queries",
    "Top 10 Temporary Space Read Queries",
)

UPGRADE_CHECK_TITLES = (
    "Check for target Postgres version",
    "Check for unsupported DB instance classes",
    "Check for open prepared transactions",
    "Check for unsupported reg* data types",
    "Check for logical replication slots",
    "Check for storage issues",
    "Check for 'Incompatible Parameter' error",
    "Check for Unknown data types",
    "Check for Read Replica upgrade failure",
    "Check for Postgres extensions",
    "Check for user access",
    "Check for sql_identifier data type",
    "Check for views dependency",
    "Check for incorrect primary user name",
    "Check for GIST index",
    "Check for User-Created ICU Collations (PostgreSQL 16+)",
    "Check for new reserved keywords (PostgreSQL 17+)",
    "Check for pending maintenance actions",
)

HEALTH_NOTES = {
    "Infrastructure Metrics (CloudWatch)": (
        "Values are averages for the stated windows. Averages can hide spikes; review "
        "time-series data and business impact separately. FreeableMemory is an "
        "availability/reclaimability observation, not unused or wasted memory."
    ),
    "Extensions Installed": (
        "Verify extension ownership, support, and version compatibility before changes."
    ),
    "Total Size of Log Files": (
        "Log metadata is observational. Retention or export changes require separate "
        "impact review and approval."
    ),
    "Maximum Used Transaction IDs": (
        "Review transaction ID age trends, autovacuum evidence, and long-running "
        "transactions. This report does not issue maintenance commands."
    ),
    "Top 10 Biggest Tables": (
        "Size alone does not justify partitioning or other changes; correlate access "
        "patterns, maintenance cost, and retention requirements."
    ),
    "Tables Without Primary Key": (
        "Review logical-replication and application requirements before proposing keys."
    ),
    "Potential Duplicate Index Candidates": (
        "These are review candidates only. Do not remove an index without validating "
        "constraints, workload history, dependencies, and rollback."
    ),
    "Rarely Used Indexes": (
        "Counters can reset and workloads can be seasonal. No automatic index removal "
        "is recommended."
    ),
    "Invalid Indexes": (
        "Confirm creation history, dependencies, storage, and an approved remediation "
        "plan before changing an invalid index."
    ),
    "Sequences Nearing Exhaustion": (
        "Usage is an evidence signal. Review ownership, growth rate, and application "
        "compatibility before changing a sequence type."
    ),
    "Top 10 Most Bloated Tables": (
        "This is a heuristic physical bloat estimate, not measured reclaimable space. "
        "Validate with approved tooling before planning remediation."
    ),
    "Top 10 Biggest Tables Last Vacuumed": (
        "Vacuum timestamps and sizes require workload, dead-tuple, transaction, and log "
        "context. No immediate vacuum operation is recommended."
    ),
    "Top 10 UPDATE/DELETE Tables": (
        "Statistics are cumulative observations. Evaluate reset time and workload phase "
        "before tuning table-level autovacuum settings."
    ),
    "Key PostgreSQL Parameters": (
        "Live pg_settings values are PostgreSQL evidence, not AWS parameter-group "
        "provenance. No shared_buffers target, percentage, reset, or reboot action is "
        "derived from these values."
    ),
    "Top 10 Read IO Tables": (
        "Cache and I/O counters do not by themselves establish a tuning action or prove "
        "working-set fit."
    ),
    "Database Cache Hit Ratio": (
        "A cache-hit ratio is observation only. It does not prove that the working set "
        "fits in shared_buffers or establish a memory target."
    ),
    "Top 10 Statements by Total Execution Time": (
        "Review estimated plans, statistics, calls, and workload impact. Plan-only "
        "EXPLAIN does not prove runtime behavior."
    ),
    "Top 10 Read I/O Queries": (
        "Shared block counters are cumulative evidence; correlate them with reset time, "
        "calls, plans, and infrastructure metrics."
    ),
    "Top 10 Temporary Space Written Queries": (
        "Review plans and concurrency before proposing session or parameter changes."
    ),
    "Top 10 Temporary Space Read Queries": (
        "Review plans and concurrency before proposing session or parameter changes."
    ),
}


HEALTH_REFERENCES: dict[str, tuple[tuple[str, str], ...]] = {
    "Total Size of Log Files": (
        (
            "RDS for PostgreSQL log concepts and retention",
            "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_LogAccess.Concepts.PostgreSQL.html",
        ),
    ),
    "Maximum Used Transaction IDs": (
        (
            "Creating CloudWatch alarms for RDS",
            "https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/creating_alarms.html",
        ),
        (
            "PostgreSQL transaction ID wraparound prevention",
            "https://www.postgresql.org/docs/current/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND",
        ),
        (
            "AWS early-warning system for transaction ID wraparound",
            "https://aws.amazon.com/blogs/database/implement-an-early-warning-system-for-transaction-id-wraparound-in-amazon-rds-for-postgresql/",
        ),
    ),
    "Top 10 Biggest Tables": (
        (
            "PostgreSQL table partitioning",
            "https://www.postgresql.org/docs/current/ddl-partitioning.html",
        ),
    ),
    "Top 5 Database Age": (
        (
            "PostgreSQL routine vacuuming and transaction ID age",
            "https://www.postgresql.org/docs/current/routine-vacuuming.html",
        ),
    ),
    "Top 5 Table age": (
        (
            "PostgreSQL routine vacuuming and freezing",
            "https://www.postgresql.org/docs/current/routine-vacuuming.html",
        ),
    ),
    "Top 10 Most Bloated Tables": (
        (
            "PostgreSQL VACUUM command",
            "https://www.postgresql.org/docs/current/sql-vacuum.html",
        ),
        (
            "PostgreSQL autovacuum configuration",
            "https://www.postgresql.org/docs/current/runtime-config-autovacuum.html",
        ),
        (
            "Understanding autovacuum in Amazon RDS for PostgreSQL",
            "https://aws.amazon.com/blogs/database/understanding-autovacuum-in-amazon-rds-for-postgresql-environments/",
        ),
        (
            "AWS autovacuum tuning case study",
            "https://aws.amazon.com/blogs/database/a-case-study-of-tuning-autovacuum-in-amazon-rds-for-postgresql/",
        ),
    ),
    "Top 10 Biggest Tables Last Vacuumed": (
        (
            "PostgreSQL routine vacuuming",
            "https://www.postgresql.org/docs/current/routine-vacuuming.html",
        ),
        (
            "Understanding autovacuum in Amazon RDS for PostgreSQL",
            "https://aws.amazon.com/blogs/database/understanding-autovacuum-in-amazon-rds-for-postgresql-environments/",
        ),
    ),
    "Top 10 UPDATE/DELETE Tables": (
        (
            "PostgreSQL autovacuum configuration",
            "https://www.postgresql.org/docs/current/runtime-config-autovacuum.html",
        ),
        (
            "AWS autovacuum tuning case study",
            "https://aws.amazon.com/blogs/database/a-case-study-of-tuning-autovacuum-in-amazon-rds-for-postgresql/",
        ),
    ),
    "Key PostgreSQL Parameters": (
        (
            "PostgreSQL resource consumption settings",
            "https://www.postgresql.org/docs/current/runtime-config-resource.html",
        ),
        (
            "Aurora PostgreSQL optimizer parameters",
            "https://aws.amazon.com/blogs/database/amazon-aurora-postgresql-parameters-part-3-optimizer-parameters/",
        ),
    ),
    "Top 10 Read IO Tables": (
        (
            "PostgreSQL pg_prewarm extension",
            "https://www.postgresql.org/docs/current/pgprewarm.html",
        ),
    ),
    "Database Cache Hit Ratio": (
        (
            "PostgreSQL pg_buffercache extension",
            "https://www.postgresql.org/docs/current/pgbuffercache.html",
        ),
    ),
    "Top 10 Statements by Total Execution Time": (
        (
            "PostgreSQL using EXPLAIN",
            "https://www.postgresql.org/docs/current/using-explain.html",
        ),
        (
            "AWS troubleshooting high CPU for RDS and Aurora PostgreSQL",
            "https://repost.aws/knowledge-center/rds-aurora-postgresql-high-cpu",
        ),
        (
            "PostgreSQL pg_stat_statements",
            "https://www.postgresql.org/docs/current/pgstatstatements.html",
        ),
    ),
    "Top 10 Read I/O Queries": (
        (
            "PostgreSQL using EXPLAIN",
            "https://www.postgresql.org/docs/current/using-explain.html",
        ),
        (
            "PostgreSQL pg_stat_statements",
            "https://www.postgresql.org/docs/current/pgstatstatements.html",
        ),
    ),
}


def _text(value: Any) -> str:
    """Escape one dynamic value for element content."""
    if value is None:
        return "NULL"
    return escape(str(value), quote=True)


def _safe_name(value: Any, fallback: str) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized else fallback


def _report_document_title(report_name: str, report_kind: str) -> str:
    """Use descriptive report names directly; otherwise add one concise prefix."""
    normalized = " ".join(
        report_name.casefold().replace("_", " ").replace("-", " ").split()
    )
    if report_kind == "health":
        if "health check" in normalized:
            return report_name
        return f"PostgreSQL Health Check — {report_name}"
    if report_kind == "pre-upgrade":
        if (
            "pre upgrade" in normalized
            or "upgrade readiness" in normalized
            or "upgrade check" in normalized
        ):
            return report_name
        return f"PostgreSQL Pre-Upgrade Readiness — {report_name}"
    raise ValueError(f"Unsupported report kind: {report_kind}")


def _document_start(title: str) -> list[str]:
    escaped_title = _text(title)
    return [
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" '
        '"http://www.w3.org/TR/html4/loose.dtd">',
        "<html>",
        "<head>",
        '<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">',
        f"<title>{escaped_title}</title>",
        '<meta name="referrer" content="no-referrer">',
        "</head>",
        '<body style="font-family: Verdana" bgcolor="#F8F8F8">',
        "<fieldset>",
        '<table width="100%" border="0" cellpadding="0" cellspacing="0">',
        '<tr><td align="center">',
        (
            '<h1 align="center">'
            f'<font face="verdana" color="#0099cc">{escaped_title}</font></h1>'
        ),
        "</td></tr></table>",
        "</fieldset>",
    ]


def _section_heading(title: str) -> str:
    return (
        '<font face="verdana" color="#ff6600">'
        f"{_text(title)}: </font><br>"
    )


def _render_health_references(title: str) -> str:
    """Render vetted, section-specific public references without external assets."""
    references = HEALTH_REFERENCES.get(title, ())
    if not references:
        return ""
    links = " | ".join(
        (
            f'<a href="{_text(url)}" target="_blank" '
            f'rel="noopener noreferrer">{_text(label)}</a>'
        )
        for label, url in references
    )
    return (
        '<p><font face="verdana" color="#0099cc"><b>References:</b> '
        f"{links}</font></p>"
    )


def _render_table(rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if not rows:
        return '<p><font face="verdana" color="#0099cc">No rows returned.</font></p>'
    selected_columns = columns or visible_columns(rows[0])
    parts = ['<table border="1" cellpadding="3" cellspacing="0">', "<tr>"]
    parts.extend(
        f'<th align="center"><font face="verdana" color="#000000">{_text(column)}</font></th>'
        for column in selected_columns
    )
    parts.append("</tr>")
    for row in rows:
        parts.append('<tr valign="top">')
        parts.extend(
            f'<td align="left">{_text(row.get(column))}</td>'
            for column in selected_columns
        )
        parts.append("</tr>")
    parts.append("</table>")
    return "\n".join(parts)


def _render_line_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<font face="verdana" color="#0099cc">No rows returned.</font><br>'
    parts = []
    for row in rows:
        label = row.get("Property", "Evidence")
        parts.append(f"{_text(label)}: {_text(row.get('Value'))}<br>")
    return "\n".join(parts)


def _render_section_content(section: dict[str, Any]) -> str:
    state = str(section.get("state", "Collected"))
    if state != "Collected":
        message = section.get("message") or state
        return (
            '<p><font face="verdana" color="#0099cc"><b>'
            f"{_text(state)}:</b> {_text(message)}</font></p>"
        )
    if "rows" in section:
        rows = section.get("rows") or []
        if section.get("layout") == "lines":
            return _render_line_rows(rows)
        return _render_table(rows, section.get("columns"))
    value = section.get("value")
    if value is None or value == "":
        return '<p><font face="verdana" color="#0099cc">No rows returned.</font></p>'
    return f"<p>{_text(value)}</p>"


def _render_remediation_summary(report: dict[str, Any]) -> list[str]:
    """Render prioritized, inert remediation guidance after canonical evidence."""
    parts = [_section_heading("Prioritized Remediation Summary")]
    parts.append(
        '<p><font face="verdana" color="#0099cc">'
        "Only read-only diagnostic queries and metadata calls were executed; no "
        "database or infrastructure change was made. "
        "Review impact, obtain owner approval, test in non-production, and use an "
        "approved change window before implementation.</font></p>"
    )
    remediations = report.get("remediations") or []
    if not remediations:
        parts.append(
            '<p><font face="verdana" color="#0099cc">'
            "No high-confidence remediation was derived from the collected snapshot. "
            "Continue monitoring and investigate any unavailable evidence.</font></p>"
        )
        return parts

    for index, item in enumerate(remediations, start=1):
        priority = item.get("priority", "Review")
        issue = item.get("issue", "Finding requires review")
        parts.append(
            '<p><font face="verdana" color="#000000"><b>'
            f"{index}. [{_text(priority)}] {_text(issue)}</b></font><br>"
            f"<b>Evidence:</b> {_text(item.get('evidence', 'Not supplied'))}<br>"
            f"<b>So what:</b> {_text(item.get('so_what', 'Impact requires review'))}<br>"
            f"<b>Steps:</b> {_text(' '.join(item.get('steps') or []))}<br>"
            f"<b>Example command (not executed):</b> "
            f"<code>{_text(item.get('example_command', 'No command proposed'))}</code><br>"
            f"<b>Validation:</b> {_text(item.get('validation', 'Re-run the relevant read-only checks'))}<br>"
            f"<b>Risk and approval:</b> {_text(item.get('risk_and_approval', 'Owner approval is required'))}<br>"
            f"<b>Rollback:</b> {_text(item.get('rollback', 'Define rollback before implementation'))}"
            "</p>"
        )
    return parts


def _markdown_text(value: Any) -> str:
    """Neutralize raw HTML and inline Markdown from dynamic values."""
    text = escape(str(value if value is not None else "NULL"), quote=False)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    for character in ("\\", "`", "*", "_", "[", "]", "|", "#", ">"):
        text = text.replace(character, f"\\{character}")
    return text


def markdown_text(value: Any) -> str:
    """Encode a dynamic value for safe Markdown output outside this renderer."""
    return _markdown_text(value)


def _markdown_cell(value: Any) -> str:
    """Escape a compact value for a Markdown table cell."""
    return _markdown_text(value)


def _markdown_inline_code(value: Any) -> str:
    """Render a controlled command as inert inline code."""
    text = " ".join(str(value if value is not None else "").split())
    return text.replace("`", "'")


def _markdown_health_references(title: str) -> str:
    references = HEALTH_REFERENCES.get(title, ())
    return " | ".join(
        f"[{_markdown_text(label)}]({url})" for label, url in references
    )


def _markdown_table(rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if not rows:
        return "_No rows returned._"
    selected_columns = columns or visible_columns(rows[0])
    lines = [
        "| " + " | ".join(_markdown_cell(column) for column in selected_columns) + " |",
        "| " + " | ".join("---" for _ in selected_columns) + " |",
    ]
    for row in rows:
        lines.append(
            "| " + " | ".join(_markdown_cell(row.get(column)) for column in selected_columns) + " |"
        )
    return "\n".join(lines)


def _section_evidence_summary(section: dict[str, Any]) -> str:
    state = str(section.get("state", "Collected"))
    if state != "Collected":
        return f"{state}: {section.get('message') or state}"
    if "rows" in section:
        return f"{len(section.get('rows') or [])} evidence row(s)"
    value = section.get("value")
    return str(value) if value not in (None, "") else "No rows returned"


def _health_sections_with_assessments(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return canonical sections with exactly one validated assessment each."""
    supplied = {
        str(section.get("title")): section
        for section in report.get("sections", [])
        if section.get("title")
    }
    ordered = [
        dict(
            supplied.get(
                title,
                {
                    "title": title,
                    "state": "Not collected",
                    "message": "Section evidence was not supplied.",
                },
            )
        )
        for title in HEALTH_SECTION_TITLES
    ]
    missing_indexes: list[int] = []
    for index, section in enumerate(ordered):
        assessment = section.get("assessment")
        if assessment is None:
            missing_indexes.append(index)
        else:
            validate_assessment(assessment)
    if missing_indexes:
        generated = [
            {key: value for key, value in section.items() if key != "assessment"}
            for section in ordered
        ]
        attach_automated_assessments(generated)
        for index in missing_indexes:
            ordered[index]["assessment"] = generated[index]["assessment"]
    for section in ordered:
        validate_assessment(section["assessment"])
    return ordered


def _should_render_assessment(section: dict[str, Any]) -> bool:
    """Suppress narrative when a collected row-based section has no matches."""
    return not (
        section.get("state", "Collected") == "Collected"
        and "rows" in section
        and not (section.get("rows") or [])
    )


def _assessment_field_visible(field: str, assessment: dict[str, str]) -> bool:
    if field == "Priority":
        return False
    if field == "Proposed changes" and assessment[field] == NO_CHANGE:
        return False
    return True


def _render_assessment_html(assessment: dict[str, str]) -> str:
    fields = " ".join(
        (
            f'<span data-assessment-field="{_text(field)}"'
            + (' style="display: none;"' if not _assessment_field_visible(field, assessment) else "")
            + ">"
            + f"{_text(assessment_narrative_value(field, assessment[field]))}</span>"
        )
        for field in ASSESSMENT_FIELDS
    )
    return (
        '<p><font face="verdana" color="#006699">'
        f"<b>Automated DBA Assessment:</b> {fields}</font></p>"
    )


def _render_assessment_markdown(assessment: dict[str, str]) -> list[str]:
    fragments: list[str] = []
    for field in ASSESSMENT_FIELDS:
        marker = f"<!-- assessment:{field} -->"
        narrative = _markdown_text(
            assessment_narrative_value(field, assessment[field])
        )
        if _assessment_field_visible(field, assessment):
            fragments.append(f"{marker}{narrative}")
        else:
            fragments.append(
                f"{marker}<!-- hidden-assessment-value:{narrative} -->"
            )
    return [f"- **Automated DBA Assessment:** {' '.join(fragments)}"]


def render_health_markdown(report: dict[str, Any]) -> str:
    """Render bounded evidence and insights for every canonical section."""
    report_name = _markdown_text(_safe_name(report.get("report_name"), "Customer"))
    ordered_sections = _health_sections_with_assessments(report)
    supplied = {str(section["title"]): section for section in ordered_sections}
    collected_count = sum(
        1 for section in ordered_sections if section.get("state") == "Collected"
    )
    lines = [
        f"# PostgreSQL Health Check — {report_name}",
        "",
        f"**Sections represented:** {len(HEALTH_SECTION_TITLES)}/{len(HEALTH_SECTION_TITLES)} canonical sections",
        f"**Sections with collected evidence:** {collected_count}/{len(HEALTH_SECTION_TITLES)}",
        "**Delivery:** On-screen evidence; no HTML file was created or uploaded.",
        "",
        "## Section evidence and automated DBA assessments",
    ]
    for number, title in enumerate(HEALTH_SECTION_TITLES, start=1):
        section = supplied.get(
            title,
            {"title": title, "state": "Not collected", "message": "Section evidence was not supplied."},
        )
        lines.extend(
            [
                "",
                f"### {number}. {_markdown_text(title)}",
                f"- **Evidence state:** {_markdown_text(_section_evidence_summary(section))}",
            ]
        )
        if _should_render_assessment(section):
            lines.extend(_render_assessment_markdown(section["assessment"]))
        reference_text = _markdown_health_references(title)
        if reference_text:
            lines.append(f"- **References:** {reference_text}")
        rows = section.get("rows") or []
        if section.get("state", "Collected") == "Collected" and rows:
            row_limit = 20 if title == "Instance Details" else 11 if title == "Key PostgreSQL Parameters" else 5 if title == "Infrastructure Metrics (CloudWatch)" else 3
            visible_rows = rows[:row_limit]
            columns = section.get("columns") or visible_columns(visible_rows[0])
            display_columns = columns[:6]
            lines.extend(["", _markdown_table(visible_rows, display_columns)])
            if len(rows) > len(visible_rows):
                lines.append(f"\n_Showing {len(visible_rows)} of {len(rows)} evidence rows on screen._")
            if len(columns) > len(display_columns):
                lines.append(f"\n_Showing {len(display_columns)} of {len(columns)} evidence columns on screen._")

    lines.extend([
        "",
        "## Prioritized remediation summary",
        "",
        "Only read-only diagnostic queries and metadata calls were executed; no database or infrastructure change was made.",
        "Each proposal requires impact review, owner approval, non-production validation, and an approved change window.",
    ])
    remediations = report.get("remediations") or []
    if not remediations:
        lines.append("\nNo high-confidence remediation was derived from this snapshot. Continue monitoring and investigate unavailable evidence.")
    for index, item in enumerate(remediations, start=1):
        lines.extend([
            "",
            f"### {index}. [{_markdown_text(item.get('priority') or 'Review')}] {_markdown_text(item.get('issue') or 'Finding requires review')}",
            f"- **Evidence:** {_markdown_text(item.get('evidence', 'Not supplied'))}",
            f"- **So what:** {_markdown_text(item.get('so_what', 'Impact requires review'))}",
            f"- **Steps:** {_markdown_text(' '.join(item.get('steps') or []))}",
            f"- **Example command (not executed):** `{_markdown_inline_code(item.get('example_command') or 'No command proposed')}`",
            f"- **Validation:** {_markdown_text(item.get('validation', 'Re-run the relevant read-only checks'))}",
            f"- **Risk and approval:** {_markdown_text(item.get('risk_and_approval', 'Owner approval is required'))}",
            f"- **Rollback:** {_markdown_text(item.get('rollback', 'Define rollback before implementation'))}",
        ])
    lines.extend([
        "",
        "_This report contains read-only evidence and is not approval for a database, infrastructure, parameter, index, maintenance, or upgrade change._",
    ])
    return "\n".join(lines)


def _render_footer() -> list[str]:
    return [
        "<br>",
        '<p><font face="verdana" color="#0099cc"><small>'
        "This report contains read-only evidence and is not approval for a database, "
        "infrastructure, parameter, index, maintenance, or upgrade change. Validate in "
        "a non-production environment and use an approved change process."
        "</small></font></p>",
        '<p><font face="verdana" color="#d3d3d3"><small>'
        f'Upstream source: <a href="{UPSTREAM_REPOSITORY}">'
        "aws-samples/sample-rds-aurora-postgres-dba-toolkit</a>; "
        f"commit {_text(UPSTREAM_COMMIT)}; local template version "
        f"{_text(LOCAL_TEMPLATE_VERSION)}."
        "</small></font></p>",
        "</body>",
        "</html>",
    ]


def render_health_report(report: dict[str, Any]) -> str:
    """Render a complete health report with every canonical section in order."""
    report_name = _safe_name(report.get("report_name"), "Customer")
    parts = _document_start(_report_document_title(report_name, "health"))
    ordered_sections = _health_sections_with_assessments(report)
    supplied = {str(section["title"]): section for section in ordered_sections}
    for title in HEALTH_SECTION_TITLES:
        section = supplied.get(
            title,
            {"title": title, "state": "Not collected", "message": "Section evidence was not supplied."},
        )
        parts.append(_section_heading(title))
        parts.append(_render_section_content(section))
        if _should_render_assessment(section):
            parts.append(_render_assessment_html(section["assessment"]))
        references = _render_health_references(title)
        if references:
            parts.append(references)
    parts.extend(_render_remediation_summary(report))
    parts.extend(_render_footer())
    return "\n".join(parts)


def render_upgrade_report(report: dict[str, Any]) -> str:
    """Render the canonical 18-check pre-upgrade report and scope summary."""
    report_name = _safe_name(report.get("report_name"), "Customer")
    parts = _document_start(_report_document_title(report_name, "pre-upgrade"))
    parts.append(_section_heading("Pre-upgrade check report for"))
    parts.append(_render_table(report.get("report_details") or []))
    parts.append(
        '<p><font face="verdana" color="#0099cc">Evidence states: Collected, '
        "Not collected, Not applicable, Error, Pass, Fail, and Manual review. "
        "No state constitutes upgrade approval.</font></p>"
    )

    supplied = {
        int(check.get("number")): check
        for check in report.get("checks", [])
        if str(check.get("number", "")).isdigit()
    }
    for number, title in enumerate(UPGRADE_CHECK_TITLES, start=1):
        check = supplied.get(
            number,
            {"state": "Not collected", "message": "Check evidence was not supplied."},
        )
        parts.append(_section_heading(f"{number}. {title}"))
        state = check.get("state", "Not collected")
        message = check.get("message", state)
        color = {"Pass": "green", "Fail": "red", "Error": "red"}.get(
            str(state), "#0099cc"
        )
        parts.append(
            f'<p><font face="verdana" color="{color}"><b>{_text(state)}:</b> '
            f"{_text(message)}</font></p>"
        )
        if check.get("rows") is not None:
            parts.append(_render_table(check.get("rows") or [], check.get("columns")))

    parts.append(_section_heading("All-Database Pre-Upgrade Summary"))
    parts.append(_render_table(report.get("database_summary") or []))
    parts.append(
        '<p><font face="verdana" color="#0099cc">Note: Database-local checks '
        "cover only each explicitly connected allowlisted database. Cluster-wide catalog "
        "evidence, such as replication-slot inventory, is identified by the relevant "
        "check and may apply across databases. Unconnected database-local evidence "
        "remains Not collected.</font></p>"
    )
    parts.append(_section_heading("Version-specific considerations"))
    considerations = report.get("version_considerations") or []
    if considerations:
        parts.append(_render_table(considerations))
    else:
        parts.append(
            '<p><font face="verdana" color="#0099cc">Not collected: No '
            "version-pair evidence was available.</font></p>"
        )
    parts.append(_section_heading("References"))
    parts.extend(
        [
            '<p><a href="https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.PostgreSQL.html">Amazon RDS for PostgreSQL upgrade guide</a></p>',
            '<p><a href="https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/USER_UpgradeDBInstance.PostgreSQL.html">Aurora PostgreSQL upgrade guide</a></p>',
            '<p><a href="https://www.postgresql.org/docs/current/pgupgrade.html">PostgreSQL pg_upgrade documentation</a></p>',
            '<p><font face="verdana" color="#0099cc"><b>Upgrade approval disclaimer:</b> '
            "This read-only evidence report is not upgrade approval. Run authoritative "
            "RDS or Aurora pre-upgrade checks and test the exact upgrade on a restored "
            "snapshot or clone.</font></p>",
        ]
    )
    parts.extend(_render_footer())
    return "\n".join(parts)
