# IBM Db2 (RDS) Upgrade Findings — Severity & Remediation Reference

RDS for Db2 major upgrades (11.5.9 -> 12.1) use IBM's native Db2 upgrade tooling.
Db2 does NOT produce a MySQL-style upgrade-checker log or a PostgreSQL
`pg_upgrade_precheck.log`. Evidence of a past attempt comes from RDS EVENTS plus
Db2's native diagnostic log (`db2diag.log`), which RDS exposes.

Verified against:
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Db2.Concepts.VersionMgmt.html
- https://aws.amazon.com/blogs/database/announcing-amazon-rds-for-db2-12-1-with-additional-community-edition/
- https://aws.amazon.com/rds/db2/faqs/
- IBM `db2ckupgrade` / `db2diag.log` documentation.
NOTE: this reference is DOC-GROUNDED, not reproduced live in our test account
(no failed Db2 upgrade was staged). Confirm the exact log filenames/paths live
when a Db2 instance is available.

## The logs (what to read)
1. `rds:DescribeEvents` — upgrade start/finish + any `cannot be upgraded` /
   incompatible / failed messages. Primary confirmation of an attempt.
2. `rds:DescribeDBLogFiles` + `rds:DownloadDBLogFilePortion` — Db2's native
   diagnostic log is surfaced by RDS (look for `db2diag.log` under the Db2 log
   path, plus any upgrade-step output). Db2 writes upgrade progress and errors
   here as `ADM####` / `SQL####N` messages.
3. IBM's pre-upgrade checker `db2ckupgrade` runs as part of the upgrade; its
   failures surface in the upgrade output / db2diag.log and in the RDS event.

## Classification (Db2 message severities)
Db2 diagnostic messages carry a level; map them:
- `SQLnnnnN` (the trailing `N` = error) or `ADMnnnnE` (E = error), or any
  `cannot be upgraded` / `db2ckupgrade` failure -> ERROR (blocks the upgrade).
- `ADMnnnnW` / `SQLnnnnW` (warning) -> WARNING.
- `ADMnnnnI` / informational -> NOTICE.
Lead with the RDS event timeline; Db2 does not emit a single footer count, so
count findings from the messages.

## Common Db2 major-upgrade blockers -> severity & remediation
| Finding | Severity | Remediation |
|---|---|---|
| Missing IBM Customer ID / Site ID parameter (required for SE/AE upgrades) | ERROR | Set the IBM customer ID + site ID in the DB parameter group before upgrading (RDS Db2 requires them for Standard/Advanced). |
| `db2ckupgrade` reports incompatible objects (deprecated types, unsupported features) | ERROR | Resolve the flagged objects per the db2ckupgrade output before retrying. |
| Database not in a consistent/quiesced state | ERROR | Ensure the database is consistent (no in-doubt transactions); let RDS quiesce and retry. |
| Insufficient storage/log space for upgrade | ERROR | Increase allocated storage / log space, then retry. |
| Deprecated configuration parameters | WARNING | Review deprecated DB/DBM cfg params against 12.1; adjust in the parameter group. |
| Edition change at upgrade (SE/AE -> CE) compute limits | WARNING | CE enforces 4 vCPU / 8 GB; only choose CE if the workload fits. |

## Strategy / upgrade-path notes
- Supported major path: **11.5.9 -> 12.1**. Pre-11.5 must migrate in via
  backup/restore first (not an in-place upgrade target).
- **Read replicas are upgraded automatically with the source** (like PostgreSQL;
  the OPPOSITE of the MySQL "upgrade replicas first" rule).
- IBM Customer ID + Site ID remain REQUIRED in the parameter group for Standard
  and Advanced edition upgrades; Community Edition is 12.1-only and compute-limited.
- No Blue/Green for Db2 — use in-place or snapshot-restore (take a manual snapshot
  first; a pre-upgrade snapshot is the rollback path).
- No RDS Extended Support for Db2 — past IBM base EOS is a hard migrate deadline.

## Cross-engine caveat
Doc-grounded only; the single VERIFIED cross-engine precheck divergence remains
the Aurora-MySQL stored-routine gap (see the MySQL reference). Confirm Db2
upgrade-log specifics live when an instance is available.
