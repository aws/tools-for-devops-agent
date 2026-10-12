# Signals and Thresholds

Thresholds here are investigation heuristics for flagging a signal as worth reporting.
They are not AWS service limits. State the observed value, not only the label.

## HyperPod node state

Valid `InstanceStatus.Status` values
([ClusterInstanceStatusDetails](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ClusterInstanceStatusDetails.html)):
`Running | Failure | Pending | ShuttingDown | SystemUpdating | DeepHealthCheckInProgress | NotFound`.

| Signal | Flag when |
|--------|-----------|
| Node in `Failure` | Always. Correlate with HMA log for that instance. |
| Node in `Pending` | Longer than 30 minutes: replacement or launch blocked. Check capacity and `LifecycleConfig` logs. |
| Node in `DeepHealthCheckInProgress` | Well past 2 hours. DCGM level 4 alone typically takes about 45 to 90 minutes, and the stress, EFA, and NCCL tests add to it. Check `DeepHealthCheckResults/<id>` streams first |
| `CurrentCount < TargetCount` | Persisting across two inventory reads. |
| `NodeRecovery = None` | Always report. Automatic reboot or replace is disabled. |
| `CurrentImageId != DesiredImageId` | Software update in progress or stalled. |

## FSx for Lustre (`AWS/FSx`)

Metric semantics and dimensions:
[FSx for Lustre metrics and dimensions](https://docs.aws.amazon.com/fsx/latest/LustreGuide/fs-metrics.html).

| Metric (dimensions) | Stat | Flag when | Meaning |
|---------------------|------|-----------|---------|
| `NetworkThroughputUtilization` (FileSystemId, FileServer) | Maximum | ≥ 90% sustained 5+ min | File server network throughput saturated |
| `FileServerDiskThroughputUtilization` (FileSystemId, FileServer) | Maximum | ≥ 90% sustained 5+ min | OSS-to-disk throughput saturated |
| `DiskIopsUtilization` (FileSystemId, StorageTargetId) | Maximum | ≥ 90% sustained 5+ min | OST IOPS saturated (not on Scratch or Persistent HDD) |
| `CPUUtilization` (FileSystemId, FileServer = MDS*) | Maximum | ≥ 90% sustained 5+ min | Metadata server saturated |
| `MetadataOperations` (FileSystemId) | Sum / period | Sharp rise aligned with the slowdown | Metadata-heavy workload |
| `FreeDataStorageCapacity` (FileSystemId, StorageTargetId) | Minimum per OST | Any OST < 10% free while others have space | Imbalanced striping, write failures possible |
| `DataReadBytes` + `DataWriteBytes` (FileSystemId) | Sum / period | Drop aligned with the stall | Clients stopped doing I/O (effect, not cause) |

Throughput in bytes per second is `Sum / period_seconds`. Do not report raw `Sum` as a
rate.

A drop in client I/O during a hang is usually the **effect** of the job stalling. It
points at storage only if a saturation metric above rose first.

## GPU activity

`AWS/EC2` `GPUPowerUtilization` (dimensions `InstanceId` and `GpuId`, as observed in live
accounts; the EC2 docs list the metric but not the `GpuId` dimension) is published by EC2 for a
subset of accelerated instance types without an agent. Unit is Percent of maximum active
power ([EC2 accelerator metrics](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html#accelerator-metrics)).

| Signal | Flag when |
|--------|-----------|
| Every GPU on a node below 5% power for an hour | Idle hour (heuristic). On reserved capacity, count it as an idle reserved hour |

## GPU utilization (`CWAgent`, optional)

Present only if the customer runs the CloudWatch agent with the NVIDIA plugin.

| Metric | Flag when |
|--------|-----------|
| `nvidia_smi_utilization_gpu` | One node near 0% while peers are busy: straggler or dead rank |
| `nvidia_smi_utilization_gpu` | All nodes drop to near 0% together: collective hang, storage stall, or job exit |
| `nvidia_smi_memory_used` / `nvidia_smi_memory_total` | Ratio near 1 just before failure: possible GPU out-of-memory (application). (`nvidia_smi_utilization_memory` measures memory read/write activity, not how full memory is) |

If the `CWAgent` namespace has no NVIDIA metrics, report GPU utilization as not
observable. Never read an absent metric as zero.

## Capacity Blocks

From [How Capacity Blocks work](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-how.html)
and [Monitor Capacity Blocks](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-monitor.html):

- Instances begin terminating 30 minutes (instance types) or 60 minutes (UltraServer
  types) before the Capacity Block end time.
- An EventBridge `Capacity Block Expiration Warning` is emitted 40 minutes before the end.
- Capacity Blocks end at 11:30 UTC, and termination begins at 11:00 UTC on the final day.
- States: `payment-pending`, `payment-failed`, `scheduled`, `active`, `expired`.
