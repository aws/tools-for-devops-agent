# Engine Dispatch — calendars, upgrade artifacts, and references

Lookup table mapping each RDS `Engine` value to its EOL calendar (Phase 1), its
past-upgrade evidence artifact and findings reference (Phase 2), and its
version-major parsing rule. Load this when you first detect a database's `Engine`
and need to pick the right per-engine files and parsing logic.

## Engine → calendar + artifact + reference

| RDS `Engine` value(s) | EOL calendar (Phase 1) | Past-upgrade artifact | Findings reference (Phase 2) |
|---|---|---|---|
| `mysql` | `references/mysql-eol-calendar.md` | `PrePatchCompatibility.log` (numbered text) | `references/precheck-findings-reference.md` |
| `aurora-mysql` | `references/mysql-eol-calendar.md` | `upgrade-prechecks.log` (JSON) | `references/precheck-findings-reference.md` |
| `postgres`, `aurora-postgresql` | `references/postgresql-eol-calendar.md` | `pg_upgrade_precheck.log` (+ `pg_upgrade_internal.log`, server log) | `references/postgresql-precheck-findings-reference.md` |
| `mariadb` | `references/mariadb-eol-calendar.md` | upgrade events + MariaDB error log | `references/mariadb-precheck-findings-reference.md` |
| `oracle-ee`, `oracle-ee-cdb`, `oracle-se2`, `oracle-se2-cdb` | `references/oracle-eol-calendar.md` | upgrade EVENTS + precheck `dbtask-<id>.log` + `trace/alert_*.log` (doc-grounded) | `references/sqlserver-oracle-review-reference.md` |
| `sqlserver-ee`, `sqlserver-se`, `sqlserver-ex`, `sqlserver-web` | `references/sqlserver-eol-calendar.md` | upgrade EVENTS + native `log/ERROR*` (parseable) | `references/sqlserver-oracle-review-reference.md` |
| `db2-se`, `db2-ae`, `db2-ce` | `references/db2-eol-calendar.md` | upgrade EVENTS + Db2 `db2diag.log` (doc-grounded) | `references/db2-upgrade-findings-reference.md` |

If an engine is none of the above, mark it UNKNOWN and recommend manual review.

## Version-major parsing (per engine)
- RDS `mysql`: first two components (`8.0.42` -> `8.0`).
- `aurora-mysql`: component after `mysql_aurora.` (`8.0.mysql_aurora.3.10.3` ->
  `3`); Aurora 8.4 appears as `8.4.mysql_aurora.8.4.x`.
- `postgres` / `aurora-postgresql`: single integer from v10 (`16.4` -> `16`);
  pre-10 two-part (`9.6.22` -> `9.6`).
- `mariadb`: two-part (`10.6.14` -> `10.6`; note `10.11` > `10.6`).
- `oracle-*`: leading release number (`19.0.0.0.ru-...` -> `19`).
- `sqlserver-*`: map build major to the SQL Server YEAR (`15.x` -> 2019,
  `16.x` -> 2022, `17.x` -> 2025, `14.x` -> 2017, `13.x` -> 2016).
- `db2-*`: first two components (`11.5.9.0.sb...` -> `11.5`; `12.1.5.0...` ->
  `12.1`).

Aurora and RDS of the same community version can have DIFFERENT dates — always
use the correct engine section of the calendar.

## RDS Extended Support applicability
RDS Extended Support exists ONLY for MySQL and PostgreSQL. MariaDB, Oracle, SQL
Server, and Db2 have NO RDS Extended Support tier: past end of standard support
(for Db2, IBM base EOS) means a forced/mandatory upgrade — classify as DEPRECATED
and flag the CloudFormation forced-upgrade risk.
