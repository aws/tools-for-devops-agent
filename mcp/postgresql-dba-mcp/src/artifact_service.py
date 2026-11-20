"""Server-side completeness validation for complete PostgreSQL HTML reports.

Retained utility for validating a complete report's section/check coverage and
escaping. Reports are delivered on screen only as the MCP's Markdown tool result;
the server produces no downloadable file and does not write to S3 or mint
presigned URLs. This module is not on the live tool path (kept for validation
tests and legacy rendering); it can be pruned in a later cleanup.
"""

from __future__ import annotations

import re
from html import escape, unescape

from assessment_engine import (
    ASSESSMENT_FIELDS,
    ASSESSMENT_PRIORITIES,
    NO_CHANGE_NARRATIVE,
    PROPOSAL_NARRATIVE_PREFIX,
    priority_from_narrative,
)
from report_renderer import (
    HEALTH_SECTION_TITLES,
    LOCAL_TEMPLATE_VERSION,
    UPGRADE_CHECK_TITLES,
    UPSTREAM_COMMIT,
)

_HTML_DOCTYPE = (
    '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" '
    '"http://www.w3.org/TR/html4/loose.dtd">'
)
_UPGRADE_TRAILING_MARKERS = (
    ">All-Database Pre-Upgrade Summary: </font><br>",
    ">Version-specific considerations: </font><br>",
    ">References: </font><br>",
    "Upgrade approval disclaimer:",
)
_ALLOWED_STATE_MARKERS = tuple(
    f"<b>{state}:</b>"
    for state in (
        "Not collected",
        "Not applicable",
        "Error",
        "Pass",
        "Fail",
        "Manual review",
    )
)
def _content_markers(report_kind: str) -> tuple[str, ...]:
    if report_kind == "health":
        return tuple(
            f">{escape(title, quote=True)}: </font><br>"
            for title in HEALTH_SECTION_TITLES
        )
    if report_kind == "pre-upgrade":
        return tuple(
            f">{number}. {escape(title, quote=True)}: </font><br>"
            for number, title in enumerate(UPGRADE_CHECK_TITLES, start=1)
        )
    raise ValueError(f"Unsupported report kind: {report_kind}")


def _ordered_positions(html: str, markers: tuple[str, ...]) -> list[int]:
    positions: list[int] = []
    cursor = 0
    for marker in markers:
        if html.count(marker) != 1:
            raise ValueError(f"Report must contain exactly one required marker: {marker}")
        position = html.find(marker, cursor)
        if position < 0:
            raise ValueError(f"Report is missing or reorders required marker: {marker}")
        positions.append(position)
        cursor = position + len(marker)
    return positions


def _visible_text(fragment: str) -> str:
    without_tags = re.sub(r"<[^>]*>", " ", fragment)
    return " ".join(unescape(without_tags).replace("\xa0", " ").split())


def _has_nonempty_data_cell(body: str) -> bool:
    cells = re.findall(r"<td\b[^>]*>(.*?)</td>", body, flags=re.IGNORECASE | re.DOTALL)
    return any(_visible_text(cell) for cell in cells)


def _has_explicit_state(body: str) -> bool:
    for marker in _ALLOWED_STATE_MARKERS:
        if marker not in body:
            continue
        message = body.split(marker, 1)[1].split("</font>", 1)[0]
        if _visible_text(message):
            return True
    return False


def _validate_health_section_evidence(evidence: str, index: int) -> None:
    if index == 0:
        date_value = (
            evidence.split("<p>", 1)[1].split("</p>", 1)[0].strip()
            if "<p>" in evidence and "</p>" in evidence
            else ""
        )
        valid = _has_explicit_state(evidence) or (
            bool(_visible_text(date_value)) and "<b>" not in date_value
        )
    elif index == 1:
        valid = _has_explicit_state(evidence) or (
            "<br>" in evidence and bool(_visible_text(evidence))
        )
    else:
        valid = (
            _has_nonempty_data_cell(evidence)
            or "No rows returned." in evidence
            or _has_explicit_state(evidence)
        )
    if not valid:
        raise ValueError(
            f"Health report section has no collected rows or explicit state: "
            f"{HEALTH_SECTION_TITLES[index]}"
        )


def _validate_health_bodies(
    html: str, markers: tuple[str, ...], positions: list[int]
) -> None:
    footer_position = html.find(
        "This report contains read-only evidence and is not approval",
        positions[-1],
    )
    if footer_position < 0:
        raise ValueError("Health report footer is missing.")
    remediation_marker = ">Prioritized Remediation Summary: </font><br>"
    remediation_position = html.find(remediation_marker, positions[-1])
    if remediation_position < 0 or remediation_position >= footer_position:
        raise ValueError("Health report prioritized remediation summary is missing.")
    remediation_body = html[
        remediation_position + len(remediation_marker):footer_position
    ]
    if (
        "Only read-only diagnostic queries and metadata calls were executed; no "
        "database or infrastructure change was made" not in remediation_body
        or not _visible_text(remediation_body)
    ):
        raise ValueError("Health report remediation summary is incomplete.")
    remediation_count = remediation_body.count("<b>Evidence:</b>")
    no_high_confidence = (
        "No high-confidence remediation was derived" in remediation_body
    )
    if not 1 <= remediation_count <= 5 and not (
        remediation_count == 0 and no_high_confidence
    ):
        raise ValueError("Health report remediation item count is invalid.")
    remediation_fields = (
        "<b>Evidence:</b>",
        "<b>So what:</b>",
        "<b>Steps:</b>",
        "<b>Example command (not executed):</b>",
        "<b>Validation:</b>",
        "<b>Risk and approval:</b>",
        "<b>Rollback:</b>",
    )
    if remediation_count and any(
        remediation_body.count(field) != remediation_count
        for field in remediation_fields
    ):
        raise ValueError("Health report remediation fields are incomplete.")

    assessment_paragraph_marker = (
        '<p><font face="verdana" color="#006699">'
        "<b>Automated DBA Assessment:</b> "
    )
    assessment_marker = "<b>Automated DBA Assessment:</b> "
    for index, (marker, position) in enumerate(zip(markers, positions)):
        end = positions[index + 1] if index + 1 < len(positions) else remediation_position
        body = html[position + len(marker):end]
        if "Evidence-Based Insight:" in body:
            raise ValueError(
                f"Health report section contains redundant Evidence-Based Insight: "
                f"{HEALTH_SECTION_TITLES[index]}"
            )
        assessment_count = body.count(assessment_paragraph_marker)
        if assessment_count == 0:
            if "No rows returned." not in body or assessment_marker in body:
                raise ValueError(
                    f"Health report section is missing Automated DBA Assessment: "
                    f"{HEALTH_SECTION_TITLES[index]}"
                )
            _validate_health_section_evidence(body, index)
            continue
        if assessment_count != 1 or body.count(assessment_marker) != 1:
            raise ValueError(
                f"Health report section must contain exactly one Automated DBA Assessment: "
                f"{HEALTH_SECTION_TITLES[index]}"
            )
        assessment_position = body.find(assessment_paragraph_marker)
        evidence = body[:assessment_position]
        if "No rows returned." in evidence:
            raise ValueError(
                f"Health report section must suppress assessment for zero rows: "
                f"{HEALTH_SECTION_TITLES[index]}"
            )
        assessment_values: dict[str, str] = {}
        field_positions: list[int] = []
        for field in ASSESSMENT_FIELDS:
            field_marker = (
                f'<span data-assessment-field="{escape(field, quote=True)}"'
            )
            if body.count(field_marker) != 1:
                raise ValueError(
                    f"Health report assessment field is missing or duplicated: "
                    f"{HEALTH_SECTION_TITLES[index]} / {field}"
                )
            field_position = body.find(field_marker)
            field_positions.append(field_position)
            start_tag_end = body.find(">", field_position + len(field_marker))
            if start_tag_end < 0:
                raise ValueError(
                    f"Health report assessment field start tag is incomplete: "
                    f"{HEALTH_SECTION_TITLES[index]} / {field}"
                )
            value_start = start_tag_end + 1
            value_end = body.find("</span>", value_start)
            if value_end < 0:
                raise ValueError(
                    f"Health report assessment field boundary is missing: "
                    f"{HEALTH_SECTION_TITLES[index]} / {field}"
                )
            value = _visible_text(body[value_start:value_end])
            if not value:
                raise ValueError(
                    f"Health report assessment field is empty: "
                    f"{HEALTH_SECTION_TITLES[index]} / {field}"
                )
            assessment_values[field] = value
        if field_positions != sorted(field_positions):
            raise ValueError(
                f"Health report assessment fields are out of order: "
                f"{HEALTH_SECTION_TITLES[index]}"
            )
        priority = priority_from_narrative(assessment_values["Priority"])
        if priority not in ASSESSMENT_PRIORITIES:
            raise ValueError(
                f"Health report assessment priority is invalid: {HEALTH_SECTION_TITLES[index]}"
            )
        proposed = assessment_values["Proposed changes"]
        if (
            proposed != NO_CHANGE_NARRATIVE
            and not proposed.startswith(PROPOSAL_NARRATIVE_PREFIX)
        ):
            raise ValueError(
                f"Health report proposed changes are not explicitly inert: "
                f"{HEALTH_SECTION_TITLES[index]}"
            )
        _validate_health_section_evidence(evidence, index)


def _validate_upgrade_bodies(
    html: str, markers: tuple[str, ...], positions: list[int]
) -> None:
    trailing_positions = _ordered_positions(html, _UPGRADE_TRAILING_MARKERS)
    if trailing_positions[0] <= positions[-1]:
        raise ValueError("Pre-upgrade trailing sections are out of order.")

    boundaries = positions[1:] + [trailing_positions[0]]
    for index, (marker, position, end) in enumerate(
        zip(markers, positions, boundaries), start=1
    ):
        body = html[position + len(marker):end]
        if not _has_explicit_state(body):
            raise ValueError(
                f"Pre-upgrade check {index} has no explicit evidence state."
            )

    summary_body = html[
        trailing_positions[0] + len(_UPGRADE_TRAILING_MARKERS[0]):
        trailing_positions[1]
    ]
    if not _has_nonempty_data_cell(summary_body) and "No rows returned." not in summary_body:
        raise ValueError("Pre-upgrade all-database summary has no explicit evidence.")

    considerations_body = html[
        trailing_positions[1] + len(_UPGRADE_TRAILING_MARKERS[1]):
        trailing_positions[2]
    ]
    considerations_has_message = (
        "Not collected:" in considerations_body
        and bool(_visible_text(considerations_body.split("Not collected:", 1)[1]))
    )
    if (
        not _has_nonempty_data_cell(considerations_body)
        and not considerations_has_message
    ):
        raise ValueError("Pre-upgrade version considerations have no explicit evidence.")

    references_body = html[trailing_positions[2]:]
    required_references = (
        "Amazon RDS for PostgreSQL upgrade guide",
        "Aurora PostgreSQL upgrade guide",
        "PostgreSQL pg_upgrade documentation",
        "Upgrade approval disclaimer:",
    )
    if any(value not in references_body for value in required_references):
        raise ValueError("Pre-upgrade references or approval disclaimer are incomplete.")


def validate_complete_html(html: str, report_kind: str) -> None:
    """Reject partial, marker-only, duplicated, or reconstructed report payloads."""
    if not isinstance(html, str) or not html.startswith(_HTML_DOCTYPE):
        raise ValueError("Report does not begin with the required HTML doctype.")
    if not html.rstrip().endswith("</html>"):
        raise ValueError("Report does not end with the required HTML closing tag.")

    markers = _content_markers(report_kind)
    positions = _ordered_positions(html, markers)
    if report_kind == "health":
        _validate_health_bodies(html, markers, positions)
    else:
        _validate_upgrade_bodies(html, markers, positions)

    required_footer_values = (
        UPSTREAM_COMMIT,
        f"local template version {LOCAL_TEMPLATE_VERSION}",
        "This report contains read-only evidence and is not approval",
    )
    if any(value not in html for value in required_footer_values):
        raise ValueError("Report provenance or non-approval footer is incomplete.")
