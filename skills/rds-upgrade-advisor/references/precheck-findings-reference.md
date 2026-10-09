# MySQL / Aurora MySQL Precheck Findings — Severity & Remediation Reference

Authoritative knowledge for classifying and remediating findings in RDS-for-MySQL
`PrePatchCompatibility.log` and Aurora MySQL `upgrade-prechecks.log`. The skill
uses this to label each finding ERROR / WARNING / NOTICE and to give ordered
remediation. Verified against:
- https://repost.aws/knowledge-center/rds-mysql-preupgrade-failure
- https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/AuroraMySQL.upgrade-prechecks.html

## Severity meaning (both engines)
- **ERROR** — blocks the upgrade. MUST be fixed before retrying. Report first.
- **WARNING** — no fatal error, but a potential issue. Review before upgrading.
- **NOTICE** — no known compatibility error; informational. Review in error logs.

Order remediation output ERROR → WARNING → NOTICE. Use the log's own reported
level; never downgrade a level the log reports.

## How each log reports severity
- **RDS for MySQL** (`PrePatchCompatibility.log`): numbered-section TEXT report.
  Sections are NOT individually tagged with a level; a footer gives totals
  (`Errors: N`, `Warnings: N`, `Database Objects Affected: N`). Infer per-section
  severity from the message text using the table below and these ERROR signals:
  a parser "syntax error"; "isn't allowed" / "is not allowed"; removed
  MASTER/SLAVE statements ("Don't use SQL statements that contain MASTER or
  SLAVE"); "must have"/"must be"; corruption. Everything else that fired is
  WARNING-class unless the table says otherwise.
- **Aurora MySQL** (`upgrade-prechecks.log`): JSON. `checksPerformed[]` each has
  `id`, `title`, `status`, and `detectedProblems[]`. IMPORTANT: `status` is the
  query status (`OK` = ran fine; `ERROR` = the precheck QUERY failed to run —
  NOT a data incompatibility). The real severity is `detectedProblems[].level`
  (Error/Warning/Notice). Footer: `errorCount`/`warningCount`/`noticeCount`.
  Drop checks with no `detectedProblems` and `status: OK`.

## RDS-for-MySQL precheck messages → severity (from re:Post)
| Message (substring to match) | Severity |
|---|---|
| Usage of old temporal type | ERROR |
| Table names in the mysql schema conflicting with new tables | ERROR |
| Partitioned tables using engines with non native partitioning | ERROR |
| Foreign key constraint names longer than 64 characters | ERROR |
| ENUM/SET column definitions containing elements longer than 255 characters | ERROR |
| Usage of partitioned tables in shared tablespaces | ERROR |
| Circular directory references in tablespace data file paths | ERROR |
| Usage of removed functions | ERROR |
| Usage of removed GROUP BY ASC/DESC syntax | ERROR |
| Removed system variables for error logging to the system log | ERROR |
| Removed system variables | ERROR |
| Schema inconsistencies resulting from file removal or corruption | ERROR |
| The definer column for mysql.events cannot be null or blank | ERROR |
| Tables with dangling FULLTEXT index reference | ERROR |
| Routines with deprecated keywords in definition | ERROR |
| DB instance must have enough free disk space | ERROR |
| The tables with redundant row format can't have an index larger than 767 bytes | ERROR |
| Column definition mismatch between InnoDB Data Dictionary and actual table definition | ERROR |
| MySQL syntax check for routine-like objects (syntax error in routine/view/trigger) | ERROR |
| Non-inclusive language in SQL statements (MASTER/SLAVE) — 8.4 | ERROR |
| Usage of db objects with names conflicting with new reserved keywords | WARNING |
| Usage of obsolete MAXDB sql_mode flag | WARNING |
| System variables with new default values | WARNING |
| Creating indexes larger than 767 bytes on tables with redundant row format | WARNING |
| Check for deprecated or invalid user authentication methods | WARNING |
| Checks for user privileges that will be removed | WARNING |
| Usage of utf8mb3 charset | NOTICE |
| Usage of obsolete sql_mode flags | NOTICE |
| Issues reported by 'check table x for upgrade' command | ERROR or WARNING or NOTICE (use the level in the message) |

## Remediation guidance by finding class (order ERROR first)
- **Removed function / removed syntax / removed GROUP BY ASC-DESC** (ERROR):
  Rewrite the SQL. Search routines, views, triggers, generated columns, default
  expressions for the removed construct and replace with the supported form.
- **Routine/view/trigger syntax error, incl. MASTER/SLAVE (non-inclusive)** (ERROR):
  Edit the object. Replace `SHOW MASTER STATUS`→`SHOW BINARY LOG STATUS`,
  `SHOW SLAVE STATUS`→`SHOW REPLICA STATUS`, `CHANGE MASTER`/`START SLAVE`→their
  REPLICA/SOURCE equivalents; then DROP+CREATE / CREATE OR REPLACE.
- **Old temporal type** (ERROR): `ALTER TABLE ... FORCE` (or dump/reload) to
  rebuild affected tables in the modern temporal format.
- **FK constraint name > 64 chars** (ERROR): recreate the FKs with names ≤ 64.
- **ENUM/SET element > 255 chars** (ERROR): shorten the element definitions.
- **Column definition mismatch / dictionary inconsistency / corruption** (ERROR):
  `ALTER TABLE ... FORCE` to rebuild; run `CHECK TABLE`/`REPAIR TABLE` on flagged
  tables; restore from backup if corrupt.
- **Removed system variables** (ERROR): remove the offending parameters from the
  custom DB parameter group. (Note: RDS 8.0→8.4 validation may not always enforce
  this — reconcile against the actual log.)
- **Not enough free disk space** (ERROR): increase allocated storage, then retry.
- **mysql.events definer null/blank** (ERROR): set a valid definer on the events.
- **Dangling FULLTEXT index** (ERROR): drop/recreate the FULLTEXT index or table.
- **Reserved-keyword identifiers** (WARNING): rename the identifiers, or quote
  them everywhere; prefer renaming.
- **System variables with new defaults** (WARNING): review customized params
  against target-version defaults; confirm intended.
- **Deprecated auth method** (WARNING): migrate users to caching_sha2_password.
- **Privileges to be removed (e.g. SET_USER_ID)** (WARNING): review affected
  users; re-grant equivalents post-upgrade if needed.
- **utf8mb3 / obsolete sql_mode** (NOTICE): plan migration to utf8mb4 / update
  sql_mode; non-blocking.

## Cross-engine precheck divergence (VERIFIED 2026-10-05 — not AWS-documented)
The MySQL 8.4 engine treats removed syntax identically on RDS-for-MySQL and
Aurora MySQL (e.g. `SHOW MASTER STATUS` / `SHOW SLAVE STATUS` return ER_PARSE_ERROR
1064 on both 8.4.11 and 8.4.8). The engines differ ONLY in precheck strictness:
- RDS-for-MySQL precheck runs a strict routine-body syntax check (+ non-inclusive
  language check) → reports ERROR → cancels the upgrade.
- Aurora MySQL precheck has NO strict routine-grammar check; it flags the same
  routine only under `auroraUpgradeCheckNonInclusiveLanguageForStoredRoutines`
  with `level: Warning` (status OK) → errorCount 0 → the upgrade COMPLETES,
  leaving the routine present but non-functional (ERROR 3512 "Failed to load
  routine" when called on 8.4). Reproduced on Aurora 3.04→8.4.7 and 3.13→8.4.8.
Guidance: when an Aurora WARNING is in this removed-syntax / non-inclusive-language
routine class, treat it as HIGH-PRIORITY action-required (will break post-upgrade),
and note that RDS-for-MySQL blocks the identical object. Grounding = MySQL 8.4
release notes (statement removal) + AWS blogs documenting the two engines run
different check sets. The "Aurora allows it through" part is an EMPIRICAL finding,
not stated in public AWS docs. Proven scope: stored-routine bodies only — do NOT
generalize to all object classes.

## Upgrade paths (for target/recommendation context)
RDS for MySQL and Aurora MySQL run these prechecks for 5.7→8.0 and 8.0→8.4
(Aurora v2→v3 and v3→8.4). Always recommend resolving ALL ERROR findings before
a retry; WARNING/NOTICE can be scheduled but should be reviewed.
