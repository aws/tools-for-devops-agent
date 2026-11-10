# EBS Performance Background

The EBS and EC2 behavior the findings rely on. Read a section when a finding
needs it. Take current limits from the API (`DescribeVolumes`,
`DescribeInstanceTypes`) and the linked AWS documentation, not from memory.

## Volume types and their limits

| Type | Performance model | Limit to compare with |
|---|---|---|
| gp3 | Provisioned IOPS and throughput, no burst bucket. Baseline 3,000 IOPS and 125 MiB/s at any size. | `Iops` and `Throughput` from `DescribeVolumes` |
| gp2 | Baseline 3 IOPS per GiB, minimum 100, maximum 16,000. Volumes under 1 TiB can burst to 3,000 IOPS while they have I/O credits. Throughput 128 MiB/s up to 170 GiB; volumes over 170 GiB and under 334 GiB can burst to 250 MiB/s; 334 GiB and larger deliver 250 MiB/s. | Baseline `max(100, 3 x size)`, burst 3,000, throughput cap for the size |
| io1, io2 | Provisioned IOPS. `DescribeVolumes` returns no `Throughput` for these types. | `Iops` from `DescribeVolumes`, and `VolumeThroughputExceededCheck` for throughput |
| st1 | Throughput, burst bucket. Baseline 40 MiB/s per TiB, burst 250 MiB/s per TiB, up to 500 MiB/s. | Baseline and burst for the size |
| sc1 | Throughput, burst bucket. Baseline 12 MiB/s per TiB, burst 80 MiB/s per TiB, up to 250 MiB/s. | Baseline and burst for the size |

A gp2 volume earns 3 I/O credits per GiB per second and holds up to 5.4
million credits, enough for at least 30 minutes at 3,000 IOPS. While it bursts,
it spends `burst IOPS - baseline IOPS` credits per second. When `BurstBalance`
reaches 0, IOPS drops to the baseline. A gp2 volume of 1 TiB or more has a
baseline of 3,000 IOPS or more, never spends credits, and reports
`BurstBalance` at 100%.

Volume throughput limits are in MiB/s (1,048,576 bytes per second).

- [Amazon EBS General Purpose SSD volumes](https://docs.aws.amazon.com/ebs/latest/userguide/general-purpose.html)
- [Amazon EBS Provisioned IOPS SSD volumes](https://docs.aws.amazon.com/ebs/latest/userguide/provisioned-iops.html)
- [Amazon EBS Throughput Optimized HDD and Cold HDD volumes](https://docs.aws.amazon.com/ebs/latest/userguide/hdd-vols.html)

## Instance EBS limits

Every instance type has an EBS bandwidth and IOPS limit for all its volumes
together. `DescribeInstanceTypes` returns `BaselineThroughputInMBps`,
`MaximumThroughputInMBps`, `BaselineIops` and `MaximumIops`. Some sizes
(`*.4xlarge` and smaller for many families) can run at the maximum for 30
minutes at least once every 24 hours, then fall back to the baseline;
`EBSByteBalance%` and `EBSIOBalance%` show the credits left. When the instance
is the limit, every volume slows down at the same time, even though each one is
under its own limit, so changing the volumes doesn't help.

The instance limits are in MB/s (1,000,000 bytes per second), not MiB/s. For
example, a maximum of 593.75 MB/s is about 566 MiB/s, so compare the instance
total in MB/s.

- [Amazon EBS-optimized instance types](https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-type-specifications.html)
- [Amazon EBS-optimized instances](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-optimized.html)

## CloudWatch metrics

- Volume metrics are published every minute while the volume is attached.
- `VolumeStalledIOCheck`, `VolumeIOPSExceededCheck`,
  `VolumeThroughputExceededCheck` and the `VolumeAvg*` metrics are published
  only for volumes on Nitro instances, with the `VolumeId` and `InstanceId`
  dimensions. The ExceededCheck metrics aren't supported on Multi-Attach
  volumes.
- The ExceededCheck metrics report whether the workload consistently tried to
  drive more than the volume's provisioned performance in the last minute. On
  gp2 this means more than the baseline, so they can read 1 while the volume
  is still bursting.
- `InstanceEBSIOPSExceededCheck`, `InstanceEBSThroughputExceededCheck` and
  `StatusCheckFailed_AttachedEBS` are instance metrics for Nitro instances.
- `EBSIOBalance%` and `EBSByteBalance%` are published at 5-minute intervals.
- `VolumeAvgReadLatency` and `VolumeAvgWriteLatency` average only completed
  ops, so a stalled volume shows 0 ms.

- [Amazon CloudWatch metrics for Amazon EBS](https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html)
- [Amazon EBS I/O characteristics and monitoring](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html)

## Latency, IOPS and queue length

For a steady workload, completed IOPS is about the number of I/Os in flight
divided by the latency per I/O. If latency rises from 1 ms to 50 ms with 4 I/Os
in flight, IOPS falls from a few thousand to about 80, while the application
asks for the same work. So falling IOPS together with rising latency and a
full queue means the volume got slower, not that demand dropped.

CloudWatch latency is a 1-minute average of completed ops. When I/O queues up
behind a limit, the time an application waits can be much longer than this
average. `iostat` (`w_await`, `aqu-sz`) on the instance shows what the OS sees.

## Status checks

- **Volume status checks** run every 5 minutes. `io-enabled` fails when EBS
  disables I/O because the data may be inconsistent. `io-performance` compares
  actual with expected performance and exists only for gp3, io1 and io2:
  `normal`, `degraded` and `severely-degraded` (status `warning`), `stalled`
  (status `impaired`).
- **Attached EBS status check** (`StatusCheckFailed_AttachedEBS`, Nitro only)
  fails when one or more attached volumes can't complete I/O.
- When the attached EBS check fails, the AWS documentation says you can wait
  for AWS to resolve it, or replace the affected volume, or stop and start the
  instance. EBS usually recovers a volume with a failed stalled I/O check
  within a few minutes.

- [Amazon EBS volume status checks](https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-checks.html)
- [Status checks for Amazon EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-system-instance-status-check.html)

## Volume modifications

After `ModifyVolume`, the volume goes through `modifying`, `optimizing` and
`completed`. While it's optimizing, performance is between the source and
target values, and no lower than the source (or than the target, when IOPS is
lowered). Performance changes can take from a few minutes to a few hours. A
volume can be modified up to four times in a rolling 24-hour period, and only
after the previous modification is `completed`.

- [Modify a volume using Elastic Volumes operations](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-modify-volume.html)

- [Monitor the progress of Amazon EBS volume modifications](https://docs.aws.amazon.com/ebs/latest/userguide/monitoring-volume-modifications.html)

## Volumes restored from snapshots

Blocks of a volume created from a snapshot load from Amazon S3 the first time
they are read, so first access is slower until the volume is initialized.
`DescribeVolumeStatus` returns `InitializationStatusDetails` with the
initialization `Progress` (0 to 100) for these volumes, and
`DescribeFastSnapshotRestores` shows whether fast snapshot restore is enabled
for the snapshot. While io1 and io2 volumes initialize, the `io-performance`
check can show `warning`, which the AWS documentation calls expected.

- [Initialize Amazon EBS volumes](https://docs.aws.amazon.com/ebs/latest/userguide/initalize-volume.html)
- [Amazon EBS fast snapshot restore](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-fast-snapshot-restore.html)

## Fault injection (AWS FIS)

AWS FIS can pause I/O on a volume (CloudTrail event `PauseVolumeIO`) or add
latency (`InjectVolumeIOLatency`). The caller in CloudTrail is the experiment.
A paused volume shows the same signals as a real stall, so CloudTrail is how
to tell them apart.

- [AWS FIS actions reference](https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html)
