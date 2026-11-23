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
   - `DescribeVolumesModifications` for every volume: original and target size, type, IOPS and throughput, with start time. It returns only the most recent modification of each volume, so it can explain a cost change only when that latest modification falls in the period.
   - For earlier modifications, use AWS CloudTrail `LookupEvents` for `ModifyVolume` events (optional; it covers the last 90 days). If it is denied, empty, or the change is older than 90 days, write a Gap that says the change could not be traced and continue.
   - `DescribeVolumes` `CreateTime` for new volumes, and `status=available` for unattached volumes.
   - Volume type changes (for example gp2 to gp3, or gp3 to io2) from the latest modification record or the AWS CloudTrail `ModifyVolume` events.
   - Amazon Data Lifecycle Manager `GetLifecyclePolicies` and AWS Backup `ListBackupPlans` for policies that create or retain snapshots.
   - Recycle Bin `ListRules`: resources in Recycle Bin are still billed during retention.
   - The same AWS CloudTrail events show who made a change. If the lookup is denied or empty, write a Gap and continue.
6. **Right-sizing check** for volumes with provisioned performance.
   - Measured IOPS and MiB/s over a representative window (`VolumeAvgIOPS` / `VolumeAvgThroughput` with `VolumeId` and `InstanceId`, or the Sum-based math in [data-collection.md](data-collection.md)) against provisioned values.
   - Provisioned performance above what the attached instance's EBS baseline can deliver.
   - AWS Compute Optimizer `GetEBSVolumeRecommendations` if enabled (optional).
7. **Separate findings.** Posture issues seen during the check (unencrypted volumes, untagged volumes, no backup coverage, no alarms) go under Separate findings with a suggestion to run Review mode ([review-operational.md](review-operational.md)).

## Decision rules

- The Answer names the component and the resource that drove the change, with the date from the modification record, the AWS CloudTrail `ModifyVolume` event, or `CreateTime`.
- Snapshot savings are an upper bound because snapshots are incremental.
- A volume with provisioned performance far above measured demand or above the instance baseline is a right-sizing candidate. Do not apply a fixed percentage rule; show the measured and provisioned values and let the operator decide.

## What to report

The verdict template in [finding-logic.md](finding-logic.md). Evidence is a table of components (storage, IOPS, throughput, snapshots) with the account's own amounts for the two periods compared, and the change records that explain each. Binding layer is "Not applicable". Recommendation lists right-sizing or type-change proposals with exact parameters and cost direction, and lists unneeded volumes or snapshots for owner review (deletion is a manual customer step, see Safety rules).

## Safety rules

- This path is read-only.
- Changing volume types and lowering IOPS or throughput are proposals for a directed action approved on the approval card. Each proposal names the volume, the exact parameters, the cost direction and the rollback.
- Deleting volumes or snapshots is never a directed action, because AWS DevOps Agent refuses delete-class operations. List the resource for owner review. After the owner confirms they no longer need it, give the manual steps for the customer to run with their own credentials. For a volume, recommend a snapshot first. Say whether a Recycle Bin rule will catch the deletion. For snapshots, use the tiers in [troubleshoot-snapshots.md](troubleshoot-snapshots.md).
- Never type a price. Use the account's Cost Explorer amounts and link the pricing page.

## Sources

- Amazon EBS pricing: https://aws.amazon.com/ebs/pricing/
- gp3 included performance: https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html
- Monitoring volume modifications: https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- DescribeVolumesModifications (most recent modification only): https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumesModifications.html
- AWS CloudTrail LookupEvents (last 90 days): https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html
- AWS DevOps Agent directed actions (Operations the agent will not perform): https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-working-with-directed-actions.html
- Snapshots (incremental): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html
- Recycle Bin: https://docs.aws.amazon.com/ebs/latest/userguide/recycle-bin.html
- Amazon Data Lifecycle Manager: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html
- AWS Backup resource assignment: https://docs.aws.amazon.com/aws-backup/latest/devguide/assigning-resources.html
