# Changelog

All notable changes to the RDS / Aurora Upgrade Advisor skill are documented here.

## 1.1.0

Restructured to follow the Agent Skills best-practices spec; no change in
functionality (content relocated and reformatted, not altered).

- Moved the engine-dispatch lookup table and per-engine version-major parsing
  rules out of the SKILL.md body into `references/engine-dispatch.md`, linked with
  a load-when trigger (progressive disclosure).
- Moved the at-scale chat + artifact output specification out of the body into
  `assets/audit-output-format.md` (DETAIL_THRESHOLD, status glyph,
  completed-upgrade scope note, chat roll-up format, required artifact title and
  per-engine sections), linked with a load-when trigger.
- Converted each phase's ordered steps to `- [ ] Step N:` checkbox-checklist
  format with matching `### Step N:` detail sections.
- Added explicit load-when triggers to every `references/` and `assets/` link.
- Added a self-validation section (check own output before presenting).
- Body reduced from 451 to ~308 lines.

## 1.0.0

Initial release.

- Read-only, multi-engine RDS / Aurora major-version upgrade-readiness advisor
  covering MySQL, Aurora MySQL, PostgreSQL, Aurora PostgreSQL, MariaDB, Oracle,
  SQL Server, and Db2.
- **Phase 1 — Version & EOL classification:** account/region discovery, config
  view, Aurora cluster de-duplication (one cluster = one database), per-engine
  major-version parsing, and classification against bundled per-engine support
  calendars (DEPRECATED / EXTENDED_SUPPORT / UPCOMING_EOL / SUPPORTED). RDS
  Extended Support modeled for MySQL and PostgreSQL only; past end of standard
  support treated as DEPRECATED / forced-upgrade for MariaDB, Oracle, SQL Server,
  and Db2.
- **Phase 2 — Past failed/blocked upgrade analysis:** engine-specific evidence
  dispatch and parsing (MySQL `PrePatchCompatibility.log`, Aurora MySQL JSON
  `upgrade-prechecks.log`, PostgreSQL `pg_upgrade` logs, MariaDB upgrade/error
  log, SQL Server native `log/ERROR*`, Oracle `dbtask`/alert logs, Db2
  `db2diag.log`), with findings classified ERROR / WARNING / NOTICE and ordered
  remediation. Only non-completed (failed/blocked) upgrades are in scope;
  completed-upgrade prechecks (including "upgraded-with-warnings") are excluded.
- **Phase 3 — Upgrade strategy:** ranks Blue/Green vs in-place vs snapshot-restore
  for the resource topology, with engine-specific caveats (PostgreSQL/Db2 replica
  auto-upgrade, Oracle/SQL Server option groups and no Blue/Green, MariaDB
  no-major-skipping chain) and mandatory pre-steps.
- **At-scale / scheduled audit mode:** two-pass account-wide run (discover +
  classify, then parse only failed/blocked logs), a concise per-engine chat
  roll-up governed by `DETAIL_THRESHOLD` (10), and a complete downloadable
  artifact with per-engine sections and a count-by-support-status chart.
- Bundled references: six per-engine EOL calendars and five per-engine
  upgrade-finding references.
- Consolidated from three precursor skills (`rds-version-eol-check`,
  `rds-upgrade-log-analysis`, `rds-upgrade-strategy`) and the at-scale custom-agent
  orchestration prompt into a single skill, with no change in functionality.
