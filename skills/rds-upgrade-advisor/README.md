# RDS / Aurora Upgrade Advisor Skill

A skill for AWS DevOps Agent that performs **read-only** major-version
upgrade-readiness assessments for Amazon RDS and Amazon Aurora databases across
engines, from a single database up to an account-wide fleet. It grounds every
support-date claim in authoritative, per-engine support calendars bundled in
`references/`, and never modifies, upgrades, or reconfigures a resource.

## Purpose

RDS/Aurora major-version upgrades fail or are forced on an unplanned schedule
when databases drift past end of standard support, breaking precheck findings go
unread, or the wrong upgrade method is chosen for a Multi-AZ / clustered / global
topology. This skill systematically answers, for every database in scope:

1. What version is it on, and what is its support status
   (DEPRECATED / EXTENDED_SUPPORT / UPCOMING_EOL / SUPPORTED)?
2. What is its configuration (region, AZ/Multi-AZ, cluster topology, replicas,
   global membership, class/storage, tags)?
3. Did a PAST upgrade attempt fail or get blocked, and if so, what did the engine
   report (findings classified ERROR / WARNING / NOTICE, with remediation)?
4. What is the safest upgrade method (Blue/Green, in-place, or snapshot-restore)
   for its engine and topology?

It is designed to run both interactively ("why did this upgrade fail?", "how
should I upgrade this?") and as a scheduled, account-wide audit that produces a
concise chat summary plus a complete downloadable artifact.

## Supported engines

MySQL, Aurora MySQL, PostgreSQL, Aurora PostgreSQL, MariaDB, Oracle, SQL Server,
and Db2. The skill detects each database's `Engine` and dispatches to the correct
EOL calendar, past-upgrade evidence parser, and strategy caveats. See the engine
dispatch table in `SKILL.md`.

## Key capabilities

- **Version & EOL classification** — per-engine support calendars in
  `references/` (standard support end, RDS Extended Support where it applies,
  deprecation). Extended Support exists only for MySQL and PostgreSQL; for
  MariaDB / Oracle / SQL Server / Db2, past end of standard support is treated as
  a forced-upgrade / DEPRECATED condition.
- **Config view** — identifier, region, AZ/Multi-AZ, cluster writer/readers,
  global-cluster membership, read replicas, class/storage, edition/licensing, and
  tags, with Aurora clusters counted as one database (de-duplicated from members).
- **Past failed/blocked upgrade analysis** — reads the engine-specific evidence
  (MySQL `PrePatchCompatibility.log`, Aurora MySQL JSON `upgrade-prechecks.log`,
  PostgreSQL `pg_upgrade` logs, MariaDB upgrade/error log, SQL Server native
  `log/ERROR*`, Oracle `dbtask`/alert logs, Db2 `db2diag.log`) and classifies each
  finding ERROR / WARNING / NOTICE with ordered remediation. Only non-completed
  (failed/blocked) upgrades are in scope.
- **Upgrade strategy** — ranks Blue/Green vs in-place vs snapshot-restore for the
  resource's topology, with engine-specific caveats (e.g. PostgreSQL/Db2 replicas
  auto-upgrade with the primary; Oracle/SQL Server have no Blue/Green and need
  option groups; MariaDB has no major-skipping).
- **At-scale audit mode** — a two-pass account-wide run (discover + classify, then
  parse only failed/blocked logs) with a per-engine chat roll-up governed by a
  `DETAIL_THRESHOLD` and a full downloadable artifact.

## Prerequisites

### IAM permissions

The DevOps Agent role needs read-only access to RDS and EC2 (for the region
sweep). All calls are describe/read only — no mutating calls are ever made:

```
ec2:DescribeRegions
rds:DescribeDBInstances
rds:DescribeDBClusters
rds:DescribeGlobalClusters
rds:DescribeDBEngineVersions
rds:ListTagsForResource
rds:DescribeEvents
rds:DescribeDBLogFiles
rds:DownloadDBLogFilePortion
```

## Files

- `SKILL.md` — the skill definition (engine dispatch, Phase 1 version/EOL, Phase 2
  past-upgrade log analysis, Phase 3 strategy, and at-scale/scheduled audit mode).
- `references/` — per-engine support calendars and upgrade-finding references:
  - EOL calendars: `mysql-eol-calendar.md`, `postgresql-eol-calendar.md`,
    `mariadb-eol-calendar.md`, `oracle-eol-calendar.md`,
    `sqlserver-eol-calendar.md`, `db2-eol-calendar.md`.
  - Upgrade-finding references: `precheck-findings-reference.md` (MySQL / Aurora
    MySQL), `postgresql-precheck-findings-reference.md`,
    `mariadb-precheck-findings-reference.md`,
    `sqlserver-oracle-review-reference.md`, `db2-upgrade-findings-reference.md`.

## Notes on coverage

- MySQL, Aurora MySQL, PostgreSQL, MariaDB, and SQL Server behaviors were
  validated live against real RDS/Aurora upgrade evidence.
- Oracle and Db2 guidance is documentation-grounded (not yet live-validated,
  because those engines were unavailable in the test account); the skill marks
  those paths accordingly and relies on events + a config-readiness review rather
  than fabricating a precheck report.
- The RDS-vs-Aurora MySQL precheck-strictness divergence noted in `SKILL.md` is an
  empirical finding (not AWS-documented) and is labeled as such.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
> It is strictly read-only and advisory: it never initiates or executes an
> upgrade. Always confirm support dates against current AWS documentation, since
> support calendars drift over time.
