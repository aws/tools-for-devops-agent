# PostgreSQL / Aurora PostgreSQL Upgrade Precheck Findings — Severity & Remediation Reference

Authoritative knowledge for reading and classifying RDS/Aurora PostgreSQL major-
version upgrade logs. PostgreSQL major upgrades use the `pg_upgrade` utility,
which produces a DIFFERENT artifact from the MySQL numbered-text / JSON formats.
Verified against:
- https://repost.aws/knowledge-center/rds-postgresql-version-upgrade-issues
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.PostgreSQL.MajorVersion.Process.html
- https://repost.aws/knowledge-center/rds-postgresql-upgrade-postgis
- https://aws.amazon.com/blogs/database/best-practices-for-upgrading-amazon-rds-to-major-and-minor-versions-of-postgresql/

## The logs (what to read)
RDS runs a precheck procedure during a major upgrade and, on failure, emits an
RDS EVENT plus log files. Locate via `rds:DescribeDBLogFiles`; download with
`rds:DownloadDBLogFilePortion` (page to the end). The log files appear under the
`error/` prefix with a timestamp suffix. VERIFIED live (RDS PG 13->16,
2026-10-06) — the exact set emitted on a precheck failure:
- `error/pg_upgrade_internal.log.<ts>` — the pg_upgrade consistency-check run and
  the FATAL reason. PRIMARY source for "why the upgrade failed its checks" (this
  is where the blocker and the `fatal : pg_upgrade reported failure for <check>`
  line appear). Read this first.
- `error/pg_upgrade_server.log.<ts>` — the old-cluster server start/stop log
  during the check (usually just confirms the check ran).
- A per-check DETAIL file naming the offending objects, e.g.
  `error/tables_using_reg.txt.<ts>` for the reg*-type check (lists
  `<db>.<schema>.<table>.<column>`). Different blockers emit differently named
  detail files; read any `error/*.txt.<ts>` produced alongside the upgrade logs.
- The regular PostgreSQL `error/postgresql.log` — engine-specific issues (e.g.
  extension errors) that the check references.
NOTE: historically some docs/paths reference a `pg_upgrade_precheck.log`; on
current RDS the authoritative failure detail is in `pg_upgrade_internal.log` +
the per-check `*.txt` detail file. Match on content, not just the filename.

An RDS event confirms the attempt + blocker, e.g. (VERIFIED): `Database instance
is in a state that cannot be upgraded: fatal : pg_upgrade reported failure for
check_for_reg_data_type_usage`. Older/other wording:  `PreUpgrade checks failed:
... not compatible with the target engine version. Please check the precheck log
file for more details`.

## Log shape (pg_upgrade_internal.log)
NOT numbered sections and NOT JSON. It is pg_upgrade console output: a series of
`Checking for <thing> ... ok` lines, then on the first failure a `fatal :
pg_upgrade reported failure for <check_name>` line followed by an explanation and
a pointer to the detail file. Example (VERIFIED live):
```
Checking for reg* data types in user tables                   executing: ...
fatal : pg_upgrade reported failure for check_for_reg_data_type_usage
Your installation contains one of the reg* data types in user tables.
These data types reference system OIDs that are not preserved by
pg_upgrade, so this cluster cannot currently be upgraded.  You can
drop the problem columns and restart the upgrade.
A list of the problem columns is in the file:
    .../tables_using_reg.txt
```
The matching detail file (`tables_using_reg.txt`) then lists:
```
In database: postgres
  public.advtest_regcol.fn
```
Some older/other failures instead use a banner form:
```
----------- Upgrade could not be run on <timestamp> -----------
The instance could not be upgraded from <src> to <tgt> because of following reasons.
Please take appropriate action on databases that have usages incompatible ...
- Following usages in database '<db>' need to be corrected before upgrade:
-- <specific incompatibility message>
----------------------- END OF LOG ----------------------
```
Classification rule: every item under "need to be corrected before upgrade" is an
ERROR (pg_upgrade is pass/fail — a precheck failure BLOCKS the upgrade; there is
no WARNING tier in the precheck itself). Treat advisory items found only in the
best-practices docs / server log (e.g. "consider larger instance for many large
objects") as WARNING/NOTICE. Report the `from <src> to <tgt>` path and the
per-database grouping verbatim.

## PostgreSQL precheck blockers -> severity & remediation (all ERROR unless noted)
| Finding (match in log) | Severity | Remediation |
|---|---|---|
| Open prepared transactions (`pg_prepared_xacts`) | ERROR | `COMMIT PREPARED` / `ROLLBACK PREPARED` all open 2-phase txns before retry. Check: `SELECT count(*) FROM pg_catalog.pg_prepared_xacts;` |
| `reg*` data types in user objects (regproc, regprocedure, regoper, regoperator, regconfig, regdictionary) | ERROR | Remove/alter columns using these types (only `regtype`/`regclass` survive). pg_upgrade cannot persist them. |
| Unsupported / incompatible extension (e.g. PostGIS + address_standardizer, postgis_tiger_geocoder, postgis_topology, postgis_raster) | ERROR | `ALTER EXTENSION ... UPDATE` to a version supported on the target BEFORE upgrading; upgrade PostGIS dependents together. |
| Logical replication slots present | ERROR | Confirm purpose; if unused, drop: `SELECT pg_drop_replication_slot(slot_name)` for non-physical slots. pglogical slots must also be dropped. (PG17+ can retain slots on non-replicas if WAL fully consumed.) |
| Invalid databases (`pg_database.datconnlimit = -2`, interrupted DROP DATABASE) | ERROR | `DROP DATABASE <invalid_db>` the flagged databases. |
| Unsupported DB instance class for target version | ERROR | Modify to a class supported by the target PostgreSQL version first. |
| Custom parameter group not compatible with target | ERROR | Prepare a target-version parameter group (default or custom) before upgrade. |
| Millions of large objects (`pg_largeobject_metadata`) | WARNING | Not a hard block, but pg_dump/pg_restore can OOM. Scale to >=32 GB RAM for 25-30M+ large objects; clean up orphaned LOs. |
| Unconsumed WAL held by logical slots (PG17+) | ERROR | Ensure all transactions/logical-decoding messages are consumed from the slot before upgrade; the log names the problem slots. |
| Multi-AZ cluster with flow_control on (source < 17.8 / 18.2) | ERROR | Disable flow_control (remove from `shared_preload_libraries`, reboot) before upgrade. |

## Extensions: the most common real-world blocker
PostGIS is the canonical case. The precheck fails if PostGIS (or a dependent:
address_standardizer, address_standardizer_data_us, postgis_tiger_geocoder,
postgis_topology, postgis_raster) is at a version not supported on the target.
Remediation is ALWAYS: upgrade the extension in place to a target-compatible
version first (`ALTER EXTENSION postgis UPDATE TO '<ver>';`), then retry. Check
installed vs available: `SELECT * FROM pg_available_extensions WHERE name LIKE
'%postgis%';`.

## Read replicas (strategy context, not a precheck error)
In-Region read replicas are upgraded automatically WITH the primary (the primary
waits for replicas). You cannot upgrade PG read replicas separately. Multi-AZ DB
CLUSTER read replicas are NOT auto-upgraded (replication goes to `terminated`).
This differs from MySQL (where you upgrade replicas BEFORE the source) — see the
strategy skill.

## Aurora PostgreSQL vs RDS PostgreSQL
Both use `pg_upgrade` and the same precheck blocker classes. Per the verified
MySQL cross-engine lesson, do NOT assume the two run identical precheck
strictness — if a specific finding's behavior matters, TEST it empirically on
both. No PostgreSQL-specific divergence has been verified yet (unlike the Aurora
MySQL stored-routine gap); label any such claim as empirical only once tested.
