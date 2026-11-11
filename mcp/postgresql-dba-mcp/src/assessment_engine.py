"""Deterministic cross-section assessments for PostgreSQL health reports.

The engine consumes structured evidence only. It never executes SQL, calls AWS,
or proposes an immediately executable change. Object correlation uses catalog
identities supplied in reserved ``_assessment_*`` fields; names are display
attributes only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


ASSESSMENT_FIELDS = (
    "Finding",
    "Priority",
    "Why it matters",
    "Recommendation",
    "Validation required",
    "Limitations",
    "Proposed changes",
)
ASSESSMENT_PRIORITIES = (
    "Critical",
    "High",
    "Medium",
    "Low",
    "Informational",
    "Review",
)
PRIVATE_FIELD_PREFIX = "_assessment_"
NO_CHANGE = "None. No change is proposed from this snapshot."
NO_CHANGE_NARRATIVE = "No change is proposed from this snapshot."
PROPOSAL_PREFIX = "Proposal only—not executed: "
PROPOSAL_NARRATIVE_PREFIX = "A proposed change—not executed—is to "
_PRIORITY_NARRATIVES = {
    "Critical": "This is a critical-priority finding.",
    "High": "This is a high-priority finding.",
    "Medium": "This is a medium-priority finding.",
    "Low": "This is a low-priority finding.",
    "Informational": "This is informational.",
    "Review": "This requires review.",
}
_LARGE_TABLE_BYTES = 500 * 1024**3
_PRIORITY_LARGE_TABLE_BYTES = 1024**4


def assessment_narrative_value(field: str, value: str) -> str:
    """Project one structured field into customer-facing natural prose."""
    if field == "Priority":
        return _PRIORITY_NARRATIVES[value]
    if field == "Proposed changes":
        if value == NO_CHANGE:
            return NO_CHANGE_NARRATIVE
        if value.startswith(PROPOSAL_PREFIX):
            proposal = value[len(PROPOSAL_PREFIX):].strip()
            return f"{PROPOSAL_NARRATIVE_PREFIX}{proposal}"
    return value


def priority_from_narrative(value: str) -> str | None:
    """Recover the closed priority value from its deterministic narrative."""
    return next(
        (priority for priority, narrative in _PRIORITY_NARRATIVES.items() if narrative == value),
        None,
    )


@dataclass(frozen=True, order=True)
class DatabaseIdentity:
    database_oid: int


@dataclass(frozen=True, order=True)
class RelationIdentity:
    database_oid: int
    relation_oid: int


@dataclass(frozen=True, order=True)
class IndexIdentity:
    database_oid: int
    index_oid: int


@dataclass(frozen=True, order=True)
class StatementIdentity:
    database_oid: int
    user_oid: int
    query_fingerprint: int


@dataclass
class EvidenceGraph:
    database_rows: dict[DatabaseIdentity, dict[str, list[dict[str, Any]]]] = field(
        default_factory=dict
    )
    database_names: dict[DatabaseIdentity, str] = field(default_factory=dict)
    relation_rows: dict[RelationIdentity, dict[str, list[dict[str, Any]]]] = field(
        default_factory=dict
    )
    statement_rows: dict[StatementIdentity, dict[str, list[dict[str, Any]]]] = field(
        default_factory=dict
    )
    relation_names: dict[RelationIdentity, str] = field(default_factory=dict)
    statement_labels: dict[StatementIdentity, str] = field(default_factory=dict)
    index_names: dict[IndexIdentity, str] = field(default_factory=dict)
    index_sizes: dict[IndexIdentity, set[int]] = field(default_factory=dict)
    index_signals: dict[str, set[IndexIdentity]] = field(
        default_factory=lambda: {"duplicate": set(), "rare": set(), "invalid": set()}
    )
    identity_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IndexMetrics:
    evidence_occurrences: int
    distinct_index_count: int
    duplicate_occurrence_count: int
    multi_signal_index_count: int
    duplicate_rare_overlap: int
    duplicate_invalid_overlap: int
    rare_invalid_overlap: int
    unique_candidate_bytes: int | None
    duplicate_candidate_bytes: int | None
    size_conflict_count: int
    top_indexes: tuple[tuple[str, int | None], ...]


def visible_columns(row: dict[str, Any]) -> list[str]:
    """Return customer-visible columns, excluding reserved engine evidence."""
    return [key for key in row if not str(key).startswith(PRIVATE_FIELD_PREFIX)]


def validate_assessment(assessment: dict[str, Any]) -> None:
    """Reject malformed or actionable assessment payloads."""
    if not isinstance(assessment, dict):
        raise ValueError("Automated DBA Assessment must be an object.")
    if tuple(assessment) != ASSESSMENT_FIELDS:
        raise ValueError("Automated DBA Assessment fields are missing, extra, or reordered.")
    for field_name in ASSESSMENT_FIELDS:
        value = assessment[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Automated DBA Assessment field is empty: {field_name}")
    if assessment["Priority"] not in ASSESSMENT_PRIORITIES:
        raise ValueError("Automated DBA Assessment priority is invalid.")
    proposed = assessment["Proposed changes"]
    if proposed != NO_CHANGE and not proposed.startswith(PROPOSAL_PREFIX):
        raise ValueError("Proposed changes must be explicitly inert.")


def _assessment(
    finding: str,
    priority: str,
    why: str,
    recommendation: str,
    validation: str,
    limitations: str,
    proposed_changes: str = NO_CHANGE,
) -> dict[str, str]:
    assessment = {
        "Finding": finding,
        "Priority": priority,
        "Why it matters": why,
        "Recommendation": recommendation,
        "Validation required": validation,
        "Limitations": limitations,
        "Proposed changes": proposed_changes,
    }
    validate_assessment(assessment)
    return assessment


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "unavailable"
    amount = float(value)
    units = ("bytes", "KiB", "MiB", "GiB", "TiB")
    unit = units[0]
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            break
        amount /= 1024
    return f"{amount:.1f} {unit}"


def _section_map(sections: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(section.get("title")): section
        for section in sections
        if section.get("title")
    }


def _rows(section: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not section or section.get("state", "Collected") != "Collected":
        return []
    return [row for row in section.get("rows", []) if isinstance(row, dict)]


def _relation_name(row: dict[str, Any]) -> str:
    schema = row.get("table_schema") or row.get("schema_name") or row.get("schemaname")
    name = row.get("table_name") or row.get("tablename") or row.get("relname")
    if schema and name:
        return f"{schema}.{name}"
    return str(name or schema or "unknown relation")


def _database_oid(row: dict[str, Any]) -> int | None:
    return _safe_int(row.get("_assessment_database_oid"))


def _database_identity(row: dict[str, Any]) -> DatabaseIdentity | None:
    database_oid = _database_oid(row)
    return DatabaseIdentity(database_oid) if database_oid is not None else None


def _database_name(row: dict[str, Any]) -> str:
    return str(
        row.get("database_name")
        or row.get("datname")
        or f"database OID {_database_oid(row)}"
    )


def _qualified_index_name(row: dict[str, Any], name: Any) -> str:
    index_name = str(name or "unknown index")
    schema = row.get("table_schema") or row.get("schema_name") or row.get("schemaname")
    return f"{schema}.{index_name}" if schema and "." not in index_name else index_name


def _relation_identity(row: dict[str, Any]) -> RelationIdentity | None:
    database_oid = _database_oid(row)
    relation_oid = _safe_int(row.get("_assessment_relation_oid"))
    if database_oid is None or relation_oid is None:
        return None
    return RelationIdentity(database_oid, relation_oid)


def _statement_identity(row: dict[str, Any]) -> StatementIdentity | None:
    database_oid = _database_oid(row)
    user_oid = _safe_int(row.get("_assessment_user_oid"))
    fingerprint = _safe_int(row.get("query_fingerprint"))
    if database_oid is None or user_oid is None or fingerprint is None:
        return None
    return StatementIdentity(database_oid, user_oid, fingerprint)


def _add_index(
    graph: EvidenceGraph,
    signal: str,
    database_oid: int | None,
    index_oid: Any,
    name: Any,
    size: Any,
) -> None:
    parsed_oid = _safe_int(index_oid)
    if database_oid is None or parsed_oid is None:
        graph.identity_warnings.append(f"{signal} index evidence lacked a stable identity")
        return
    identity = IndexIdentity(database_oid, parsed_oid)
    graph.index_signals[signal].add(identity)
    graph.index_names.setdefault(identity, str(name or f"index OID {parsed_oid}"))
    parsed_size = _safe_int(size)
    if parsed_size is not None and parsed_size >= 0:
        graph.index_sizes.setdefault(identity, set()).add(parsed_size)


def build_evidence_graph(sections: Iterable[dict[str, Any]]) -> EvidenceGraph:
    """Build canonical, order-independent evidence indexes."""
    graph = EvidenceGraph()
    section_by_title = _section_map(sections)
    for title, section in sorted(section_by_title.items()):
        for row in _rows(section):
            database = _database_identity(row)
            if database is not None:
                graph.database_rows.setdefault(database, {}).setdefault(title, []).append(row)
                graph.database_names.setdefault(database, _database_name(row))
            relation = _relation_identity(row)
            if relation is not None:
                graph.relation_rows.setdefault(relation, {}).setdefault(title, []).append(row)
                graph.relation_names.setdefault(relation, _relation_name(row))
            statement = _statement_identity(row)
            if statement is not None:
                graph.statement_rows.setdefault(statement, {}).setdefault(title, []).append(row)
                graph.statement_labels.setdefault(
                    statement, f"fingerprint {statement.query_fingerprint}"
                )

    for row in _rows(section_by_title.get("Potential Duplicate Index Candidates")):
        database_oid = _database_oid(row)
        oids = row.get("_assessment_candidate_index_oids")
        names = row.get("candidate_indexes")
        sizes = row.get("_assessment_candidate_index_bytes")
        if not all(isinstance(values, (list, tuple)) for values in (oids, names, sizes)):
            graph.identity_warnings.append("duplicate-index arrays were unavailable")
            continue
        if not (len(oids) == len(names) == len(sizes)):
            graph.identity_warnings.append("duplicate-index arrays were not aligned")
            continue
        candidate_count = _safe_int(row.get("candidate_count"))
        if candidate_count is not None and candidate_count != len(oids):
            graph.identity_warnings.append("duplicate-index candidate count was inconsistent")
            continue
        for index_oid, name, size in zip(oids, names, sizes):
            _add_index(
                graph,
                "duplicate",
                database_oid,
                index_oid,
                _qualified_index_name(row, name),
                size,
            )

    individual_specs = (
        ("Rarely Used Indexes", "rare"),
        ("Invalid Indexes", "invalid"),
    )
    for title, signal in individual_specs:
        for row in _rows(section_by_title.get(title)):
            _add_index(
                graph,
                signal,
                _database_oid(row),
                row.get("_assessment_index_oid"),
                _qualified_index_name(row, row.get("index_name")),
                row.get("_assessment_index_bytes"),
            )
    return graph


def calculate_index_metrics(graph: EvidenceGraph) -> IndexMetrics:
    signal_sets = graph.index_signals
    all_indexes = set().union(*signal_sets.values())
    evidence_occurrences = sum(len(indexes) for indexes in signal_sets.values())
    multi_signal = sum(
        1 for identity in all_indexes
        if sum(identity in indexes for indexes in signal_sets.values()) >= 2
    )
    conflicting = {
        identity for identity, sizes in graph.index_sizes.items() if len(sizes) > 1
    }

    def total_for(indexes: set[IndexIdentity]) -> int | None:
        if indexes & conflicting:
            return None
        known_sizes = [next(iter(graph.index_sizes[index])) for index in indexes if index in graph.index_sizes]
        return sum(known_sizes) if len(known_sizes) == len(indexes) else None

    top_indexes = sorted(
        (
            (graph.index_names.get(identity, f"index OID {identity.index_oid}"),
             next(iter(graph.index_sizes[identity]))
             if identity in graph.index_sizes and len(graph.index_sizes[identity]) == 1
             else None)
            for identity in all_indexes
        ),
        key=lambda item: (-(item[1] if item[1] is not None else -1), item[0]),
    )[:3]
    return IndexMetrics(
        evidence_occurrences=evidence_occurrences,
        distinct_index_count=len(all_indexes),
        duplicate_occurrence_count=evidence_occurrences - len(all_indexes),
        multi_signal_index_count=multi_signal,
        duplicate_rare_overlap=len(signal_sets["duplicate"] & signal_sets["rare"]),
        duplicate_invalid_overlap=len(signal_sets["duplicate"] & signal_sets["invalid"]),
        rare_invalid_overlap=len(signal_sets["rare"] & signal_sets["invalid"]),
        unique_candidate_bytes=total_for(all_indexes),
        duplicate_candidate_bytes=total_for(signal_sets["duplicate"]),
        size_conflict_count=len(conflicting),
        top_indexes=tuple(top_indexes),
    )


def _top_names(names: Iterable[str], limit: int = 3) -> str:
    ordered = sorted(set(names))
    shown = ordered[:limit]
    suffix = f"; {len(ordered) - limit} additional" if len(ordered) > limit else ""
    return ", ".join(shown) + suffix if shown else "none"


def _index_finding(metrics: IndexMetrics, signal_name: str, signal_count: int) -> str:
    top = ", ".join(
        f"{name} ({_format_bytes(size)})" for name, size in metrics.top_indexes
    ) or "none"
    footprint = _format_bytes(metrics.unique_candidate_bytes)
    duplicate_footprint = _format_bytes(metrics.duplicate_candidate_bytes)
    return (
        f"{signal_count} {signal_name} index candidate(s) contributed to "
        f"{metrics.evidence_occurrences} evidence occurrence(s) across "
        f"{metrics.distinct_index_count} distinct index(es), with a deduplicated "
        f"candidate footprint of {footprint} and potential duplicate footprint of "
        f"{duplicate_footprint}. Top objects: {top}. "
        f"Cross-category overlap: duplicate/rare {metrics.duplicate_rare_overlap}, "
        f"duplicate/invalid {metrics.duplicate_invalid_overlap}, "
        f"rare/invalid {metrics.rare_invalid_overlap}."
    )


def _parameter_values(section: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("name")): row
        for row in _rows(section)
        if row.get("name") is not None
    }


def _positive_sum(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> int:
    total = 0
    for row in rows:
        for column in columns:
            value = _safe_int(row.get(column))
            if value is not None and value > 0:
                total += value
    return total


def _base_for_state(section: dict[str, Any]) -> dict[str, str] | None:
    title = str(section.get("title", "Section"))
    state = str(section.get("state", "Collected"))
    if state == "Collected":
        return None
    message = str(section.get("message") or state)
    return _assessment(
        f"{title} evidence was {state}: {message}",
        "Review",
        "A recommendation without the required evidence could be incorrect or unsafe.",
        "Restore collection for this section and rerun the read-only assessment.",
        "Confirm permissions, extension availability, query compatibility, and the report deadline.",
        "No conclusion about the underlying database condition can be drawn from unavailable evidence.",
    )


def _relation_cross_signal_assessment(
    title: str,
    graph: EvidenceGraph,
    required_titles: tuple[str, ...],
) -> tuple[list[RelationIdentity], list[str]]:
    identities = [
        identity
        for identity, evidence in graph.relation_rows.items()
        if all(required in evidence for required in required_titles)
    ]
    names = [graph.relation_names[identity] for identity in identities]
    return identities, names


def _build_section_assessment(
    section: dict[str, Any],
    section_by_title: dict[str, dict[str, Any]],
    graph: EvidenceGraph,
    index_metrics: IndexMetrics,
) -> dict[str, str]:
    state_assessment = _base_for_state(section)
    if state_assessment:
        return state_assessment
    title = str(section.get("title", "Section"))
    rows = _rows(section)

    if title == "Date":
        return _assessment(
            f"The report snapshot is dated {section.get('value') or 'an unspecified time'}.",
            "Informational",
            "All findings must be interpreted within this collection time window.",
            "Compare the snapshot with workload events and changes from the same period.",
            "Confirm the collection timestamp and target instance before using the report.",
            "The timestamp does not establish trend, causality, or current state after collection.",
        )

    if title == "Instance Details":
        properties = {str(row.get("Property")): row.get("Value") for row in rows}
        concerns: list[str] = []
        priority = "Informational"
        if properties.get("Publicly Accessible (DB instance)") is True:
            concerns.append("the DB instance is marked publicly accessible")
            priority = "High"
        if any("Storage Encrypted" in key and value is False for key, value in properties.items()):
            concerns.append("storage encryption is disabled in control-plane metadata")
            priority = "High"
        if any("Deletion Protection" in key and value is False for key, value in properties.items()):
            concerns.append("deletion protection is disabled")
            if priority == "Informational":
                priority = "Medium"
        finding = "; ".join(concerns) if concerns else "No high-confidence instance-metadata concern was identified by the deterministic rules."
        return _assessment(
            finding,
            priority,
            "Connectivity, encryption, and deletion safeguards affect exposure and recoverability.",
            "Review any identified control-plane concern with the service owner and platform security requirements.",
            "Verify current RDS or Aurora cluster metadata, network paths, backup policy, and approved exceptions.",
            "Metadata is a point-in-time control-plane view and does not prove effective network reachability or data classification.",
            PROPOSAL_PREFIX + "prepare an approved infrastructure change for confirmed concerns."
            if concerns else NO_CHANGE,
        )

    if title == "Extensions Installed":
        extensions = [
            f"{row.get('name')} {row.get('version')}".strip()
            for row in rows
            if row.get("name")
        ]
        return _assessment(
            f"The report found {len(extensions)} installed extension(s): {_top_names(extensions)}.",
            "Informational",
            "Extensions can affect engine-upgrade compatibility, security ownership, shared libraries, and operational support boundaries.",
            "Maintain an approved extension inventory and review ownership, support status, and version compatibility before an engine or extension change.",
            "Confirm extension owners, dependent applications, preload requirements, target-engine support, and a tested rollback path.",
            "This snapshot identifies installed extension versions but does not prove whether every extension is actively used or compatible with a future target version.",
        )

    if title == "Total Size of All Databases":
        row = rows[0] if rows else {}
        database_count = _safe_int(row.get("database_count"))
        total_size = row.get("total_size") or _format_bytes(
            _safe_int(row.get("total_bytes"))
        )
        count_text = str(database_count) if database_count is not None else "an unknown number of"
        return _assessment(
            f"The database catalog reports {count_text} non-template database(s) using {total_size} in total.",
            "Informational",
            "Aggregate database size affects storage forecasting, backup and restore duration, and migration capacity, but does not identify which objects are growing.",
            "Trend total and per-database growth against retention policy, recovery objectives, backup duration, and storage headroom.",
            "Confirm historical growth, backup and restore timing, WAL generation, retention changes, and available storage capacity.",
            "This is a point-in-time aggregate and cannot attribute growth to a database, schema, table, index, or workload event.",
        )

    if title == "Top 5 Databases Size":
        database_sizes = [
            f"{row.get('datname') or row.get('database_name')} ({row.get('size') or _format_bytes(_safe_int(row.get('total_bytes')))})"
            for row in rows
        ]
        return _assessment(
            f"The largest returned databases are {_top_names(database_sizes)}.",
            "Informational",
            "Database size influences storage growth, backup and restore duration, maintenance planning, and migration capacity, but size alone does not indicate a performance problem.",
            "Trend database growth and correlate it with retention, workload changes, backup duration, recovery objectives, and available storage headroom.",
            "Confirm historical size growth, storage metrics, backup and restore timing, WAL generation, retention requirements, and forecast assumptions.",
            "This is a point-in-time top-five view and cannot establish growth rate or attribute size to specific relations without additional evidence.",
        )

    if title == "Top 10 Biggest Tables":
        large = [
            row
            for row in rows
            if (_safe_int(row.get("total_bytes")) or 0) >= _LARGE_TABLE_BYTES
        ]
        priority_large = [
            row
            for row in large
            if (_safe_int(row.get("total_bytes")) or 0)
            >= _PRIORITY_LARGE_TABLE_BYTES
        ]
        ranked_items = [
            f"{_relation_name(row)} ({row.get('total_size') or _format_bytes(_safe_int(row.get('total_bytes')))})"
            for row in rows[:3]
        ]
        ranked = ", ".join(ranked_items) or "none"
        if len(rows) > 3:
            ranked += f"; {len(rows) - 3} additional returned relation(s)"
        database_name = (
            str(rows[0].get("_assessment_database_name"))
            if rows and rows[0].get("_assessment_database_name")
            else "the connected database"
        )
        total_count = (
            _safe_int(rows[0].get("_assessment_total_user_table_count"))
            if rows else None
        )
        if total_count is not None:
            scope = (
                f"Showing {len(rows)} of {total_count} user table(s) in database "
                f"{database_name}."
            )
            scope_limitation = (
                "The query returns at most ten user tables and does not include system catalogs."
            )
        else:
            scope = (
                f"The section contains {len(rows)} returned table row(s), but the total "
                "user-table count was not collected; this does not imply that only these "
                "tables exist."
            )
            scope_limitation = (
                "Total table count is unavailable in this evidence, and the query returns "
                "at most ten user tables without system catalogs."
            )
        finding = (
            f"{scope} Largest returned relations, in descending total-size order: "
            f"{ranked}. "
        )
        if priority_large:
            finding += (
                f"{len(priority_large)} relation(s) crossed the 1 TiB priority "
                "review threshold."
            )
            priority = "High"
        elif large:
            finding += (
                f"{len(large)} relation(s) crossed the 500 GiB operational "
                "review threshold."
            )
            priority = "Medium"
        else:
            finding += (
                "No returned relation crossed the 500 GiB operational review threshold."
            )
            priority = "Informational"
        recommendation = (
            "Review growth, retention, access paths, pruning opportunity, maintenance, "
            "WAL, constraints, and migration impact before selecting an architecture response."
            if large
            else "Trend the largest relations and investigate when growth, maintenance duration, retention, or workload impact indicates a concern."
        )
        return _assessment(
            finding,
            priority,
            "Relation size can affect maintenance duration, index cost, backup and migration time, and storage-growth risk, but size alone does not establish a performance problem.",
            recommendation,
            "Collect growth trends, query plans, retention requirements, vacuum/index duration, write rates, storage headroom, and non-production migration evidence before a table-layout change.",
            f"{scope_limitation} Size alone does not justify partitioning, and partitioning does not guarantee lower IOPS.",
            PROPOSAL_PREFIX + "open a large-relation architecture review; do not alter table layout from size alone."
            if large else NO_CHANGE,
        )

    if title == "Tables Without Primary Key":
        names = [_relation_name(row) for row in rows]
        return _assessment(
            f"{len(rows)} returned table(s) lack a primary key: {_top_names(names)}.",
            "Medium" if rows else "Informational",
            "Missing keys can constrain logical replication, row identity, and application integrity patterns, but a synthetic key may not match the data model.",
            "Review application uniqueness, logical-replication requirements, duplicate data, foreign keys, and write impact before proposing a key.",
            "Validate candidate columns for nulls and duplicates, dependent queries, lock duration, storage, and rollback in non-production.",
            "The query reports catalog state only and does not prove that a table needs a new key.",
            PROPOSAL_PREFIX + "design and test a key only for tables with a confirmed requirement."
            if rows else NO_CHANGE,
        )

    if title in ("Potential Duplicate Index Candidates", "Rarely Used Indexes", "Invalid Indexes"):
        signal = {
            "Potential Duplicate Index Candidates": "duplicate",
            "Rarely Used Indexes": "rarely used",
            "Invalid Indexes": "invalid",
        }[title]
        signal_key = "rare" if signal == "rarely used" else signal
        count = len(graph.index_signals[signal_key])
        finding = _index_finding(index_metrics, signal, count)
        limitations = (
            "Statistics can reset and workloads can be seasonal. OIDs are snapshot identities and change after drop/recreate or restore. "
            "No byte total is reported when identities, sizes, or aligned duplicate arrays are incomplete."
        )
        if graph.identity_warnings:
            limitations += f" Identity warnings: {len(graph.identity_warnings)}."
        if index_metrics.size_conflict_count:
            limitations += f" Conflicting sizes were observed for {index_metrics.size_conflict_count} index identity(ies)."
        recommendation = (
            "Validate constraints, uniqueness, predicates, operator classes, included columns, dependencies, scan-counter history, workload cycles, and rollback before any index change."
        )
        return _assessment(
            finding,
            "High" if signal == "invalid" and count else "Medium" if count else "Informational",
            "Redundant indexes can add storage and write maintenance, rarely used indexes may still protect seasonal paths, and invalid indexes need separate cause analysis.",
            recommendation,
            "Capture a representative statistics window, inspect pg_get_indexdef and constraints, confirm application owners, test plans and write impact, and prepare a reversible change procedure.",
            limitations,
            PROPOSAL_PREFIX + "create an index-by-index review plan; no DROP or REINDEX command is approved or executed."
            if count else NO_CHANGE,
        )

    if title == "Top 10 Most Bloated Tables":
        _, correlated_names = _relation_cross_signal_assessment(
            title, graph, ("Top 10 Most Bloated Tables", "Top 10 UPDATE/DELETE Tables")
        )
        estimated_waste = sum(
            _safe_int(row.get("estimated_table_wasted_bytes")) or 0 for row in rows
        )
        return _assessment(
            f"The heuristic returned {len(rows)} table(s) with {_format_bytes(estimated_waste)} estimated table waste; write-activity evidence overlaps for {_top_names(correlated_names)}.",
            "Medium" if rows and correlated_names else "Low" if rows else "Informational",
            "Sustained update/delete churn can create dead tuples and maintenance pressure, but heuristic bloat estimates can be inaccurate.",
            "Validate material candidates with table growth, dead tuples, maintenance history, workload timing, and a more precise bloat measurement before choosing remediation.",
            "Confirm statistics freshness, relation identity, maintenance windows, free storage, lock/WAL impact, replicas, and rollback in non-production.",
            "This is a pinned heuristic, not an exact reclaimable-byte measurement; index waste is aggregated at table level.",
            PROPOSAL_PREFIX + "evaluate targeted online maintenance or per-table autovacuum tuning only after validation; VACUUM FULL is not automatically recommended."
            if correlated_names else NO_CHANGE,
        )

    if title in ("Top 10 Biggest Tables Last Vacuumed", "Top 10 UPDATE/DELETE Tables"):
        _, cross_names = _relation_cross_signal_assessment(
            title, graph, ("Top 10 Biggest Tables Last Vacuumed", "Top 10 UPDATE/DELETE Tables")
        )
        candidates: list[str] = []
        for identity, evidence in graph.relation_rows.items():
            if not all(required in evidence for required in ("Top 10 Biggest Tables Last Vacuumed", "Top 10 UPDATE/DELETE Tables")):
                continue
            maintenance_rows = evidence["Top 10 Biggest Tables Last Vacuumed"]
            write_rows = evidence["Top 10 UPDATE/DELETE Tables"]
            dead = max((_safe_int(row.get("n_dead_tup")) or 0 for row in write_rows), default=0)
            missing_auto = any(row.get("last_autovacuum") is None for row in maintenance_rows)
            if dead > 0 or missing_auto:
                candidates.append(graph.relation_names[identity])
        finding = (
            f"Maintenance and write evidence overlaps for {_top_names(cross_names)}; "
            f"{len(candidates)} relation(s) have dead-tuple or missing-autovacuum signals: {_top_names(candidates)}."
        )
        return _assessment(
            finding,
            "Medium" if candidates else "Low" if rows else "Informational",
            "High update/delete activity can outpace default autovacuum thresholds and increase bloat, stale statistics, and transaction-ID risk.",
            "For confirmed candidates, evaluate per-table autovacuum vacuum/analyze scale factors and thresholds using observed churn and maintenance duration; preserve global defaults unless fleet-wide evidence supports a change.",
            "Measure dead-tuple growth, live-row count, autovacuum frequency/duration, cancellations, locks, I/O/WAL headroom, and query-plan effects across a representative workload window.",
            "Statistics are cumulative and can reset; a null maintenance timestamp does not by itself prove autovacuum failure. Top-ten truncation can omit other candidates.",
            PROPOSAL_PREFIX + "test per-table autovacuum settings for validated candidates in non-production, then use an approved change window."
            if candidates else NO_CHANGE,
        )

    if title == "Key PostgreSQL Parameters":
        parameters = _parameter_values(section)
        work_mem = parameters.get("work_mem", {}).get("setting", "not collected")
        temp_rows = (
            _rows(section_by_title.get("Top 10 Temporary Space Written Queries"))
            + _rows(section_by_title.get("Top 10 Temporary Space Read Queries"))
        )
        temp_blocks = _positive_sum(temp_rows, ("temp_blks_written", "temp_blks_read"))
        log_gaps: list[str] = []
        if temp_blocks and str(parameters.get("log_temp_files", {}).get("setting")) == "-1":
            log_gaps.append("log_temp_files is disabled while temporary I/O was observed")
        statement_rows = _rows(section_by_title.get("Top 10 Statements by Total Execution Time"))
        if statement_rows and str(parameters.get("log_min_duration_statement", {}).get("setting")) == "-1":
            log_gaps.append("log_min_duration_statement is disabled while high-total-time statements were observed")
        if temp_blocks:
            finding = f"work_mem is {work_mem}; statement evidence recorded {temp_blocks} temporary block operation(s)."
            priority = "Medium"
            recommendation = (
                "Inspect the identified plans and concurrent-session/parallel-worker demand, then benchmark scoped work_mem values rather than applying a universal global minimum."
            )
            proposed = PROPOSAL_PREFIX + "benchmark a session- or role-scoped work_mem increase, including 4 MB as one test point, and promote only a measured safe value."
        else:
            finding = f"work_mem is {work_mem}; no positive temporary-block evidence was returned by the bounded statement sections."
            priority = "Informational"
            recommendation = "Keep the current value under observation and collect spill, concurrency, and plan evidence before tuning."
            proposed = NO_CHANGE
        if log_gaps:
            finding += " Observability gaps: " + "; ".join(log_gaps) + "."
            priority = "Medium"
            recommendation += " Also review targeted slow-query and temporary-file logging with retention and cost controls."
            proposed = PROPOSAL_PREFIX + "benchmark a session- or role-scoped work_mem increase, including 4 MB as one test point, and test targeted logging changes in non-production; no parameter group change was made."
        return _assessment(
            finding,
            priority,
            "work_mem is allocated per sort/hash operation and can multiply across sessions and parallel workers; spills can add temporary I/O, while an oversized global value can exhaust memory. Logging gaps can delay diagnosis.",
            recommendation,
            "Use EXPLAIN evidence, temp-byte trends, peak concurrency, parallelism, instance memory headroom, representative latency, log volume, retention cost, and rollback criteria.",
            "Statement lists are top-ten snapshots and pg_stat_statements counters can reset. Temporary blocks do not prove that work_mem is the sole cause, and the safe value is workload-specific.",
            proposed,
        )

    if title == "Total Size of Log Files":
        parameters = _parameter_values(section_by_title.get("Key PostgreSQL Parameters"))
        temp_rows = (
            _rows(section_by_title.get("Top 10 Temporary Space Written Queries"))
            + _rows(section_by_title.get("Top 10 Temporary Space Read Queries"))
        )
        temp_blocks = _positive_sum(temp_rows, ("temp_blks_written", "temp_blks_read"))
        gaps: list[str] = []
        if temp_blocks and str(parameters.get("log_temp_files", {}).get("setting")) == "-1":
            gaps.append("temporary-file logging is disabled despite temporary I/O evidence")
        if _rows(section_by_title.get("Top 10 Statements by Total Execution Time")) and str(parameters.get("log_min_duration_statement", {}).get("setting")) == "-1":
            gaps.append("duration logging is disabled despite high-total-time statement evidence")
        return _assessment(
            ("Logging observability gaps: " + "; ".join(gaps) + ".") if gaps else "No cross-section logging change was justified by the collected parameter and workload evidence.",
            "Medium" if gaps else "Informational",
            "Targeted logging can support diagnosis, but indiscriminate logging can increase volume, cost, and sensitive-data exposure.",
            "Review only evidence-backed logging gaps and define thresholds, export, retention, redaction, and cost controls before changing parameters.",
            "Estimate log volume under representative load, verify CloudWatch export/retention and access controls, test overhead, and define rollback thresholds.",
            "RDS log metadata is a point-in-time inventory; zero reported bytes can reflect service metadata behavior and does not prove an absence of log events.",
            PROPOSAL_PREFIX + "test targeted logging for the identified gaps in non-production and obtain owner approval."
            if gaps else NO_CHANGE,
        )

    if title.startswith("Top 10 ") and ("Queries" in title or "Statements" in title):
        identities = {
            identity
            for identity, evidence in graph.statement_rows.items()
            if title in evidence
        }
        multi_signal = [
            identity for identity in identities
            if len(graph.statement_rows[identity]) > 1
        ]
        window = str(section.get("statement_statistics_window") or "Statistics reset evidence was not supplied.")
        return _assessment(
            f"{len(rows)} statement row(s) were returned; {len(multi_signal)} exact database/user/fingerprint identity(ies) also appear in another statement signal.",
            "Medium" if rows else "Informational",
            "Repeated total-time, read-I/O, or temporary-I/O signals can identify candidates for plan and workload review, but do not establish root cause.",
            "Inspect sanitized candidates with safe EXPLAIN, wait events, call distribution, indexes, cardinality, and application context before proposing SQL or schema changes.",
            "Confirm database OID, role OID, query fingerprint, statistics window, representative load, plan variants, bind sensitivity, and regression tests.",
            f"{window} Query text is normalized and bounded; identical fingerprints across different databases or roles are not merged.",
        )

    if title == "Sequences Nearing Exhaustion":
        names = [f"{row.get('schema_name')}.{row.get('sequence_name')}" for row in rows]
        return _assessment(
            f"{len(rows)} sequence(s) crossed the configured usage-review threshold: {_top_names(names)}.",
            "High" if rows else "Informational",
            "Sequence exhaustion can block inserts, while widening or replacing a sequence can affect dependent columns and applications.",
            "Review growth rate, ownership, dependent column types, generated values, application compatibility, and migration options.",
            "Project exhaustion time from historical growth and test dependency-safe migration and rollback in non-production.",
            "The threshold is a screening signal; percentage used alone does not establish urgency without growth rate.",
            PROPOSAL_PREFIX + "prepare a dependency-aware sequence capacity plan for confirmed risks."
            if rows else NO_CHANGE,
        )

    if title in ("Maximum Used Transaction IDs", "Top 5 Database Age", "Top 5 Table age"):
        age_rows = [
            (row, _safe_int(row.get("age")))
            for row in rows
            if _safe_int(row.get("age")) is not None
        ]
        highest_row, max_age = max(
            age_rows,
            key=lambda item: item[1] or 0,
            default=({}, None),
        )
        hard_limit = 2_147_483_647
        percent = (
            100.0 * max_age / hard_limit if max_age is not None else None
        )
        if title == "Top 5 Table age":
            object_name = _relation_name(highest_row)
        else:
            object_name = str(
                highest_row.get("datname")
                or highest_row.get("database_name")
                or "unknown database"
            )
        if max_age is None:
            finding = "Transaction-ID age could not be interpreted from the returned evidence."
            priority = "Review"
        else:
            finding = (
                f"The highest returned transaction-ID age is {max_age:,} "
                f"({percent:.2f}% of PostgreSQL's hard wraparound limit) for "
                f"{object_name}."
            )
            priority = "High" if max_age >= 1_500_000_000 else "Medium" if max_age >= 1_000_000_000 else "Informational"
        recommendation = (
            "Escalate the age trend and investigate freeze progress, blocked maintenance, and long-running transactions before the remaining margin narrows further."
            if priority in {"High", "Medium"}
            else "Continue trending transaction-ID age and investigate only if growth accelerates, freeze progress stalls, or configured maintenance thresholds are approached."
        )
        return _assessment(
            finding,
            priority,
            "Transaction-ID age can eventually threaten write availability, but risk depends on the configured freeze threshold, growth rate, autovacuum progress, and long-running transactions.",
            recommendation,
            "Compare the age and trend with autovacuum_freeze_max_age, recent vacuum/freeze history, long-running transactions, replica health, and maintenance capacity.",
            "The hard-limit percentage is a screening context, not the configured autovacuum threshold; this snapshot does not establish growth rate and executes no VACUUM or freeze operation.",
        )

    if rows:
        finding = f"{title} returned {len(rows)} evidence row(s); the evidence table remains authoritative."
    else:
        finding = f"{title} returned no matching rows in this snapshot."
    return _assessment(
        finding,
        "Informational",
        "This evidence provides operational context but does not independently justify a database or infrastructure change.",
        "Correlate the section with workload history, trends, service objectives, and recent changes before taking action.",
        "Confirm the collection scope, target, statistics window, representative workload, and any engine-specific semantics.",
        "This is bounded point-in-time evidence; empty results do not prove the condition has never occurred.",
    )


def attach_automated_assessments(
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attach one validated seven-field assessment to every report section."""
    graph = build_evidence_graph(sections)
    metrics = calculate_index_metrics(graph)
    section_by_title = _section_map(sections)
    for section in sections:
        section["assessment"] = _build_section_assessment(
            section, section_by_title, graph, metrics
        )
    return {
        "index_evidence_occurrences": metrics.evidence_occurrences,
        "distinct_index_count": metrics.distinct_index_count,
        "multi_signal_index_count": metrics.multi_signal_index_count,
        "unique_candidate_bytes": metrics.unique_candidate_bytes,
        "identity_warning_count": len(graph.identity_warnings),
    }
