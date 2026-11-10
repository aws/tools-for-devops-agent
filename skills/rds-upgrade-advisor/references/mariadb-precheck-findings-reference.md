# MariaDB (RDS) Upgrade Findings — Severity & Remediation Reference

MariaDB major upgrades on RDS run `mariadb-upgrade` (and `mysql_upgrade`-style
table checks) rather than the MySQL Shell `util.checkForServerUpgrade` prechecker
used by MySQL 8.x. MariaDB is the CLOSEST engine to MySQL in this toolset, but it
has its OWN removed-feature set and its own upgrade log — do NOT assume the MySQL
numbered-text `PrePatchCompatibility.log` parser applies verbatim.

Verified against:
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/MariaDB.Concepts.VersionMgmt.html
- MariaDB community upgrade documentation (mariadb.com/kb) for removed features.

## The log (what to read)
On a failed major upgrade RDS emits an RDS EVENT and writes upgrade output to the
MariaDB error log (`error/mysql-error.log` family) and any
`*upgrade*`/`PrePatchCompatibility`-style file surfaced by
`rds:DescribeDBLogFiles`. Locate + download the same way as MySQL
(`DescribeEvents` -> `DescribeDBLogFiles` -> `DownloadDBLogFilePortion`). The
format is log-line text, not the MySQL Shell JSON.

## Classification
MariaDB upgrade failures are typically reported as plain error lines. Treat as:
- ERROR — any line that stops the upgrade (incompatible table, crashed/corrupt
  table needing REPAIR, removed system variable in the parameter group, removed
  SQL syntax in a routine/view/trigger).
- WARNING — deprecation notices that do not stop the upgrade.
- NOTICE — informational.
Lead with the RDS event timeline; MariaDB does not emit a MySQL-Shell-style
footer with error/warning counts, so counts come from the lines themselves.

## Common MariaDB major-upgrade blockers -> severity & remediation
| Finding | Severity | Remediation |
|---|---|---|
| Table needs rebuild/repair ("Table upgrade required", crashed/corrupt) | ERROR | Run `mysqlcheck`/`REPAIR TABLE` or `ALTER TABLE ... FORCE`; restore from backup if corrupt. |
| Removed/renamed system variable in custom parameter group | ERROR | Remove the offending parameter from the DB parameter group before retry (common across 10.3->10.6->10.11->11.4). |
| Removed SQL syntax / function in routine, view, trigger | ERROR | Rewrite the object to the supported form; DROP+CREATE. |
| Incompatible storage engine / removed engine (e.g. legacy TokuDB) | ERROR | Convert affected tables to a supported engine (InnoDB) before upgrade. |
| Deprecated authentication plugin | WARNING | Migrate users to a supported auth plugin before relying on them post-upgrade. |
| Reserved-word identifier conflicts in the target version | WARNING | Rename or quote identifiers that collide with new reserved words. |
| Deprecated sql_mode flags | NOTICE | Update sql_mode; non-blocking. |

## Upgrade-path notes (target/recommendation context)
- MariaDB does NOT support skipping across many majors in one step. Upgrade
  along the supported chain (e.g. 10.5 -> 10.6 -> 10.11 -> 11.4); 10.11 and 11.4
  are the LTS landing points.
- RDS MariaDB has NO Extended Support: end of standard support is a hard
  auto-upgrade deadline (see the MariaDB EOL calendar). Flag EOL MariaDB as
  action-required with urgency.
- No Aurora MariaDB exists; all MariaDB resources are standalone/Multi-AZ RDS
  instances (strategy = Blue/Green or in-place or snapshot-restore, same as RDS
  MySQL).

## Cross-engine caveat
Like MySQL, test precheck/upgrade behavior empirically where it matters; the only
VERIFIED cross-engine precheck divergence to date is the Aurora-MySQL stored-
routine gap (MySQL reference). No MariaDB-specific empirical divergence is
recorded yet.

## VERIFIED MariaDB behavior (2026-10-06, live RDS 10.5.28 -> 11.4.13)
Reproduced on a seeded RDS MariaDB instance:
- A stored routine containing `SHOW MASTER STATUS` (the exact object class that
  BLOCKS an RDS-for-MySQL 8.0->8.4 upgrade) did NOT block the MariaDB 10.5->11.4
  major upgrade — the pre-check passed and the upgrade COMPLETED.
- Reason (verified engine ground truth): MariaDB 11.4 has NOT removed
  `SHOW MASTER STATUS` — it still parses and runs on 11.4, and the surviving
  routine `CALL`s fine. MariaDB also supports `SHOW BINLOG STATUS` (its newer
  alias). This is the OPPOSITE of MySQL 8.4, where the statement is removed
  (ER_PARSE_ERROR) and the routine is left non-functional.
GUIDANCE: Do NOT port the MySQL "removed MASTER/SLAVE syntax" ERROR class to
MariaDB. MariaDB's removed-feature set is its own; the MySQL non-inclusive /
replication-statement blocker does not apply. MariaDB 10.5->11.4 of ordinary
objects is a clean, non-blocking upgrade. Focus MariaDB feature-4 on the real
blocker classes in the table above (removed sysvars in the parameter group,
tables needing rebuild/repair, removed storage engines), confirmed via RDS
events + the MariaDB error log — NOT the MySQL routine-syntax check.
