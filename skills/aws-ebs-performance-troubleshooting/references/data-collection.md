# Data Collection

All calls are read-only and use the agent's AWS access in the target account
and region. Collect in this order, because later steps use earlier results.

Time window: `T0` is the start of the problem. Use `T0 - 60 min` to now for an
ongoing problem, or `T0 - 60 min` to `T0 + 60 min` for a past one. If `T0` is
unknown, use the last 3 hours and find it in step 3.

## 1. Inventory

| Call | Parameters | Keep |
|---|---|---|
| `ec2:DescribeInstances` | `InstanceIds=[<id>]` | `InstanceType`, `State`, `EbsOptimized`, `LaunchTime`, `BlockDeviceMappings[].Ebs.VolumeId` and `DeviceName` |
| `ec2:DescribeVolumes` | `VolumeIds=[...]` from the mappings, or `Filters=[attachment.instance-id=<id>]` | `VolumeType`, `Size`, `Iops`, `Throughput`, `SnapshotId`, `CreateTime`, `MultiAttachEnabled`, `State`, `Attachments` |
| `ec2:DescribeInstanceTypes` | `InstanceTypes=[<type>]` | `Hypervisor` (`nitro` or `xen`), `BareMetal`, `EbsInfo.EbsOptimizedInfo` (`BaselineThroughputInMBps`, `MaximumThroughputInMBps`, `BaselineIops`, `MaximumIops`) |
| `ec2:DescribeVolumesModifications` | `VolumeIds=[...]` | Any modification with `StartTime` in or just before the window, its `ModificationState` and `Progress` |
| `ec2:DescribeFastSnapshotRestores` | `Filters=[snapshot-id=<SnapshotId>]`, only for volumes with a `SnapshotId` | `State` per Availability Zone |

Take the hypervisor from `DescribeInstanceTypes`, not from the instance's
`Hypervisor` field in `DescribeInstances`: EC2 reports `xen` there for both Xen
and Nitro instances. A value of `xen` in `DescribeInstances` is not a gap.

`BaselineThroughputInMBps` and `MaximumThroughputInMBps` are in MB/s (10^6
bytes per second). Volume throughput limits are in MiB/s. Keep each in its own
unit when comparing.

With a volume ID only, call `DescribeVolumes` first and take the instance from
`Attachments[].InstanceId`. If the volume isn't attached, CloudWatch has no
volume metrics for it: say so and stop.

Work out each volume's expected limits from `references/ebs-performance-background.md`:
baseline and burst IOPS for gp2, baseline and burst throughput for st1 and sc1,
provisioned IOPS and throughput for gp3, io1 and io2.

## 2. Status

| Call | Parameters | Keep |
|---|---|---|
| `ec2:DescribeVolumeStatus` | `VolumeIds=[...]` | `VolumeStatus.Status`, each `Details[]` entry (`io-enabled`, `io-performance`, `initialization-state`), every `Events[]` entry (`EventType`, `Description`, `NotBefore`, `NotAfter`, `EventId`), `Actions[]`, and `InitializationStatusDetails` (`InitializationType`, `Progress`) for volumes created from snapshots. The initialization details can take up to 5 minutes to appear after the volume is created. |
| `ec2:DescribeInstanceStatus` | `InstanceIds=[<id>]`, `IncludeAllInstances=true` | `SystemStatus`, `InstanceStatus`, `AttachedEbsStatus` with `Details[].ImpairedSince` |

The `io-performance` check exists only for gp3, io1 and io2 volumes. For gp2,
st1, sc1 and standard, its absence is expected.

## 3. CloudWatch metrics

Use `cloudwatch:GetMetricData` with `Period=60` unless the table says
otherwise, over the time window. Convert counts per period to per-second rates
by dividing by the period in seconds.

### Per volume, dimension `VolumeId` only (`AWS/EBS`)

| Metric | Statistic | Use |
|---|---|---|
| `VolumeReadOps`, `VolumeWriteOps` | Sum | Completed IOPS |
| `VolumeReadBytes`, `VolumeWriteBytes` | Sum | Throughput, and average I/O size (bytes / ops) |
| `VolumeTotalReadTime`, `VolumeTotalWriteTime` | Sum | Average latency per op (total time / ops), when the Nitro latency metrics are missing |
| `VolumeQueueLength` | Average | I/O waiting to complete |
| `VolumeIdleTime` | Sum | Seconds with nothing submitted |
| `BurstBalance` | Minimum | gp2, st1 and sc1 only: burst credits left |
| `VolumeThroughputPercentage` | Average | io1 and io2 only: share of provisioned IOPS delivered |

### Per volume, dimensions `VolumeId` and `InstanceId` (`AWS/EBS`, Nitro only)

These metrics have both dimensions. A query with `VolumeId` only returns no
data points.

| Metric | Statistic | Use |
|---|---|---|
| `VolumeStalledIOCheck` | Maximum | 1 = the volume failed the stalled I/O check in that minute |
| `VolumeIOPSExceededCheck` | Maximum | 1 = the workload tried to drive more IOPS than the volume's provisioned (or gp2 baseline) IOPS |
| `VolumeThroughputExceededCheck` | Maximum | 1 = the workload tried to drive more throughput than provisioned |
| `VolumeAvgReadLatency`, `VolumeAvgWriteLatency` | Average | Average latency of completed ops, in ms |
| `VolumeAvgIOPS`, `VolumeAvgThroughput` | Average | Average IOPS and KiB/s driven |

If the instance is Xen or bare metal, or a volume is Multi-Attach enabled,
some of these aren't published. Fall back to the `VolumeId`-only metrics and
the status checks, and record the gap.

### Per instance, dimension `InstanceId` (`AWS/EC2`)

| Metric | Statistic | Period | Use |
|---|---|---|---|
| `EBSReadOps`, `EBSWriteOps` | Sum | 60, or 300 without detailed monitoring | Total IOPS across all volumes |
| `EBSReadBytes`, `EBSWriteBytes` | Sum | 60, or 300 | Total throughput across all volumes, in MB/s as `bytes / period / 1,000,000` |
| `EBSIOBalance%`, `EBSByteBalance%` | Minimum | 300 | Instance burst credits left (only on instance sizes that burst) |
| `InstanceEBSIOPSExceededCheck`, `InstanceEBSThroughputExceededCheck` | Maximum | 60 | 1 = the workload tried to exceed the instance's EBS IOPS or throughput limit (Nitro only) |
| `StatusCheckFailed_AttachedEBS` | Maximum | 60 | 1 = one or more attached volumes can't complete I/O (Nitro only) |

`EBSIOBalance%` and `EBSByteBalance%` are published every 5 minutes. In a
1-minute query they show gaps; use a 300-second period.

If `GetMetricData` returns an empty result for a metric, call
`cloudwatch:ListMetrics` with the namespace and the `VolumeId` or `InstanceId`
dimension to see which metrics and dimensions exist, then retry with the right
dimensions.

## 4. Changes

### CloudTrail

`cloudtrail:LookupEvents` takes one lookup attribute per call. For the window
from `T0 - 2 h` to now, run:

1. `ResourceName=<volume-id>` for each volume.
2. `ResourceName=<instance-id>`.
3. `EventName=PauseVolumeIO` and `EventName=InjectVolumeIOLatency`. AWS FIS
   experiments make these calls, and their resource name may not match the
   volume ID, so steps 1 and 2 can miss them.

Page through `NextToken` until the window is covered. Parse each event's
`CloudTrailEvent` JSON and keep the events where `readOnly` is `false`. For
each, keep `eventTime`, `eventName`, `eventSource`, the caller
(`userIdentity`), the target resources and the request parameters.

Keep every mutating event, not only well-known ones. Then classify them in
`references/finding-logic.md`.

### AWS FIS (always)

CloudTrail can take several minutes to deliver an event, so during a live
problem `PauseVolumeIO` or `InjectVolumeIOLatency` may not be there yet. Check
experiments directly every time:

1. `fis:ListExperiments`: keep every experiment whose `state.status` is
   `running`, or whose `creationTime` is in the window, with its `id`,
   `experimentTemplateId`, `state.status` and `creationTime`.
2. `fis:ListExperimentResolvedTargets` with each experiment `id`: keep the
   ones whose targets include the instance or one of its volumes.
3. `fis:GetExperimentTemplate` with the template ID of each kept experiment:
   keep the action and its duration, to say what it does and when the effect
   ends.

The effect starts when the action runs, a few seconds after the experiment
starts. Use the `eventTime` of `PauseVolumeIO` or `InjectVolumeIOLatency` in
CloudTrail as the start when it's there; otherwise use the experiment's start
time and say "about". The effect ends at that start plus the action's
duration.

The agent's default permissions don't allow `fis:GetExperiment`.

## 5. AWS Health

Do this in every run, in chat and in investigations. Hand off to the
`aws-health-events` skill for EBS and EC2 events in the region and window,
including events that name the volume or the instance. If that skill isn't
available, call `health:DescribeEvents` in `us-east-1` with
`filter={services:[EBS, EC2], regions:[<region>], startTimes:[{from:<T0 - 2 h>}]}`
and keep each event's `arn`, `eventTypeCode`, `statusCode`, `startTime` and
`endTime`. If the API reports that it isn't available (`SubscriptionRequiredException`:
the API needs a Business Support+, Enterprise Support or Unified Operations
plan), record this as a data gap and tell the user to check the AWS Health
Dashboard.

## 6. From inside the instance (ask the user)

The agent can't run commands on the instance. When the conclusion depends on
what the OS sees, ask the user for:

- Linux: `iostat -x 1 10` (for `r_await`, `w_await`, `aqu-sz`, `%util`) and
  `dmesg -T | tail -50` (for NVMe timeouts or I/O errors).
- Windows: Performance Monitor counters `Avg. Disk sec/Read`,
  `Avg. Disk sec/Write` and `Current Disk Queue Length`, and the System event
  log for disk or `stornvme` errors.

## Errors and gaps

| Result | What to do |
|---|---|
| `AccessDenied` or `UnauthorizedOperation` | Record the call and the missing action as a data gap. Continue. Name the gap in the answer. |
| Throttling | Retry with backoff up to 3 times, then record a gap. |
| Empty metric | Check the dimensions with `ListMetrics`. If still empty, record "not published" with the likely reason (Xen, bare metal, Multi-Attach, volume not attached, or wrong region). |
| Volume or instance not found | Check the region, then ask the user. |

## Allowlist

Only these actions are called: `ec2:DescribeInstances`, `ec2:DescribeVolumes`,
`ec2:DescribeInstanceTypes`, `ec2:DescribeVolumesModifications`,
`ec2:DescribeFastSnapshotRestores`, `ec2:DescribeVolumeStatus`,
`ec2:DescribeInstanceStatus`, `cloudwatch:GetMetricData`,
`cloudwatch:ListMetrics`, `cloudtrail:LookupEvents`, `fis:ListExperiments`,
`fis:ListExperimentResolvedTargets`, `fis:GetExperimentTemplate`, and
`health:DescribeEvents` when the `aws-health-events` skill isn't available.
AWS Support calls are made by the `support-cases` skill.
