# Review mode: Amazon EBS operational review

Review mode answers "is my EBS setup healthy before something goes wrong?". It is entirely read-only. Run each area per Region, rate each finding with the scale in [finding-logic.md](finding-logic.md), and write the report with [review-report-format.md](review-report-format.md).

The Capacity and quota headroom section is also a shared capability. Troubleshoot paths use it when an operation failed on a limit.

## Capacity and quota headroom

**Checks**

Run every check below even when the error looks simple. A user who reports a quota error has already failed to fix it alone, so give documented findings in the verdict format, not a short chat reply. Whether the run is a chat or a formal investigation is decided by how the user starts it, not by this skill.

1. If an operation failed, quote the error and name the quota it refers to. For example "You have exceeded your maximum io2 IOPS limit of 100000 IOPS in this region" refers to the regional io2 IOPS quota, which is separate from the per-volume maximum.
2. `ListServiceQuotas --service-code ebs`: quota name, code, applied `Value`, `Adjustable`. Find quotas by name; never hardcode codes. `GetAWSDefaultServiceQuota` shows the default.
3. Compute usage from the inventory:
   - Provisioned IOPS: sum of `Iops` for io1 volumes and for io2 volumes, separately.
   - Storage per type: sum of `Size` per volume type, converted from GiB to TiB.
   - Snapshots per Region: count of `DescribeSnapshots --owner-ids self`.
   - Fast snapshot restore: `DescribeFastSnapshotRestores` count of enabled entries.
4. `ListRequestedServiceQuotaChangeHistoryByQuota` for pending requests. Never propose a duplicate.

**Rating rule**

- Usage at or above 80% of the applied quota is flagged. The 80% value is configurable; ask the operator if they use a different one.
- A quota that blocked an operation is `High`.
- A quota flagged at or above the threshold is `Medium`, or `High` if the user states a planned increase that would exceed it.
- Unreadable quota or usage is `Indeterminate`.

**Fix**

- Adjustable: a pre-filled Service Quotas request (service code `ebs`, quota code as read, desired value) proposed as a directed action. The desired value is the user's stated need, or current usage plus the request that failed. No fixed multipliers. Include the intake questions for the matching quota below, and show the adjustable-path approval caution.
- Not adjustable: draft the AWS Support case text (service, quota name, Region, desired value, business justification). Include the intake questions for the matching quota below, and show the case-path approval caution.
- Name the quotas that commonly cause problems: per-Region IOPS for io1 and io2, per-Region storage per volume type, snapshots per Region, and fast snapshot restore.

**Intake questions to include with the request or case**

Add the questions for the quota being proposed. These are for the agent to ask the customer in plain, customer-facing wording. Answering these in the request gives the AWS team the detail they need to review it, which helps them action it faster. Do not promise approval or a timeframe.

The archiving best practices are at https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/archiving-guidelines.html.

- IOPS or storage:
  - What workload is driving the need for more storage or IOPS? Is there a planned launch or event, or is this organic growth you want to secure capacity for?
  - How will the workload be spread across Availability Zones? If it is not spread evenly, which zone will carry most of the usage?
  - By what date do you need the extra capacity, and what is the ramp-up timeline?
  - What is the minimum amount you need?
- Fast Snapshot Restore (FSR):
  - What is your use case for a higher FSR limit?
  - How is this split across Availability Zones?
  - Will you enable FSR gradually in batches or all at once, and for how many snapshots?
  - What is the size of the snapshots you are enabling FSR on?
  - For how long will FSR stay enabled?
- Maximum number of archived snapshots per volume (include these only when the requested value is more than 25):
  - Is this for daily or weekly snapshots? Archiving daily or weekly snapshots is usually only worthwhile when their change rate is above 25 percent.
  - Is this for monthly, quarterly, or yearly snapshots? If so, why do you need more than 25 archived snapshots per volume?
  - Is this for new or existing snapshots? EBS Snapshots Archive stores full versions of snapshots. Have you reviewed the archiving best practices linked above?
- Maximum number of in-progress snapshot archives (include these only when the requested value is more than 25):
  - Is this for daily or weekly snapshots? Archiving daily or weekly snapshots is usually only worthwhile when their change rate is above 25 percent.
  - Is this for monthly, quarterly, or yearly snapshots?
  - Is this for new or existing snapshots? EBS Snapshots Archive stores full versions of snapshots. Have you reviewed the archiving best practices linked above?
  - Is this a one-time archival? Can you archive in batches of 25?
- Max concurrent copy-volume operations (volume clone):
  - What is the use case?
  - Which Availability Zones will you use in the Region?
  - What are the source and target volume types?
  - What is the estimated size of data on these volumes?
  - How often will you clone a volume (daily, weekly, or monthly)?
- Amazon EBS Provisioned Rate for Volume Initialization:
  - Which Availability Zones will you use with this feature?
  - What snapshot sizes will you use?
  - Which volume types will you use?
  - How many volumes will you create at the same time with this feature?
  - How often will you create volumes with this feature (hourly, daily, or weekly)?

**Approval caution (always show with the request or case)**

- Adjustable path (show with the pre-filled Service Quotas request): A request through Service Quotas is not guaranteed. AWS reviews each one and may approve a lower value than you asked for or ask for more detail, and a very large increase may be routed to AWS Support before it is granted.
- Case path (show with the AWS Support case text): Approval and the exact amount are decided by AWS.

## Observability

**Checks**

1. `DescribeAlarms` for the AWS/EBS namespace: alarms on `VolumeQueueLength`, latency (`VolumeAvgReadLatency`, `VolumeAvgWriteLatency`, or `VolumeTotalReadTime` / `VolumeTotalWriteTime` math), throughput, and `BurstBalance` for gp2, st1 and sc1.
2. `DescribeAlarms` for the AWS/EC2 namespace: `EBSIOBalance%` and `EBSByteBalance%` on instances that publish them.
3. Which volumes are critical: ask the operator, or use tags they name. Do not infer criticality from tag values by yourself.

**Rating rule**: a critical volume with no Amazon EBS alarm is `Medium`. `High` if the operator says the volume backs a production database or service. An alarm in `INSUFFICIENT_DATA` for a long time is `Low` (it may be on a deleted volume).

**Fix**: propose alarms with metric, dimensions (`VolumeAvg*` need `VolumeId` and `InstanceId`) and the threshold the operator chooses.

## Cost hygiene

**Checks**

1. gp2 volumes: gp3 candidates. gp3 has 20% lower price per GiB than gp2 and includes 3,000 IOPS and 125 MiB/s.
2. Unattached volumes: `DescribeVolumes` with `status=available`.
3. Over-provisioned IOPS or throughput: measured vs provisioned, and provisioned above the instance EBS baseline (see [troubleshoot-billing.md](troubleshoot-billing.md) step 6).
4. AWS Compute Optimizer `GetEBSVolumeRecommendations` if enabled (optional).

**Rating rule**: `Low` by default. `Medium` when the operator names cost as a goal or the resource is large relative to the account's Amazon EBS spend as shown in Cost Explorer.

**Fix**: `ModifyVolume` to gp3 with IOPS and throughput sized as in [troubleshoot-volume-modification.md](troubleshoot-volume-modification.md) step 6; snapshot then delete for unattached volumes. All as directed-action proposals.

## Resilience

**Checks**

1. Inventory volumes (`DescribeVolumes`), including root volumes.
2. Amazon Data Lifecycle Manager: `GetLifecyclePolicies` (state `ENABLED`) and `GetLifecyclePolicy` for target tags and resource type. Target tags are case sensitive. Note default policies, which target the Region's volumes or instances without recent backups.
3. AWS Backup: `ListBackupPlans`, `ListBackupSelections`, `GetBackupSelection` (selection by resource ARN, by tag condition, or all resources of a type), and `ListProtectedResources`.
4. Match each volume to a policy or a selection. A volume that matches none is unprotected.
5. For protected volumes, `ListRecoveryPointsByResource` with `ManagedByAWSBackupOnly` set to true for the latest recovery point, and the latest `aws:dlm:*` tagged snapshot of the volume. Compare its age with the policy schedule. Without that parameter, the call also returns manual snapshots, which are not backups from the plan.
6. Cross-Region copy for disaster recovery: copy actions in DLM policies or AWS Backup copy rules.
7. Ask the operator for their recovery point objective. Do not assume one.

**Rating rule**: an unprotected volume the operator calls critical is `High`. A protected volume whose latest recovery point is older than its own schedule is `High` (the backup may be failing). No cross-Region copy where the operator needs Regional disaster recovery is `Medium`. Unprotected non-critical volumes are `Low`.

**Fix**: tag the volume to match an existing policy, add it to a backup selection, or create a policy. All as directed-action proposals.

## Encryption posture

**Checks**

1. `GetEbsEncryptionByDefault` and `GetEbsDefaultKmsKeyId` per Region.
2. Unencrypted volumes and snapshots (`Encrypted` is false).
3. For keys in use, AWS KMS `DescribeKey` state. A disabled or pending-deletion key in use is a risk.
4. Snapshot exposure: `GetSnapshotBlockPublicAccessState` per Region, and `DescribeSnapshots --owner-ids self --restorable-by-user-ids all` for snapshots that are public now.

**Rating rule**: a key in use that is disabled or pending deletion is `High`. A public snapshot is `High`. Encryption by default off is `Medium`. Unencrypted volumes are `Medium`, or `High` if the operator says the data is regulated. Snapshot block public access in the `unblocked` state is `Medium`.

**Fix**: turn on encryption by default; re-encrypt with the steps in [troubleshoot-encryption.md](troubleshoot-encryption.md); turn on snapshot block public access (`block-all-sharing`, or `block-new-sharing` while existing public shares are reviewed). All as directed-action proposals.

## Deletion protection

**Checks**

1. `DescribeInstanceAttribute --attribute blockDeviceMapping` for `DeleteOnTermination` on each attached volume. A data volume with `DeleteOnTermination` true is deleted when the instance terminates.
2. Recycle Bin `ListRules` for `EBS_SNAPSHOT` (and for AMIs if the account uses them).
3. Snapshot lock: `DescribeLockedSnapshots` for snapshots the operator must keep.

**Rating rule**: a critical data volume with `DeleteOnTermination` true is `High`. No Recycle Bin rule for snapshots is `Medium`. No lock on snapshots the operator says are compliance records is `Medium`.

**Fix**: `ModifyInstanceAttribute` to set `DeleteOnTermination` false on the data volume, a Recycle Bin retention rule, or a snapshot lock. All as directed-action proposals.

## Safety rules

- Review mode is entirely read-only. It never runs a mutating call.
- Every fix is listed under "Proposed actions" in the report with exact parameters, expected effect, cost direction and rollback. Each one needs a directed action approved on the approval card.

## Sources

- Amazon EBS quotas: https://docs.aws.amazon.com/general/latest/gr/ebs-service.html and https://docs.aws.amazon.com/ebs/latest/userguide/ebs-resource-quotas.html
- Requesting a quota increase: https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html
- Amazon CloudWatch metrics for Amazon EBS: https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- gp3 and gp2: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- Amazon Data Lifecycle Manager: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html and https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-ami-policy.html
- AWS Backup resource assignment: https://docs.aws.amazon.com/aws-backup/latest/devguide/assigning-resources.html
- Encryption by default: https://docs.aws.amazon.com/ebs/latest/userguide/encryption-by-default.html
- Block public access for snapshots: https://docs.aws.amazon.com/ebs/latest/userguide/block-public-access-snapshots.html
- AWS Backup ListRecoveryPointsByResource: https://docs.aws.amazon.com/aws-backup/latest/APIReference/API_ListRecoveryPointsByResource.html
- DeleteOnTermination: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/terminating-instances.html
- Recycle Bin: https://docs.aws.amazon.com/ebs/latest/userguide/recycle-bin.html
- Snapshot lock: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshot-lock.html
- Fast snapshot restore: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-fast-snapshot-restore.html
