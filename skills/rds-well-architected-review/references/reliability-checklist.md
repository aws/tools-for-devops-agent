# RDS / Aurora Reliability Best Practices Checklist

## High Availability

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 1 | Multi-AZ enabled (production) | `MultiAZ=true` for RDS; ≥1 reader in different AZ for Aurora | HIGH |
| 2 | Subnet group AZ spread | DB subnet group spans ≥ 2 AZs | HIGH |
| 3 | Aurora reader count | ≥ 1 reader instance for production clusters | MEDIUM |
| 4 | Aurora reader AZ diversity | Readers distributed across AZs | MEDIUM |
| 5 | RDS Proxy (high connection workloads) | Proxy configured for failover speed | LOW |

## Backup & Recovery

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 6 | Backup retention | `BackupRetentionPeriod` > 0 | CRITICAL if 0 |
| 7 | Backup retention (production) | ≥ 7 days for production workloads | HIGH if < 7 |
| 8 | Backup window | Non-business-hours window configured | LOW |
| 9 | Deletion protection | `DeletionProtection=true` for production | HIGH |
| 10 | Manual snapshots | Reviewed for retention (> 90 days flagged) | LOW |
| 11 | Point-in-time recovery | Automated backups enabled (retention > 0) | CRITICAL |

## Disaster Recovery

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 12 | Cross-region DR (tier-1) | Cross-region read replica or Aurora Global Database | MEDIUM |
| 13 | Aurora Global Database | Configured for tier-1 workloads requiring < 1s RPO | MEDIUM |
| 14 | Cross-region snapshots | Automated copy to DR region | LOW |
| 15 | DR testing | Documented and tested recovery procedure | MEDIUM |

## Replication Health

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 16 | ReplicaLag (RDS) | 7-day max < 30 seconds | HIGH if > 30s; CRITICAL if > 300s |
| 17 | AuroraReplicaLag | 7-day max < 100 ms | HIGH if > 1000 ms |
| 18 | Replication errors | No `replication has stopped` events | CRITICAL |
| 19 | Read replica instance class | Same or larger than source | MEDIUM |

## Version & Maintenance

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 20 | Auto minor version upgrade | `AutoMinorVersionUpgrade=true` (non-production) | MEDIUM |
| 21 | Engine version currency | Within standard support window | HIGH if approaching EOL |
| 22 | Pending maintenance | Applied within scheduled window | MEDIUM |
| 23 | Maintenance window | Non-business-hours, weekly | LOW |

### Compare current version to the latest release, then recommend an upgrade

Do not judge currency from a static list — determine the current version, the latest
available minor/major, and the **valid upgrade targets** live, then recommend a path
and call out the new features/fixes the upgrade unlocks.

1. **Get valid upgrade targets for the running version (live, not hardcoded):**
   ```
   aws rds describe-db-engine-versions \
     --engine <engine> --engine-version <current-version> \
     --query 'DBEngineVersions[0].{Current:EngineVersion,MinorTargets:ValidUpgradeTarget[?IsMajorVersionUpgrade==`false`].EngineVersion,MajorTargets:ValidUpgradeTarget[?IsMajorVersionUpgrade==`true`].EngineVersion}'
   ```
   List all versions/status for the engine: `aws rds describe-db-engine-versions --engine <engine> --query 'DBEngineVersions[*].[EngineVersion,Status]' --output table`.

2. **Check end-of-standard-support / deprecation** for both the major and the specific
   minor version (minors can reach EOL before the major deadline). Recommend an
   in-place minor upgrade to the latest supported minor, and plan the major upgrade
   before the deprecation date (use blue/green to minimize downtime).

3. **Identify the new features/benefits** the target version provides (performance,
   security, replication, vacuum/optimizer improvements, new extensions) from the
   engine release notes, and include them in the recommendation so the team knows what
   they gain by upgrading.

**Recommendation guidance:**
- Current minor ≠ latest supported minor → recommend minor upgrade (LOW, or higher if the running minor is near/past EOL).
- Current major approaching/past end of standard support → recommend major upgrade (HIGH), citing the deprecation date and target version.
- Always confirm valid targets via `describe-db-engine-versions` (targets are version- and Region-specific).

**References:**
- Upgrading a DB instance engine version (major vs minor, blue/green): https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Upgrading.html
- RDS deprecation guidance & version-support policy: https://aws.amazon.com/rds/faqs/
- RDS for PostgreSQL versions & release calendar: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_PostgreSQL.html and PostgreSQL release notes: https://www.postgresql.org/docs/release/
- RDS for MySQL versions & release calendar: https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_MySQL.html
- Aurora PostgreSQL updates/release notes (Aurora-specific features): https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/AuroraPostgreSQL.Updates.html
- Aurora MySQL updates/release notes: https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/Welcome.html
- Amazon Aurora versions & upgrade planning — release calendars: Aurora PostgreSQL https://docs.aws.amazon.com/AmazonRDS/latest/AuroraPostgreSQLReleaseNotes/aurorapostgresql-release-calendar.html · Aurora MySQL https://docs.aws.amazon.com/AmazonRDS/latest/AuroraMySQLReleaseNotes/AuroraMySQL.release-calendars.html

## Data Integrity

| # | Check | Expected State | Severity if Missing |
|---|-------|---------------|---------------------|
| 24 | Transaction ID wraparound (PostgreSQL) | > 500M transactions remaining | HIGH if < 1B remaining |
| 25 | Autovacuum running | `autovacuum=on`, tables being vacuumed | HIGH if disabled |
| 26 | Storage headroom | FreeStorageSpace > 20% | HIGH if < 20% |
| 27 | Storage autoscaling | `MaxAllocatedStorage` configured | LOW |

## RDS Events Indicating Reliability Issues

| Event Pattern | Severity | Required Action |
|---------------|----------|-----------------|
| `failover` (unplanned) | HIGH | Investigate root cause |
| `storage-full` / `low-storage` | CRITICAL | Emergency storage increase |
| `out of memory` | HIGH | Instance class upgrade |
| `automated-backup-failed` | HIGH | Investigate immediately |
| `replication-error` | HIGH | Fix replication |
| `restart` (unplanned) | HIGH | Investigate logs |
| `instance-stopped` (production) | HIGH | Verify intentional |
