# SQL Server & Oracle (RDS) Upgrade Review — Events + Config Model

IMPORTANT: Microsoft SQL Server and Oracle on RDS do NOT produce a MySQL-style
upgrade-checker precheck log or a PostgreSQL `pg_upgrade_precheck.log` — there is
no single pre-upgrade compatibility report to parse like those engines. Feature 4
for them is primarily an EVENTS + CONFIG REVIEW. HOWEVER (verified 2026-10-06 on a
live RDS SQL Server upgrade), SQL Server DOES expose a parseable native ERROR LOG
via `rds:DescribeDBLogFiles` / `rds:DownloadDBLogFilePortion` (`log/ERROR`,
`log/ERROR.1`, ...), and the engine writes the database-upgrade conversion and any
failures there. So for SQL Server: use events FIRST, and ALSO read `log/ERROR*`
for upgrade detail. Do not fabricate a MySQL/PG-style precheck report.

Verified against:
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.SQLServer.Major.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Overview.html
- https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Major.html
- https://aws.amazon.com/blogs/database/best-practices-for-upgrading-amazon-rds-for-oracle-db-instances-from-12c-to-19c/
- EMPIRICAL (2026-10-06): live RDS SQL Server Express 2017->2019 upgrade; error
  log readable via DownloadDBLogFilePortion; see "SQL Server error log" below.

## What to read
### SQL Server (events + native error log)
1. `rds:DescribeEvents` — look for `upgrade`, `incompatible`, `cannot be
   upgraded`, `is in a state that cannot be upgraded`, `failed to upgrade`.
2. `rds:DescribeDBLogFiles` -> the `log/ERROR*` files; `rds:DownloadDBLogFilePortion`
   to read them. VERIFIED the error log contains:
   - the per-database upgrade conversion, e.g.
     `Converting database 'master' from version 869 to the current version 904`
     and `Database '<db>' running the upgrade step from version X to version Y`
     (these are SUCCESS/progress lines — NOT failures; do not report as errors).
   - structured errors in the form `Error: <number>, Severity: <sev>, State: <st>.`
     followed by the message (e.g. `Error: 3041, Severity: 16` BACKUP failed).
   Classification for SQL Server error-log lines:
   - `Severity: 16-18` or higher, or any `cannot be upgraded`/conversion-failure
     line -> ERROR (blocks/failed the upgrade).
   - deprecation / informational (`This is an informational message only. No user
     action is required.`) -> NOTICE.
   - Treat `Converting database ...`/`running the upgrade step ...` as progress,
     not findings.
3. `rds:DescribeDBEngineVersions` with `ValidUpgradeTarget` to confirm the target
   is reachable (restricted matrix — see the EOL calendar).

### Oracle (events + config review; no comparable native upgrade log exposed)
1. `rds:DescribeEvents` — same upgrade/incompatible/cannot-be-upgraded strings.
2. `rds:DescribeDBEngineVersions` `ValidUpgradeTarget` for the restricted matrix.
Report Oracle findings from events + the config-review checklist below.

Report from events + (SQL Server) the error log + the config review. If there is
no upgrade event and no upgrade lines in the error log, state "no prior upgrade
attempt" — do not imply a missing precheck report.

## Oracle — logs & precheck (doc-grounded; NOT live-verified in this account)
Oracle on RDS does expose parseable artifacts — more than "events only". NOTE:
Oracle RDS was not available in our test account, so the below is grounded in AWS
docs, not reproduced live. Treat as authoritative-but-unverified; confirm live
when an Oracle-enabled account is available.
- **On-demand pre-upgrade precheck (read-only)**: run
  `rdsadmin.rdsadmin_precheck_tasks.precheck_minor_upgrade`. It returns a task_id
  and writes `dbtask-<task_id>.log` to the BDUMP directory, downloadable via
  `rds:DescribeDBLogFiles` / `rds:DownloadDBLogFilePortion`. This is a real,
  parseable precheck result (the closest Oracle analog to the MySQL/PG precheck).
  Source: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Oracle.Precheck.html
- **alert log**: `trace/alert_*.log` (RDS surfaces the Oracle `alert.log`). Upgrade
  activity and `ORA-NNNNN` errors land here. Major upgrades run Oracle scripts
  (`catctl.pl`/`catcon.pl`/`datapatch`); on failure the instance can enter a
  failed state and emit an RDS event.
Parse guidance: in `dbtask-*.log`, read the precheck findings/section; in the
alert log, classify `ORA-` errors (any `ORA-` during the upgrade window => ERROR;
Oracle warnings/informational => WARNING/NOTICE). Still ALSO apply the Oracle
config-readiness checklist below (option group, licensing, matrix). If neither a
precheck log nor upgrade `ORA-` lines exist, state "no prior upgrade attempt".

## SQL Server — config review checklist (classify as ERROR if it blocks)
| Item | Why it matters | Severity if violated |
|---|---|---|
| Target version reachable per upgrade matrix (2016->2017/19/22/25, etc.) | Unsupported hops are rejected | ERROR |
| Database compatibility level | Old compat levels may be unsupported on the target; plan `ALTER DATABASE ... SET COMPATIBILITY_LEVEL` after upgrade | WARNING |
| Option group bound to target version (SQLSERVER_AUDIT, native backup/restore, TDE, etc.) | Options don't carry across major versions automatically | ERROR |
| Parameter group compatible with target | Deprecated params block/alter behavior | WARNING |
| Edition fixed across upgrade (EE/SE/Web/Express) | Edition can't change during a major upgrade | ERROR if a change was assumed |
| Features deprecated/removed in target SQL Server | e.g. old deprecated T-SQL constructs | WARNING |
| Multi-AZ / mirroring + in-use features (e.g. in-memory OLTP) | Some features restrict upgrade paths | WARNING |

## Oracle — config review checklist (classify as ERROR if it blocks)
| Item | Why it matters | Severity if violated |
|---|---|---|
| Target reachable per matrix (12.1->12.2/19c; 18c->19c; 19c->21c/26ai; 21c->26ai) | Restricted matrix; some hops need an intermediate version | ERROR |
| Target RU released same month or later than source RU | Oracle rule for major upgrades | ERROR |
| Target-version OPTION GROUP prepared (matching options: OEM, SQLT, APEX, Spatial/Locator, etc.) | Options are uninstalled/reinstalled across majors; default group is used if none supplied | ERROR |
| Licensing (BYOL vs License Included) and edition (SE2/EE; 26ai is EE-only) | Must match target availability | ERROR |
| Deprecated/desupported features (e.g. Oracle Multimedia desupported in 19c; move to Spatial/Locator) | Breaks dependent objects post-upgrade | WARNING |
| APEX / OEM agent upgrade handled as a separate prep step | Speeds upgrade, avoids failures | WARNING |
| Option group tied to the same VPC | Can't reuse across a VPC change (e.g. restore to another VPC) | WARNING |
| Major downgrade attempted | Not supported | ERROR |

## Remediation framing
Neither engine has a MySQL/PG-style single precheck report, but BOTH expose
parseable logs: SQL Server -> native `log/ERROR*` (VERIFIED); Oracle ->
`dbtask-<task_id>.log` precheck + `trace/alert_*.log` (doc-grounded). So output =
log findings (where present) + a config-readiness checklist. Lead with: the
upgrade-event timeline (if any), any ERROR/`ORA-` lines from the log, whether the
requested target is in the valid upgrade matrix, and option-group / parameter-
group / licensing readiness. Mandatory pre-steps live in the strategy skill.
Never fabricate a MySQL/PG-style precheck report for these engines.

## Mandatory / forced upgrades
Both engines perform mandatory ("forced") upgrades near end of support (Oracle
tracks Oracle's lifecycle; SQL Server tracks Microsoft EOS). Forced upgrades can
break CloudFormation stacks that pin an engine version — flag EOL instances as
action-required and note the CFN risk.
