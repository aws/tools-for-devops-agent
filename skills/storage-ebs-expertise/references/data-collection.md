# Data collection: read-only APIs, metric math, errors and fallbacks

Load this file on every request. Every value in a verdict or a review comes from one of these calls. Tags are used for naming only, never as the source of a configuration value.

## Read-only API allowlist

| Service | APIs |
|---|---|
| Amazon EC2 | `DescribeVolumes`, `DescribeVolumeStatus`, `DescribeVolumesModifications`, `DescribeVolumeAttribute`, `DescribeInstances`, `DescribeInstanceTypes`, `DescribeInstanceAttribute`, `DescribeSnapshots`, `DescribeSnapshotAttribute`, `DescribeImages`, `DescribeFastSnapshotRestores`, `GetEbsEncryptionByDefault`, `GetEbsDefaultKmsKeyId`, `GetSnapshotBlockPublicAccessState`, `DescribeLockedSnapshots` |
| Amazon CloudWatch | `DescribeAlarms`, `DescribeAlarmHistory`, `GetMetricData`, `ListMetrics` |
| Service Quotas | `ListServiceQuotas`, `GetServiceQuota`, `GetAWSDefaultServiceQuota`, `ListRequestedServiceQuotaChangeHistoryByQuota` |
| Amazon Data Lifecycle Manager | `GetLifecyclePolicies`, `GetLifecyclePolicy` |
| Recycle Bin | `ListRules`, `GetRule` |
| AWS Backup | `ListBackupPlans`, `ListBackupSelections`, `GetBackupSelection`, `ListRecoveryPointsByResource` (always with `ManagedByAWSBackupOnly` set to true; without it the call also returns snapshots AWS Backup did not create), `ListProtectedResources` |
| AWS KMS | `DescribeKey`, `GetKeyPolicy`, `ListGrants` |
| AWS Cost Explorer | `GetCostAndUsage`, `GetDimensionValues` |
| AWS FIS | `ListExperiments`, `GetExperiment` |
| AWS Health | `DescribeEvents` |
| AWS Compute Optimizer (optional) | `GetEBSVolumeRecommendations` |
| AWS CloudTrail (optional) | `LookupEvents`. This call is optional. If it is denied or returns nothing, record a Gap and continue. Never make it a required step |

Nothing outside this list is called by the skill on its own. Mutating calls are proposals (see SKILL.md Critical rules).

## Metric rules

AWS/EBS publishes 1-minute data.

| Namespace | Metrics | Dimensions |
|---|---|---|
| AWS/EBS | `VolumeAvgIOPS` (Ops/s), `VolumeAvgThroughput` (KiB/s), `VolumeAvgReadLatency`, `VolumeAvgWriteLatency` | `VolumeId` AND `InstanceId`. Nitro instances only |
| AWS/EBS | `VolumeReadOps`, `VolumeWriteOps`, `VolumeReadBytes`, `VolumeWriteBytes`, `VolumeTotalReadTime`, `VolumeTotalWriteTime`, `VolumeQueueLength`, `VolumeIdleTime`, `BurstBalance`, `VolumeThroughputPercentage` (Provisioned IOPS SSD only) | `VolumeId` |
| AWS/EC2 | `EBSIOBalance%`, `EBSByteBalance%`, `EBSReadOps`, `EBSWriteOps`, `EBSReadBytes`, `EBSWriteBytes` | `InstanceId` |

Metric math from the Amazon CloudWatch metrics page for Amazon EBS. Use `Sum` statistics for ops, bytes and time.

- IOPS = Sum(`VolumeReadOps` + `VolumeWriteOps`) / period in seconds
- MiB/s = Sum(`VolumeReadBytes` + `VolumeWriteBytes`) / period in seconds / 1,048,576
- Average latency per operation = `VolumeTotalReadTime` / `VolumeReadOps` (and the write equivalent)
- Idle percentage = Sum(`VolumeIdleTime`) / period in seconds x 100
- MiB/s from `VolumeAvgThroughput` = value in KiB/s / 1,024

What a 1-minute average hides: sub-minute peaks can reach a limit while the minute average looks below it (micro-bursting). When latency or queue length rises while the average sits below the limit, say that headroom is not proven instead of claiming it.

`EBSIOBalance%` and `EBSByteBalance%` are published only for some instance sizes (generally 4xlarge and smaller) that can burst. If they are absent, the instance does not publish them. That is not a fault.

## Errors and fallbacks

| What happens | What it means | What to do |
|---|---|---|
| `AccessDenied` on any call | The role cannot read that data | Name the exact API in Gaps. Continue with the rest |
| A read call is held behind an operator-approval gate (for example `dlm:GetLifecyclePolicies` or `rbin:ListRules`) | The Agent Space treats it as an action | Report it as a Gap and say which conclusion stays unconfirmed. Never ask the operator to bypass the gate |
| No `VolumeAvg*` data | The instance is not Nitro, or the `InstanceId` dimension is missing | Add `InstanceId`. If still empty, use the Sum-based math above |
| `EBSIOBalance%` absent | The instance size does not publish it | Compare the summed IOPS and MiB/s of all attached volumes to the `DescribeInstanceTypes` baseline |
| `DescribeInstanceTypes` values in MB/s | The API reports instance throughput in MB/s (bandwidth in Mbps) | Convert to MiB/s before comparing (1 MB/s = 1,000,000 bytes/s; 1 MiB/s = 1,048,576 bytes/s) |
| AWS CloudTrail optional lookup denied or empty | No access, or the event is outside retention | Use `DescribeVolumesModifications` for the change record. It is not bound by AWS CloudTrail retention |
| No metric data for a volume | The volume is new, detached, or the window is wrong | Check `DescribeVolumes` state and attachment times, widen the window, report the Gap |

## Sources

- Amazon CloudWatch metrics for Amazon EBS: https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Instance metrics, including `EBSIOBalance%` and `EBSByteBalance%`: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
- Amazon EBS-optimized instances (baseline and maximum, MB/s): https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- AWS FIS actions: https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html
