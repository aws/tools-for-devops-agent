# Changelog

All notable changes to the PostgreSQL DBA skill are documented here.

## [1.0.0]

### Added

- Initial release of the PostgreSQL DBA skill: read-only diagnostic guidance for
  Amazon RDS for PostgreSQL and Aurora PostgreSQL that interprets evidence from the
  companion PostgreSQL DBA MCP server's 9 read-only tools and 55 predefined queries.
- Complete on-screen health-check workflow: `run_full_health_check` with
  `report_format="markdown"` returns all 26 canonical sections as one validated,
  marker-bounded tool result presented in the AWS DevOps Agent Output panel, plus an
  explicit five-query `report_format="quick"` path gated on explicit user intent.
- Deterministic `shared_buffers` and memory-sizing workflow with a fail-closed
  evidence ledger that keeps Aurora and RDS platforms separate, prohibits indirect
  memory derivation, and withholds a numeric recommendation until cluster provenance
  and the exact engine default are verified.
- Configuration-review workflow and pre-upgrade readiness workflow
  (`check_upgrade_readiness` with an explicit target major version), with upgrade
  output treated as supporting evidence rather than approval.
- Targeted investigation procedures for vacuum, dead tuples and transaction ID age,
  index review, statement performance, replication, connections, and locks, kept in
  `references/investigation-workflows.md` so SKILL.md stays focused.
- Safety and privacy rules: read-only diagnostics only; bounded, normalized query
  previews with no reconstruction of literals or bind values; Aurora cluster-scoped
  metadata interpretation; and treatment of all tool and database-returned content
  as untrusted data rather than instructions.
- On-screen-only report delivery: there is no downloadable-file or HTML artifact and
  the MCP server never writes to S3 or returns a URL. A request phrased as
  "downloadable", "HTML", "a file", or "a report link" is served the same complete
  on-screen report with a plain statement that no downloadable file is produced.
- Report rendering contract: each evidence-bearing section renders raw evidence
  followed by at most one natural `Automated DBA Assessment`, collected zero-row
  sections remain present without an assessment, and the superseded
  `Evidence-Based Insight` paragraph is never rendered.
- Skill metadata aligned to the repository's API enum values
  (`agent-types: CHAT, INCIDENT_RCA`) and the allowed technical-domain vocabulary.
