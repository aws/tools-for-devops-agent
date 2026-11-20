# Troubleshoot: Amazon EBS cost and billing

## When this path applies

- "Why did my EBS bill go up?", unexplained Amazon EBS charges, a cost forecast
- Idle, unattached or over-provisioned volumes
- Snapshot cost growth, Recycle Bin retention cost
- Questions about the Amazon EBS pricing model

## Procedure

1. **Get the cost trend.** AWS Cost Explorer `GetCostAndUsage`, monthly for the last several months and daily for the month that changed, grouped by `USAGE_TYPE`. Amazon EBS charges appear under the "EC2 - Other" service in Cost Explorer; confirm this with `GetDimensionValues` for `SERVICE` in the account.
2. **List the account's usage types.** `GetDimensionValues` for `USAGE_TYPE` in the period. Do not trust a hardcoded list. Classify each Amazon EBS usage type by its name:
   - volume storage (names containing `VolumeUsage`)
   - provisioned IOPS (names containing `IOPS`)
   - provisioned throughput (names containing `Throughput`)
   - snapshots (names containing `Snapshot`)
3. **Break the change into components.** Report the change in storage, provisioned IOPS above the included baseline, provisioned throughput above the included baseline, and snapshots, using the account's own Cost Explorer amounts. These include the account's discounts and pricing agreements, so never replace them with list prices.
4. **Explain the gp3 model when gp3 is involved.** gp3 includes 3,000 IOPS and 125 MiB/s at any size. Only IOPS above 3,000 and throughput above 125 MiB/s are billed as provisioned performance. Link the pricing page; do not type a price.
5. **Find what changed.**
   - `DescribeVolumesModifications` for every volume: original and target size, type, IOPS and throughput, with start time. This record is not bound by AWS CloudTrail retention.
   - `DescribeVolumes` `CreateTime` for new volumes, and `status=available` for unattached volumes.
   - Volume type changes (for example gp2 to gp3, or gp3 to io2) from the modification record.
   - Amazon Data Lifecycle Manager `GetLifecyclePolicies` and AWS Backup `ListBackupPlans` for policies that create or retain snapshots.
   - Recycle Bin `ListRules`: resources in Recycle Bin are still billed during retention.
   - AWS CloudTrail `LookupEvents` is optional, only if available, to find who made a change. If it is denied or empty, write a Gap and continue.
6. **Right-sizing check** for volumes with provisioned performance.
   - Measured IOPS and MiB/s over a representative window (`VolumeAvgIOPS` / `VolumeAvgThroughput` with `VolumeId` and `InstanceId`, or the Sum-based math in [data-collection.md](data-collection.md)) against provisioned values.
   - Provisioned performance above what the attached instance's EBS baseline can deliver.
   - AWS Compute Optimizer `GetEBSVolumeRecommendations` if enabled (optional).
7. **Separate findings.** Posture issues seen during the check (unencrypted volumes, untagged volumes, no backup coverage, no alarms) go under Separate findings with a suggestion to run Review mode ([review-operational.md](review-operational.md)).

## Decision rules

- The Answer names the component and the resource that drove the change, with the date from the modification record or `CreateTime`.
- Snapshot savings are an upper bound because snapshots are incremental.
- A volume with provisioned performance far above measured demand or above the instance baseline is a right-sizing candidate. Do not apply a fixed percentage rule; show the measured and provisioned values and let the operator decide.

## What to report

The verdict template in [finding-logic.md](finding-logic.md). Evidence is a table of components (storage, IOPS, throughput, snapshots) with the account's own amounts for the two periods compared, and the change records that explain each. Binding layer is "Not applicable". Recommendation lists right-sizing, deletion or type-change proposals with exact parameters and cost direction.

## Safety rules

- This path is read-only.
- Deleting volumes or snapshots, changing volume types and lowering IOPS or throughput are proposals for a directed action approved on the approval card. Each proposal names the volume, the exact parameters, the cost direction and the rollback. For deletions, recommend a snapshot first and say whether a Recycle Bin rule will catch it.
- Never type a price. Use the account's Cost Explorer amounts and link the pricing page.

## Sources

- Amazon EBS pricing: https://aws.amazon.com/ebs/pricing/
- gp3 included performance: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Snapshots (incremental): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html
- Recycle Bin: https://docs.aws.amazon.com/ebs/latest/userguide/recycle-bin.html
- Amazon Data Lifecycle Manager: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html
- AWS Backup resource assignment: https://docs.aws.amazon.com/aws-backup/latest/devguide/assigning-resources.html
