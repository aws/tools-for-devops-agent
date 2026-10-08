# Backup — Check Definitions

> **Read `overview.md` first.** It holds the Severity Model, Status Values, the Evidence
> Guardrails (observed-data-only), and the public AWS API / `AWS/FSx` metric reference that
> govern every check below. Load this pillar file when you run this pillar's checks.

## Backup (7 checks)

### BKP-01 — Backup configured

- **Severity**: High
- **API**: `backup list-protected-resources`, cross-referenced with `fsx describe-volumes`
- **Logic**: List AWS Backup protected resources and match them to the RW (`OntapVolumeType = RW`)
  volumes on the in-scope file systems.
- **Status**: Pass — every RW volume is a protected resource. Warning — at least one but not all RW
  volumes protected. Fail — no volumes protected.
- **Recommendation (Fail/Warning)**: Expand the AWS Backup plan to cover all production RW volumes.
- **Fields**: `fileSystemId`, `volumeId`, `protected` (bool), `status`, `severity`

### BKP-02 — Recovery points exist

- **Severity**: High
- **API**: `backup list-recovery-points-by-resource`
- **Logic**: For each protected volume, confirm at least one recent recovery point exists.
- **Status**: Pass — all protected volumes have recent recovery points. Warning — some but not all do.
  Fail — no recovery points for any volume.
- **Recommendation (Fail/Warning)**: Verify backup jobs are running and producing recovery points for
  every protected volume.
- **Fields**: `resourceArn`, `recoveryPointCount`, `latestRecoveryPointAge`, `status`, `severity`

### BKP-03 — SnapMirror (DP) relationships exist

- **Severity**: High
- **API**: `fsx describe-volumes`
- **Logic**: Count DP volumes (`OntapConfiguration.OntapVolumeType = DP`) and compare to production RW
  volumes. DP volumes are the destination endpoints of SnapMirror relationships and are visible via the
  public FSx API; relationship *health and lag* are not exposed by AWS APIs and are out of scope for
  this review.
- **Status**: Pass — all production RW volumes have corresponding DP volumes. Warning — at least one DP
  volume exists but not all RW volumes are covered. Fail — no DP volumes found.
- **Recommendation (Fail/Warning)**: No/partial DP coverage — SnapMirror may not be configured for all
  production data. Ensure each production volume has a replication relationship.
- **Fields**: `fileSystemId`, `rwVolumeCount`, `dpVolumeCount`, `status`, `severity`

### BKP-07 — File-system automatic backups enabled

- **Severity**: High
- **API**: `fsx describe-file-systems`
- **Logic**: Check `OntapConfiguration.AutomaticBackupRetentionDays > 0` and
  `DailyAutomaticBackupStartTime` is set.
- **Status**: Pass — retention > 0 and start time set. Fail — retention is 0/null (no FS-level backups).
- **Recommendation (Fail)**: Enable automatic backups — set retention (7–35 days) and a start time
  aligned to off-peak. FS-level backups cover all volumes automatically, including newly created ones,
  preventing gaps when volumes are added without updating AWS Backup plans.
- **Fields**: `fileSystemId`, `automaticBackupRetentionDays`, `dailyAutomaticBackupStartTime`, `status`, `severity`

### BKP-08 — Backup size growth trend

- **Severity**: Medium
- **API**: `backup list-recovery-points-by-resource` (read `BackupSizeInBytes` and `CreationDate` per
  recovery point)
- **Logic**: For each recovery point compute `ageDays = now − CreationDate`; consider only points with
  `ageDays ≤ 30`, then compute the percentage growth of `BackupSizeInBytes` from the oldest to the
  newest point in that set. Derive each point's age from its own `CreationDate` — do not synthesize a
  30-days-ago cutoff timestamp.
- **Status**: Pass — growth < 10%. Warning — 10–25%. Fail — > 25%.
- **Recommendation (Fail/Warning)**: Review data-growth drivers; verify storage efficiency is enabled;
  confirm snapshot retention is not inflating backup size; plan SSD capacity increases before reaching
  80% utilization.
- **Fields**: `resourceArn`, `growthPct30d`, `status`, `severity`

### BKP-09 — Backup staleness detection

- **Severity**: Medium
- **API**: `fsx describe-backups` (filter `Type = USER_INITIATED`, read `CreationTime`)
- **Logic**: For the most recent user-initiated backup compute `ageDays = now − CreationTime`; flag
  if `ageDays > 90` (no recent restore point outside the automatic-backup retention window). Derive the
  age from the backup's own `CreationTime` — do not synthesize a 90-days-ago cutoff timestamp.
- **Status**: Pass — a user backup exists within the last 90 days (or automatic backups cover the need).
  Warning — most recent user backup is 90+ days old. Fail — only stale user backups exist.
- **Recommendation (Fail/Warning)**: Review and replace stale backups; confirm the current backup
  strategy still meets the recovery-point objective.
- **Fields**: `fileSystemId`, `latestUserBackupAgeDays`, `status`, `severity`

### BKP-10 — Automatic backup daily cadence

- **Severity**: Medium
- **API**: `fsx describe-backups` (filter `Type = AUTOMATIC`, sort `CreationTime`)
- **Logic**: Sort automatic backups by `CreationTime` and compute the **delta between each adjacent
  pair**; verify a consistent daily cadence (deltas roughly 86,400 s) with no multi-day gaps. Work from
  deltas between existing timestamps — do not synthesize a past cutoff timestamp.
- **Status**: Pass — consecutive daily backups with no gap. Warning — occasional gap. Fail — large or
  repeated gaps, or no automatic backups despite retention being set.
- **Recommendation (Fail/Warning)**: Fix the backup schedule to maintain a daily cadence;
  cross-check `AutomaticBackupRetentionDays` and `DailyAutomaticBackupStartTime` (see BKP-07).
- **Fields**: `fileSystemId`, `maxGapHours`, `backupCount`, `status`, `severity`

---
