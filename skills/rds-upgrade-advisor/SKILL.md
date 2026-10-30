---
name: rds-upgrade-advisor
description: Use this skill to assess Amazon RDS and Aurora databases for
  major-version upgrade readiness across engines (MySQL, Aurora MySQL, PostgreSQL,
  Aurora PostgreSQL, MariaDB, Oracle, SQL Server, Db2). Use it whenever a user asks
  to run an RDS or Aurora upgrade-readiness audit or review; which databases are
  outdated, end-of-life, deprecated, approaching end of support, or on RDS Extended
  Support; whether a database qualifies for RDS Extended Support or is forced to
  upgrade; why a past major-version upgrade failed, did not complete, or was
  blocked, or what its precheck or PrePatchCompatibility log reported; how to
  upgrade a database with minimal downtime, or whether to use Blue/Green, in-place,
  or snapshot-restore. For each database it reports the current version and support
  status, a configuration view, analysis of any past failed or blocked upgrade
  evidence classified ERROR / WARNING / NOTICE with remediation, and an ordered
  upgrade strategy. Read-only; it never modifies, upgrades, or initiates a change.
metadata:
  author: leachwi
  version: "1.1.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon RDS"
  aws-devops-agent-skills.technical-domains: "Databases"
---

# RDS / Aurora Upgrade Advisor (multi-engine, read-only)

A READ-ONLY advisor that assesses Amazon RDS and Aurora databases — across engines
(MySQL, Aurora MySQL, PostgreSQL, Aurora PostgreSQL, MariaDB, Oracle, SQL Server,
Db2) — for major-version upgrade readiness, from a single database up to accounts
with hundreds of databases. It discovers resources with built-in AWS tools,
classifies each engine version against authoritative per-engine support calendars,
reads and classifies any evidence a PAST upgrade attempt left behind, and
recommends an ordered upgrade strategy. It NEVER modifies, upgrades, deletes, or
reconfigures any resource — it only describes, reads logs, and recommends.

## What it produces for each database (one audit pass)
1. Current engine version.
2. Support status: DEPRECATED / EXTENDED_SUPPORT / UPCOMING_EOL / SUPPORTED.
3. Config view: identifier, region, AZ / Multi-AZ, cluster writer/readers,
   global-cluster membership, read replicas, tags, instance class/storage, status.
4. Past upgrade prechecks/failures: if an upgrade was already ATTEMPTED and
   FAILED/BLOCKED, each finding classified ERROR / WARNING / NOTICE.
5. Ordered remediation (ERROR first) plus a suggested upgrade method.

## Engine dispatch (which calendar, artifact, and reference to use)
This skill is MULTI-ENGINE. Detect each database's `Engine` and dispatch to the
right per-engine EOL calendar, upgrade-evidence parser, and strategy caveats. Read
[engine dispatch reference](references/engine-dispatch.md) when you first detect a
database's `Engine`, to pick its calendar, past-upgrade artifact, findings
reference, and version-major parsing rule. If an engine is not listed there, mark
it UNKNOWN and recommend manual review.

## When to use
- "Which databases are end-of-life / on Extended Support / approaching EOL?"
- "Run an RDS/Aurora upgrade-readiness audit for region X" (any/all engines).
- "Why did the upgrade of <db> fail?" / "Summarize the precheck errors for <db>."
- "What's the safest way to upgrade <db> to <target>?" / "Blue/Green or in-place?"
- On a schedule, as a proactive account-wide audit.

## Scope, assumptions, and guardrails
- Phase-2 evidence only exists if an upgrade was already ATTEMPTED. RDS runs
  mandatory prechecks and, on incompatibility, cancels and records evidence. If
  none was attempted, there is no log — say "no prior upgrade attempt" (not an
  error) and recommend attempting the upgrade to generate it.
- There is NO live checker utility. Do not connect to or run checks against a
  database; only read what the engine already produced.
- Do NOT rely on memory for support dates — always read the engine's calendar file.
- READ-ONLY. Never recommend executing, nor initiate, any upgrade or remediation;
  those are separate, human-approved workflows.

## Tools (all READ-ONLY, via built-in use_aws)
`ec2:DescribeRegions` (to enumerate regions for an account-wide sweep),
`rds:DescribeDBInstances`, `rds:DescribeDBClusters`, `rds:DescribeGlobalClusters`,
`rds:DescribeDBEngineVersions`, `rds:ListTagsForResource`, `rds:DescribeEvents`,
`rds:DescribeDBLogFiles`, `rds:DownloadDBLogFilePortion`. No mutating calls, ever.
See [the least-privilege IAM policy](references/iam-policy.json) when provisioning or scoping the DevOps Agent role's permissions for this skill.

---

# Phase 1 — Discover databases, config view, and version/EOL status

- [ ] Step 1: Discover databases and read their config.
- [ ] Step 2: Count each database once (Aurora de-dup).
- [ ] Step 3: Determine the tracked major version per engine.
- [ ] Step 4: Classify each version against the engine's calendar.
- [ ] Step 5: Detect past FAILED/BLOCKED upgrade attempts (detection only).

### Step 1: Discover databases and read config
REGION SCOPE: unless the user names specific region(s), scan ALL regions — do not
limit to the agent's home region. Enumerate enabled regions
(`ec2:DescribeRegions`) and call `rds:DescribeDBInstances` and
`rds:DescribeDBClusters` in EACH, then aggregate; record each database's region.
If the user names region(s), scan exactly those. Keep ALL supported engines (do
not filter to MySQL). For each, record the CONFIG VIEW:
- identifier (`DBInstanceIdentifier` / `DBClusterIdentifier`), region
- `Engine` and `EngineVersion`
- `MultiAZ` (instance) / whether it is an Aurora cluster
- Availability Zone(s); for clusters, member AZs and writer/reader roles
- cluster member count (`DBClusterMembers`) and writer (`IsClusterWriter`)
- `GlobalClusterIdentifier` if part of a global database
- read replicas (`ReadReplicaDBInstanceIdentifiers`)
- `Edition`/licensing where present (`LicenseModel`)
- tags (`rds:ListTagsForResource` on the ARN)
- storage, instance class, status (`DBInstanceStatus` / cluster `Status`)

If the user only asks to "view config", output the config view and stop.

### Step 2: Count each database once (Aurora de-dup)
An Aurora cluster is ONE database — do not also count its member instances (the
writer/readers returned by `DescribeDBInstances` with a `DBClusterIdentifier`) as
separate databases. Count = standalone RDS instances + Aurora clusters. Fold each
Aurora member into its cluster as topology detail. De-duplicate before counting so
the roll-up total equals the sum of the per-engine counts. An Aurora cluster
counts under its cluster `Engine` (`aurora-mysql` / `aurora-postgresql`); do not
also tally its writer instance under the same engine.

### Step 3: Determine the tracked major version per engine
Parse the major using the per-engine rule in
[engine dispatch reference](references/engine-dispatch.md) — load it if you have
not already. Aurora and RDS of the same community version can have DIFFERENT
dates, so always use the correct engine section of the calendar.

### Step 4: Classify each version against the engine's calendar
Open the engine's calendar file (identified in Step 3). Read the engine's EOL
calendar when classifying that engine's version — load
[mysql/Aurora MySQL](references/mysql-eol-calendar.md) for `mysql`/`aurora-mysql`,
[PostgreSQL](references/postgresql-eol-calendar.md) for
`postgres`/`aurora-postgresql`, [MariaDB](references/mariadb-eol-calendar.md) for
`mariadb`, [Oracle](references/oracle-eol-calendar.md) for `oracle-*`,
[SQL Server](references/sqlserver-eol-calendar.md) for `sqlserver-*`, or
[Db2](references/db2-eol-calendar.md) for `db2-*`. For each resource, compare
TODAY to the dates:
- After end of Extended Support (or deprecated, no Extended tier) -> **DEPRECATED**.
- After end of standard support but on/before end of Extended Support ->
  **EXTENDED_SUPPORT** (paid; MySQL/PostgreSQL only — for other engines, past end
  of standard support = DEPRECATED / forced-upgrade imminent).
- Within 180 days before end of standard support -> **UPCOMING_EOL**.
- Otherwise -> **SUPPORTED**. Major not in the table -> **UNKNOWN** (manual review).

### Step 5: Detect past FAILED/BLOCKED upgrade attempts (detection only)
For each database check whether a past upgrade attempt FAILED or was BLOCKED and
left evidence — use `rds:DescribeEvents` and `rds:DescribeDBLogFiles` only. Only
NON-completed upgrades are in scope: the attempt rolled back / was canceled and
the current `EngineVersion` is still the OLD major (events say "cannot be
upgraded", "PreUpgrade checks failed", "pg_upgrade reported failure", rollback).
A database whose upgrade SUCCEEDED (now on the new major / "upgrade complete") is
OUT OF SCOPE — do not flag its precheck. Record which databases have in-scope
evidence; do not download/parse here (that is Phase 2). If none, note "no prior
upgrade attempt" once — not an error.

Phase 1 output: a prioritized, multi-engine list of databases needing attention
(DEPRECATED, then EXTENDED_SUPPORT, then UPCOMING_EOL) — or "all supported" — each
with id, engine, current version, status, end-of-standard-support date + days
remaining, recommended target, and the cited calendar source URL.

---

# Phase 2 — Analyze past failed/blocked upgrade evidence

Read-only analysis of what the ENGINE already produced during a prior upgrade
attempt — this does NOT run any checker itself. The artifact differs sharply by
engine, so dispatch on `Engine` using
[engine dispatch reference](references/engine-dispatch.md). Parse ONLY databases
whose prior upgrade attempt FAILED or was BLOCKED (detected in Phase 1 Step 5);
SKIP any database that successfully upgraded.

- [ ] Step 1: Read upgrade events (all engines).
- [ ] Step 2: Locate and read the engine's artifact (if any).
- [ ] Step 3: Parse and classify findings using the engine's reference.
- [ ] Step 4: Remediate, ordered ERROR -> WARNING -> NOTICE.

### Step 1: Read upgrade events (all engines)
Call `rds:DescribeEvents`. Flag events containing: `upgrade`, `precheck`,
`prerequisites`, `incompatible`, `cannot be upgraded`, `prechecks failed`,
`PreUpgrade checks failed`. These confirm an attempt and give the timeline. For
SQL Server/Oracle this is the PRIMARY (often only) evidence.

### Step 2: Locate and read the engine's artifact (if any)
Use `rds:DescribeDBLogFiles` to find the file, then
`rds:DownloadDBLogFilePortion` (page with the marker until `AdditionalDataPending`
is false). Use `rds:DescribeDBEngineVersions` (`ValidUpgradeTarget`) to confirm the
target is reachable. The artifact per engine is in
[engine dispatch reference](references/engine-dispatch.md). Notes: SQL Server has
no MySQL/PG-style precheck report — read `log/ERROR*` plus events; do not fabricate
one. Oracle/Db2 are doc-grounded (events + `dbtask`/alert or `db2diag.log`). If a
log is expected but absent while events show a failure, report from events and note
the log was not retained.

### Step 3: Parse and classify findings using the engine's reference
Load the engine's findings reference (from the dispatch table) when parsing its
evidence: read
[MySQL / Aurora MySQL findings](references/precheck-findings-reference.md) for
`mysql`/`aurora-mysql`,
[PostgreSQL findings](references/postgresql-precheck-findings-reference.md) for
`postgres`/`aurora-postgresql`,
[MariaDB findings](references/mariadb-precheck-findings-reference.md) for
`mariadb`, and
[SQL Server / Oracle review](references/sqlserver-oracle-review-reference.md) for
`sqlserver-*`/`oracle-*`, or
[Db2 findings](references/db2-upgrade-findings-reference.md) for `db2-*`. Classify
each finding ERROR / WARNING / NOTICE per that reference; never downgrade a level
the engine reports. (MySQL = numbered-text with footer totals; Aurora MySQL = JSON
`detectedProblems[].level`; PostgreSQL = per-database items under "need to be
corrected before upgrade", each an ERROR; MariaDB = error-log lines; SQL Server =
`Error: n, Severity: s` lines + config checklist; Oracle/Db2 per their references.)

### Step 4: Remediate
Give the specific remediation for each finding class from the engine's reference,
ordered ERROR -> WARNING -> NOTICE. Report authoritative counts where the engine
provides them (MySQL/Aurora MySQL footer); otherwise count from findings/events.

### Cross-engine precheck divergence (EMPIRICAL — MySQL only, so far)
RDS-for-MySQL and Aurora MySQL run DIFFERENT precheck rule sets for stored routines
with removed replication / non-inclusive syntax (SHOW MASTER/SLAVE STATUS): RDS
reports ERROR and BLOCKS; Aurora reports only WARNING and ALLOWS the upgrade,
leaving the routine non-functional (ERROR 3512) on 8.4. Reproduced on Aurora
3.04->8.4.7 and 3.13->8.4.8. Treat such an Aurora WARNING as HIGH-PRIORITY
action-required. This is EMPIRICAL (not AWS-documented). No equivalent divergence
is verified for other engines — do not assume RDS==Aurora precheck strictness;
test where it matters.

---

# Phase 3 — Recommend an upgrade strategy

Read-only, advisory. Recommends an ordered upgrade approach for a resource based on
its configuration and engine. Does NOT execute anything.

- [ ] Step 1: Read configuration and confirm the target is reachable.
- [ ] Step 2: Rank the methods (Blue/Green vs in-place vs snapshot-restore).
- [ ] Step 3: Apply the engine-specific caveats.
- [ ] Step 4: Output ordered options with mandatory pre-steps.

### Step 1: Read configuration and confirm the target is reachable
Use the config already gathered in Phase 1 (`Engine`, `MultiAZ`, cluster/Aurora,
`GlobalClusterIdentifier`, read replicas, edition/licensing). Confirm the target
is reachable with `rds:DescribeDBEngineVersions` `ValidUpgradeTarget` (critical for
SQL Server/Oracle restricted matrices and the "no major skipping" MariaDB chain).

### Step 2: Rank the methods (engine-agnostic core)
- **Blue/Green** — lowest downtime (~5s switchover); replicates Multi-AZ
  automatically. Rank #1 for production, Multi-AZ, or clustered/Aurora. Available
  for RDS MySQL, RDS MariaDB, RDS PostgreSQL, Aurora MySQL, Aurora PostgreSQL. NOT
  available for RDS Oracle, RDS SQL Server, or RDS Db2 — drop it for those engines.
- **In-place** — simplest; full downtime for the upgrade duration. Multi-AZ
  upgrades primary+standby together. Rank #1 only for non-prod single-AZ. Always
  snapshot first; rollback = restore snapshot (Oracle/SQL Server: no in-place
  downgrade, so the snapshot is the only rollback).
- **Snapshot-restore** — restore a copy, upgrade it, validate side-by-side, cut
  over. Best for trial upgrades / staging and as the rollback fallback. The primary
  low-risk path for Oracle/SQL Server where Blue/Green is unavailable.

If global database: note Blue/Green topology constraints and plan Region order.

### Step 3: Apply the engine-specific caveats (include the ones matching the engine)
- **MySQL / Aurora MySQL**: upgrade read replicas BEFORE the source. Resolve all
  ERROR precheck findings first. Reserved-word + removed-syntax routines are the
  common blocker.
- **PostgreSQL / Aurora PostgreSQL**: in-Region read replicas upgrade
  AUTOMATICALLY with the primary (you CANNOT upgrade them first — the opposite of
  MySQL); Multi-AZ DB CLUSTER replicas are not auto-upgraded. Prepare a
  TARGET-version parameter group first. Upgrade EXTENSIONS (e.g. PostGIS) to a
  target-compatible version first. Clear prepared transactions, logical
  replication slots, `reg*` types, and invalid databases first.
- **MariaDB**: no major skipping — upgrade along the chain (10.5->10.6->10.11->
  11.4); 10.11/11.4 are LTS targets. No Aurora MariaDB. No Extended Support, so EOL
  is a hard auto-upgrade deadline. Remove removed system variables from the
  parameter group first.
- **Oracle**: NO Blue/Green. Prepare a TARGET-version OPTION GROUP matching the
  source options (OEM, APEX, SQLT, Spatial/Locator) first; options are
  uninstalled/reinstalled across majors. Target RU must be same-month-or-later than
  source RU. Honor licensing (BYOL/LI) and edition (26ai is EE-only). No downgrade.
- **SQL Server**: NO Blue/Green. Confirm the target is in the upgrade matrix
  (2016->2017/19/22/25; can't skip from 2008). Bind a target-version OPTION GROUP
  (audit, native backup/restore, TDE) and parameter group. Edition can't change
  during the upgrade. Review database compatibility level post-upgrade.
- **Db2**: NO Blue/Green. Supported major path 11.5.9 -> 12.1. Read replicas
  auto-upgrade WITH the source (like PostgreSQL, NOT MySQL). IBM Customer ID + Site
  ID must be set in the parameter group for Standard/Advanced upgrades. Community
  Edition is 12.1-only and compute-limited. No RDS Extended Support — IBM base EOS
  is the deadline. Pre-11.5 migrates in via backup/restore (not in-place).

### Step 4: Output ordered options with mandatory pre-steps
List methods in ranked order with downtime, rationale, caveats. Universal
pre-steps (tailor the replica step to the engine):
1. Resolve all ERROR-level precheck/review findings (Phase 2).
2. Prepare/validate a target-version parameter group (and option group for
   Oracle/SQL Server) against the target version.
3. Take a manual snapshot immediately before the upgrade.
4. Replicas: MySQL/MariaDB — upgrade replicas BEFORE the source; PostgreSQL/Db2 —
   replicas upgrade automatically with the primary (or promote/delete to exclude).

---

# At-scale / scheduled audit mode

When auditing a whole account (tens to hundreds of databases) or running on a
schedule, run the three phases as two passes:
- **Pass A — Discovery (cheap, all databases):** run Phase 1 across the region
  scope (ALL regions unless the user names some). For every database: version +
  EOL status + config view, and DETECT whether an in-scope failed/blocked upgrade
  log exists (Phase 1 Step 5). Do NOT download/parse logs in this pass.
- **Pass B — Log analysis (Phase 2, failed/blocked only):** download and classify
  the detected logs, but ONLY for databases whose prior upgrade FAILED or was
  BLOCKED. SKIP any database that upgraded successfully. There is no interactive
  prompt — full detail goes to the artifact so the chat stays concise.

For the two output surfaces (concise chat response and full downloadable
artifact), load [at-scale audit output format](assets/audit-output-format.md) when
producing an account-wide or scheduled audit's output. It defines the
DETAIL_THRESHOLD, the per-database status glyph, the completed-upgrade scope note,
the chat roll-up format, and the required artifact title and per-engine sections.

## Validation (check your own output before presenting)
Before presenting results, verify:
- The roll-up total equals the sum of the per-engine counts (confirms Aurora
  de-dup in Phase 1 Step 2 — one cluster counted once, not also as its writer).
- Every non-SUPPORTED database has a recommended target version and a cited
  calendar source URL for its support-date claim.
- Each support status was read from the engine's calendar file, not from memory,
  and the correct per-engine calendar was used (Aurora vs RDS dates differ).
- Only FAILED/BLOCKED upgrades were parsed in Phase 2; no completed-upgrade
  precheck was reported.
- In an account-wide audit, the artifact's first line is the required titled H1.

## Success criteria
A prioritized, multi-engine, remediation-oriented upgrade-readiness assessment:
each database's version, support status (correct per-engine calendar used), config
view, any FAILED/BLOCKED past-upgrade findings classified ERROR/WARNING/NOTICE with
remediation, and an engine-correct ranked upgrade strategy — delivered as a concise
chat summary plus a complete downloadable artifact at scale, and never initiating
or recommending execution of an upgrade.
