# Operations — Check Definitions

> **Read `overview.md` first.** It holds the Severity Model, Status Values, the Evidence
> Guardrails (observed-data-only), and the public AWS API / `AWS/FSx` metric reference that
> govern every check below. Load this pillar file when you run this pillar's checks.

## Operations (11 checks)

### OPS-01 — Cost-allocation tags

- **Severity**: Medium
- **API**: `fsx describe-file-systems` (`Tags`) or `fsx list-tags-for-resource`
- **Logic**: Confirm tags include `Project`, `Owner`, and `CostCenter` at minimum.
- **Status**: Pass — all three present. Warning — some present. Fail — none present.
- **Recommendation (Fail/Warning)**: Tag file systems with `Project`, `Owner`, and `CostCenter` at a
  minimum for cost attribution and ownership.
- **Fields**: `fileSystemId`, `tagsPresent`, `tagsMissing`, `status`, `severity`

### OPS-02 — Unused volumes identified

- **Severity**: Medium
- **API**: `fsx describe-volumes` + `cloudwatch get-metric-data` (`DataReadOperations`,
  `DataWriteOperations` per `VolumeId` over a trailing window)
- **Logic**: Flag volumes with no (or negligible) read/write operations over the window. Evaluate every
  volume including the SVM root; **tag** the root-volume row `SVM root (JunctionPath=/)`.
- **Status**: Pass — volume shows recent I/O. Warning — negligible I/O. Fail — no I/O over the window.
  No datapoints returned ⇒ **Not evaluated — no datapoints** (do not treat absence of the metric as "no
  I/O").
- **Recommendation (Fail/Warning)**: Audit and remove unused data volumes to reduce cost and sprawl.
  **Never recommend removing the SVM root volume** (`JunctionPath=/`) — it cannot be deleted; for it,
  report the observed I/O without a removal recommendation.
- **Fields**: `volumeId`, `isSvmRoot`, `readOps`, `writeOps`, `status`, `severity`

### OPS-03 — Maintenance window aligned

- **Severity**: Low
- **API**: `fsx describe-file-systems` (`WeeklyMaintenanceStartTime`)
- **Logic**: Report the configured maintenance window for customer review (Informational).
- **Status**: Info — report value.
- **Recommendation**: Confirm the maintenance window aligns with the customer's change-management policy.
- **Fields**: `fileSystemId`, `weeklyMaintenanceStartTime`, `status`

### OPS-04 — Consistent maintenance windows

- **Severity**: Low
- **API**: `fsx describe-file-systems`
- **Logic**: Compare `WeeklyMaintenanceStartTime` across all in-scope file systems.
- **Status**: Pass — same window across all file systems. Warning — windows differ.
- **Recommendation (Warning)**: Align maintenance windows across file systems for coordinated change
  management.
- **Fields**: `fileSystemId`, `weeklyMaintenanceStartTime`, `status`, `severity`

### OPS-05 — Storage efficiency enabled

- **Severity**: Medium
- **API**: `fsx describe-volumes` (`OntapConfiguration.StorageEfficiencyEnabled`)
- **Logic**: Confirm storage efficiency is enabled on volumes.
- **Status**: Pass — enabled. Fail — disabled.
- **Recommendation (Fail)**: Enable storage efficiency (compression, deduplication, compaction) —
  typically ~65% savings for general-purpose workloads.
- **Fields**: `volumeId`, `storageEfficiencyEnabled`, `status`, `severity`

### OPS-06 — Snapshot policies on production volumes

- **Severity**: High
- **API**: `fsx describe-volumes` (`OntapConfiguration.SnapshotPolicy`)
- **Logic**: Confirm `SnapshotPolicy != none` on RW volumes.
- **Status**: Pass — a snapshot policy is set. Fail — policy is `none` on an RW volume.
- **Recommendation (Fail)**: Attach a snapshot policy to production data volumes for point-in-time
  recovery.
- **Fields**: `volumeId`, `ontapVolumeType`, `snapshotPolicy`, `status`, `severity`

### OPS-07 — Deployment type matches HA requirements

- **Severity**: High
- **API**: `fsx describe-file-systems` (`OntapConfiguration.DeploymentType`)
- **Logic**: Report deployment type (`SINGLE_AZ_1/2`, `MULTI_AZ_1/2`) for review against the workload's
  availability requirement.
- **Status**: Info — report value; flag for review when a persistent-production file system is Single-AZ.
- **Recommendation**: Use Multi-AZ for production persistent data requiring the highest availability;
  Single-AZ is acceptable for non-critical or reproducible data.
- **Fields**: `fileSystemId`, `deploymentType`, `status`, `severity`

### OPS-08 — Active Directory configured on SVM

- **Severity**: Medium
- **API**: `fsx describe-storage-virtual-machines` (`ActiveDirectoryConfiguration`)
- **Logic**: Report AD configuration on each SVM.
- **Status**: Pass — AD configured where SMB access is required. Info — report config.
- **Recommendation**: Verify AD integration is configured on SVMs serving SMB clients.
- **Fields**: `svmId`, `netBiosName`, `activeDirectoryConfigured`, `status`, `severity`

### OPS-09 — Volume and SVM tag audit

- **Severity**: Medium
- **API**: `fsx describe-volumes` and `fsx describe-storage-virtual-machines` (`Tags`), or
  `fsx list-tags-for-resource`
- **Logic**: Confirm every volume and SVM carries tags (not an empty tag set). OPS-01 covers
  file-system-level cost-allocation tags; this check extends tag coverage to volumes and SVMs.
- **Status**: Pass — every volume and SVM has tags. Warning — some are untagged. Fail — volumes/SVMs
  have no tags at all.
- **Recommendation (Fail/Warning)**: Tag every volume and SVM for ownership and cost attribution; flag
  any with an empty tag set.
- **Fields**: `resourceId`, `resourceType`, `tagCount`, `status`, `severity`

### OPS-10 — Per-volume storage capacity utilization

- **Severity**: High
- **API**: `cloudwatch get-metric-data` — `StorageUsed` (detailed, dims `FileSystemId`, `VolumeId`,
  summed across `StorageTier`) ÷ volume size from `fsx describe-volumes`
  (`OntapConfiguration.SizeInMegabytes`)
- **Scope**: **Data volumes only.** This is the one check that **excludes** the **SVM root volume**
  (`JunctionPath = /`, `Name = <svm-name>_root`), because `usedPct` is mathematically invalid for a
  namespace root. Render the root as an explicit `Excluded — SVM root (JunctionPath=/)` row — never
  drop it silently. DP/LS volumes are likewise out of scope here.
- **Logic**: For each in-scope data volume compute `usedPct = StorageUsed ÷ (SizeInMegabytes × 1024 ×
  1024)`. Volumes are thin-provisioned, so "capacity" is the configured volume size, not the
  file-system SSD tier (distinct from PERF-05). No `StorageUsed` datapoint for a volume ⇒
  **Not evaluated — no datapoints**, not a guessed 0%.
- **Status**: Pass — below 80% used. Warning — 80–90%. Fail — above 90%. If `usedPct` computes above
  100% on an in-scope volume, do **not** flag it as a capacity breach — report it **Informational** as a
  metric/size artifact to verify, since a true data volume cannot exceed its own configured size.
- **Recommendation (Fail/Warning)**: Expand the volume or clean up data on volumes over 80% used; a
  volume that fills can take writes offline for its clients.
- **Fields**: `volumeId`, `usedPct`, `sizeMB`, `status`, `severity`

### OPS-11 — Aged snapshots

- **Severity**: Low
- **API**: `fsx describe-snapshots` (read `CreationTime`)
- **Logic**: For each snapshot compute `ageDays = now − CreationTime`; flag if `ageDays > 90`
  (candidate cleanup to reclaim space and reduce sprawl). Derive age from each snapshot's own
  `CreationTime` — do not synthesize a 90-days-ago cutoff timestamp.
- **Status**: Pass — no snapshots older than 90 days. Warning — aged snapshots present.
- **Recommendation (Warning)**: Review and delete aged snapshots that are no longer needed; confirm
  retention policy aligns with the recovery requirement.
- **Fields**: `volumeId`, `snapshotId`, `ageDays`, `status`, `severity`

---
