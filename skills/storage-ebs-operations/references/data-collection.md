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
| AWS/EBS | `VolumeAvgIOPS` (Ops/s), `VolumeAvgThroughput` (KiB/s), `VolumeAvgReadLatency` (milliseconds), `VolumeAvgWriteLatency` (milliseconds), `VolumeStalledIOCheck` (0 passed, 1 failed), `VolumeIOPSExceededCheck` and `VolumeThroughputExceededCheck` (0 not exceeded, 1 the application tried to drive more than the volume's provisioned IOPS or throughput in that minute; not for Multi-Attach volumes) | `VolumeId` AND `InstanceId`. Nitro instances only. A query with `VolumeId` alone returns no datapoints |
| AWS/EBS | `VolumeReadOps`, `VolumeWriteOps`, `VolumeReadBytes`, `VolumeWriteBytes`, `VolumeTotalReadTime` (seconds), `VolumeTotalWriteTime` (seconds), `VolumeQueueLength`, `VolumeIdleTime` (seconds), `BurstBalance`, `VolumeThroughputPercentage` (Provisioned IOPS SSD only) | `VolumeId` |
| AWS/EC2 | `EBSIOBalance%`, `EBSByteBalance%`, `EBSReadOps`, `EBSWriteOps`, `EBSReadBytes`, `EBSWriteBytes`, `InstanceEBSIOPSExceededCheck`, `InstanceEBSThroughputExceededCheck` (0 not exceeded, 1 the application tried to drive more than the instance's maximum EBS IOPS or throughput in that minute; Nitro instances that are not bare metal) | `InstanceId` |

The four exceeded checks and `VolumeStalledIOCheck` are not available in AWS Outposts, Local Zones or Wavelength Zones. They are ordinary CloudWatch metrics read with `GetMetricData`, so they need no extra permission. For the exceeded and stalled checks, report the `Maximum` per minute, the number of minutes at 1 and the time window. "No datapoints" is not the same as 0: say which one you got, and list "no datapoints" under Gaps.

Metric math from the Amazon CloudWatch metrics page for Amazon EBS. Use `Sum` statistics for ops, bytes and time.

- IOPS = Sum(`VolumeReadOps` + `VolumeWriteOps`) / period in seconds
- MiB/s = Sum(`VolumeReadBytes` + `VolumeWriteBytes`) / period in seconds / 1,048,576
- Average read latency in milliseconds per operation = Sum(`VolumeTotalReadTime`, in seconds) / Sum(`VolumeReadOps`) x 1,000 (and the write equivalent with `VolumeTotalWriteTime` and `VolumeWriteOps`). Without the x 1,000 the result is in seconds. Always state latency in milliseconds
- Idle percentage = Sum(`VolumeIdleTime`) / period in seconds x 100
- MiB/s from `VolumeAvgThroughput` = value in KiB/s / 1,024

What a 1-minute average hides: sub-minute peaks can reach a limit while the minute average looks below it (micro-bursting). When latency or queue length rises while the average sits below the limit, say that headroom is not proven instead of claiming it.

`EBSIOBalance%` and `EBSByteBalance%` are published only for some instance sizes (generally 4xlarge and smaller) that can burst. If they are absent, the instance does not publish them. That is not a fault.

## Errors and fallbacks

| What happens | What it means | What to do |
|---|---|---|
| `AccessDenied` on any call | The role cannot read that data | Name the exact API in Gaps. Continue with the rest |
| A read call is held behind an operator-approval gate (for example `dlm:GetLifecyclePolicies` or `rbin:ListRules`) | The Agent Space treats it as an action | Report it as a Gap and say which conclusion stays unconfirmed. Never ask the operator to bypass the gate |
| No datapoints for `VolumeIOPSExceededCheck`, `VolumeThroughputExceededCheck` or `VolumeStalledIOCheck` | The `InstanceId` dimension is missing, the instance is not Nitro, or the volume is Multi-Attach (exceeded checks only) | Query again with `VolumeId` and `InstanceId`. If still empty, report "no datapoints" under Gaps, not 0, and judge the limit from the measured IOPS and MiB/s |
| No `VolumeAvg*` data | The instance is not Nitro, or the `InstanceId` dimension is missing | Add `InstanceId`. If still empty, use the Sum-based math above |
| `EBSIOBalance%` absent | The instance size does not publish it | Compare the summed IOPS and MiB/s of all attached volumes to the `DescribeInstanceTypes` baseline |
| `DescribeInstanceTypes` values in MB/s | The API reports instance throughput in MB/s (bandwidth in Mbps) | Convert to MiB/s before comparing (1 MB/s = 1,000,000 bytes/s; 1 MiB/s = 1,048,576 bytes/s) |
| AWS CloudTrail optional lookup denied or empty | No access, or the event is older than the 90 days that `LookupEvents` covers | Use `DescribeVolumesModifications` for the current or latest modification only; it returns only the most recent modification per volume. Record a Gap for the modification history and for the 24-hour modification count |
| No metric data for a volume | The volume is new, detached, or the window is wrong | Check `DescribeVolumes` state and attachment times, widen the window, report the Gap |

## Sources

- Amazon CloudWatch metrics for Amazon EBS (units, dimensions, `VolumeStalledIOCheck` with `VolumeId` and `InstanceId`, and the latency formula Sum(`VolumeTotalReadTime`) / Sum(`VolumeReadOps`) x 1000 in ms/op): https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Volume exceeded checks (`VolumeIOPSExceededCheck`, `VolumeThroughputExceededCheck`): https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html
- Instance metrics, including `EBSIOBalance%`, `EBSByteBalance%`, `InstanceEBSIOPSExceededCheck` and `InstanceEBSThroughputExceededCheck`: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html
- Status check metrics, including `VolumeStalledIOCheck`: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html#status-check-metrics
- Amazon EBS-optimized instances (baseline and maximum, MB/s): https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- DescribeVolumesModifications (most recent modification request only): https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumesModifications.html
- AWS CloudTrail LookupEvents (last 90 days): https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html
- AWS FIS actions: https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html
