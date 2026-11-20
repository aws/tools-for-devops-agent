# Amazon EBS service rules and quirks

Load this file for any statement about how Amazon EBS behaves. Per-type limits are in [metrics-thresholds.md](metrics-thresholds.md).

## Elastic Volumes rules

- You can make up to 4 modifications to a volume in a rolling 24-hour period. There is no fixed waiting period between modifications; the next one is allowed once the previous one completes (January 2026 change).
- Size can only increase. It cannot be reduced. To get a smaller volume, create a new volume and copy the data.
- A modification request cannot be cancelled after it is submitted.
- States are `modifying`, then `optimizing`, then `completed` (or `failed`). In `optimizing` the new configuration already applies, and performance is between the source and the target. The modification completes on its own.
- Duration is best effort. The Amazon EBS User Guide says a 1 TiB volume typically takes up to about six hours to modify, and some performance changes take more than 24 hours, for example when the volume is not fully initialized.
- After a size increase, the operating system must extend the partition and the file system. The agent gives the commands; the operator runs them.
- Read the requirements page before proposing a change on an older instance, or on a volume with an MBR partition (2 TiB limit).

## Instance EBS layer

- All volumes attached to an instance share the instance's EBS bandwidth, IOPS and throughput. Sum the measured values across all attached volumes, including the root volume.
- Size any target within the instance's EBS baseline from `DescribeInstanceTypes`, not its burst maximum.
- `DescribeInstanceTypes` reports throughput in MB/s at 128 KiB I/O and IOPS at 16 KiB I/O. Convert MB/s to MiB/s before comparing with volume throughput.
- Some smaller instance sizes burst above the baseline for a limited time and publish `EBSIOBalance%` and `EBSByteBalance%`. When those balances drain or reach 0, the instance drops to its baseline.

## Quotas

- Amazon EBS quotas are per Region. Check each Region the user works in.
- Discover quota codes by name with `ListServiceQuotas --service-code ebs`. Never hardcode quota codes.
- Read defaults from the Amazon EBS quotas page. For example, the default for snapshots per Region is 100,000 and it is adjustable.
- The io2 regional IOPS quota is separate from the per-volume maximum. A request within the per-volume maximum can still fail on the regional quota. Existing io2 volumes already consume part of that quota.
- Adjustable quotas are raised through Service Quotas. Quotas that are not adjustable need an AWS Support case.

## Snapshots

- Snapshots are incremental. Deleting a snapshot might not reduce storage cost, because later snapshots can reference its blocks. Any savings figure is an upper bound.
- You cannot delete a snapshot that is the root device snapshot of a registered AMI, even if the AMI is deprecated or disabled. Deregister the AMI first, and only if it is no longer needed.
- Snapshots created by AWS Backup are managed in AWS Backup, not with Amazon EC2 delete calls.
- Identify Amazon Data Lifecycle Manager snapshots by `aws:dlm:*` tags, never by the snapshot name or description. A snapshot can be named like a DLM snapshot and still have no `aws:dlm:*` tags.
- Target tags for Amazon Data Lifecycle Manager policies are case sensitive.
- Recycle Bin rules decide whether a deleted snapshot can be recovered. With no matching rule, deletion is permanent.

## Quirks that change answers

| Quirk | Rule |
|---|---|
| `VolumeThroughputPercentage` on io1/io2 | Reports the percentage of provisioned IOPS delivered. Not a throughput signal |
| `VolumeAvg*` metrics | Need `VolumeId` and `InstanceId`; Nitro only; `VolumeAvgThroughput` is KiB/s |
| Change history | `DescribeVolumesModifications` is the authoritative modification record. AWS CloudTrail is optional and may be blocked or outside retention |
| Units | Throughput in MiB/s every time. Instance limits arrive in MB/s; convert |
| Approval | A typed "approve" in chat is not approval. Only the approval card of a directed action approves a mutating action |

## Sources

- Modify a volume (4 modifications in 24 hours, size increase only, no cancel): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html
- January 2026 What's New post: https://aws.amazon.com/about-aws/whats-new/2026/01/amazon-ebs-up-to-four-volume-modifications/
- Monitoring modifications (states, optimizing performance): https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Modification duration example (1 TiB, about six hours, more than 24 hours): https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html and https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html
- Elastic Volumes requirements: https://docs.aws.amazon.com/ebs/latest/userguide/modify-volume-requirements.html
- Extend the file system: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/recognize-expanded-volume-linux.html
- Amazon EBS-optimized instances: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-optimized.html
- Instance type specifications: https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html
- Amazon EBS quotas: https://docs.aws.amazon.com/general/latest/gr/ebs-service.html and https://docs.aws.amazon.com/ebs/latest/userguide/ebs-resource-quotas.html
- Requesting a quota increase: https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html
- Snapshots: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-snapshots.html
- Deleting a snapshot: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-deleting-snapshot.html
- Amazon Data Lifecycle Manager: https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-lifecycle.html and https://docs.aws.amazon.com/ebs/latest/userguide/snapshot-ami-policy.html
- Recycle Bin: https://docs.aws.amazon.com/ebs/latest/userguide/recycle-bin.html
