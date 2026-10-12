# Fault Classification, Node Verdicts, Metrics, and Root-Cause Branches

<!-- Loaded by SKILL.md. Content validated live against HyperPod Slurm, HyperPod EKS, and ParallelCluster clusters. -->

## Step 4: Classify GPU and node faults

Load the Xid reference before interpreting any Xid:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/xid-triage.md")
```

For each Xid found (from any source in Step 3a):

- Record the code, the node, the PCI bus ID, and the first occurrence time.
- Use the reference to label it **hardware / node action**, **application**, or
  **sympathetic** (secondary to another error).
- If a hardware-class Xid on node N is the **first** error in the window and the job
  failed after it, node N is the leading root-cause candidate.
- If the only Xids are application-class (for example 13 or 31) and they appear on
  many nodes at once, suspect the application or a bad input, not hardware.
- Repeated hardware-class Xids on the **same** node across reboots mean that node
  should be replaced, not rebooted.

Also check the HMA event for `RepairAction` and `Recommendation` fields when present
(for example `Recommendation: Please Replace the Faulty Node.`).

## Step 4b: Node verdict (replace, reboot, or leave alone)

Give every affected node exactly one verdict, with the evidence that meets its bar.
Recommend actions only; never run them.

| Verdict | Evidence bar (all must hold) |
|---------|------------------------------|
| `REPLACE` | Xid 64 or `Remapping Failure Occurred: Yes`; fewer GPUs than the instance type has; a hardware-class Xid that recurs on the same PCI bus ID after a reboot; Xid 79 or infoROM corruption that persists after a reboot; HMA `reason: XidHardwareFailure` with a replace recommendation or the EKS label `UnschedulablePendingReplacement` |
| `REBOOT` | A first occurrence of a hardware-class Xid whose NVIDIA immediate action is a GPU reset or restart (46, 48, 62, 74, 79, 95, 109, 136, 140, 143, 158), infoROM corruption, a pending row remap, Xid 154 `GPU Reset Required` or `Node Reboot Required`, or the EKS label `UnschedulablePendingReboot`. No competing application explanation |
| `LEAVE ALONE` | Driver configuration faults (Xid 119/120: deactivate GSP), node configuration or bootstrap failures, or only application-class Xids (for example 13, 31) that name a user process, or HMA `reason: XidUserAppError`, with node status `Running` and no hardware-class Xid. Hand the process name and PID to the application owner |
| `MONITOR` | Informational or trend signals only (for example Xid 63, or 92 without escalation) |
| `NOT OBSERVABLE` | The coverage audit (Step 3a) could not prove the node's GPU signals were arriving. No verdict can be given; say what to collect |

State the verdict first in the report, then the evidence. If the user asked "should we
replace the node?", the verdict is the answer.

## Step 5: Collect storage and utilization metrics

Load the thresholds reference:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/signals-and-thresholds.md")
```

For each linked FSx for Lustre file system, pull `AWS/FSx` metrics with
`cloudwatch.GetMetricData` at 1-minute period across the impact window. Use the correct
dimensions; they differ by metric family:

| Metric | Dimensions | Stat |
|--------|-----------|------|
| `DataReadBytes`, `DataWriteBytes`, `MetadataOperations`, `ClientConnections` | `FileSystemId` | Sum |
| `NetworkThroughputUtilization`, `FileServerDiskThroughputUtilization` | `FileSystemId`, `FileServer` | Maximum |
| `DiskIopsUtilization` | `FileSystemId`, `StorageTargetId` | Maximum |
| `CPUUtilization` (metadata server) | `FileSystemId`, `FileServer` | Maximum |
| `FreeDataStorageCapacity` | `FileSystemId`, `StorageTargetId` | Sum (and Minimum per OST) |

Discover the valid `FileServer` and `StorageTargetId` values with
`cloudwatch.ListMetrics` first; do not guess them.

GPU activity signals, in order of preference:

- `AWS/EC2` `GPUPowerUtilization`, dimensions `InstanceId` and `GpuId` (discover them with
  `ListMetrics`). Published by EC2
  itself for a subset of accelerated instance types with no agent. Unit is **Percent** of
  maximum active power, so a value of `0.3` means 0.3 percent, not 30 percent.
- `CWAgent` `nvidia_smi_utilization_gpu`, `nvidia_smi_memory_used`, and `nvidia_smi_memory_total`, if the customer runs
  the CloudWatch agent with the NVIDIA plugin.

Discover which exist with `cloudwatch.ListMetrics`. If neither exists, say GPU activity was
not observable. Do not treat missing GPU metrics as zero utilization.

**Idle reserved GPUs.** When the nodes run in a Capacity Block, training plan, or other
reserved capacity, compute the hours in the window where every GPU on a node stayed below
5 percent power utilization. Report them as idle reserved hours (a finding in its own right,
because that capacity is already paid for) and use them as context: a job that was not
running cannot have been slowed by storage.

## Step 6: Decide the root-cause branch

Evaluate every branch against the timeline. Report the branch whose evidence is on
the affected nodes and precedes the failure. If two branches both have evidence,
report both, with the order in which they happened.

### Branch A: GPU / node hardware fault

Evidence: HMA detection or hardware-class Xid on the affected node before the failure;
node `InstanceStatus` `Failure`; EC2 status check failure; AWS Health hardware event.

Then check recovery:

- `NodeRecovery = None`: explains why no automatic replacement happened.
- Node stuck in `Failure` or `Pending` for a long time with `CurrentCount < TargetCount`:
  replacement is blocked. Check branch B (no capacity to replace into) and the
  `LifecycleConfig` stream (lifecycle script failing on the replacement).
- Node stuck in `DeepHealthCheckInProgress`: note that the documented DCGM level 4
  diagnostic alone typically takes about 45 to 90 minutes. Only call it stuck well past
  that range.
- Job did not resume after replacement: check whether the job used auto-resume
  (Slurm: `srun --auto-resume=1`) and whether checkpoints were written. The skill
  cannot see this directly; ask the operator.

### Branch B: capacity lifecycle

Evidence: many nodes terminated within the same few minutes; that time is 30 minutes
(instances) or 60 minutes (UltraServers) before a Capacity Block `EndDate`; or
`CurrentCount < TargetCount` with replacements not launching and the Capacity Block
or ODCR at `AvailableInstanceCount = 0`, or already `expired`. Capacity Blocks end at
11:30 UTC, and termination of instances begins at 11:00 UTC on the final day, so a mass
termination at about 11:00 UTC is a strong signature.

A Capacity Block expiry is expected behavior, not a fault. The finding is the missing
plan for it (no extension, no checkpoint before the end time, no alert on the
expiration warning event).

### Branch C: storage bottleneck (FSx for Lustre)

Evidence during the slow or stalled period: `NetworkThroughputUtilization` or
`FileServerDiskThroughputUtilization` near 100% on one or more file servers;
`DiskIopsUtilization` near 100% on OSTs; metadata server `CPUUtilization` saturated
with high `MetadataOperations`; or an OST with very low `FreeDataStorageCapacity`
while others have space (imbalanced striping).

Distinguish throughput-bound (large sequential checkpoint writes saturating network or
disk throughput) from metadata-bound (many small files, high `MetadataOperations`,
MDS CPU high, throughput well below capacity). The fix differs, so the report must say
which one the metrics show. If no FSx metric is near saturation, say storage is
**not saturated**. Do not recommend raising throughput when it isn't saturated. FSx does
not publish client-side latency, so a metadata or I/O spike without saturation makes FSx a
`Hypothesis (to validate)` as the cause of slowness, not a proven one. The confirming
measurement is client-side: time a `stat` or small-file open on the mount during the slow
period, or collect Lustre client metrics as described in
[Best practices for monitoring FSx for Lustre clients](https://aws.amazon.com/blogs/storage/best-practices-for-monitoring-amazon-fsx-for-lustre-clients-and-file-systems/).

### Branch D: GPU communication (NCCL transport, NVLink / NVSwitch, EFA)

Load the reference first:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/nccl-nvlink-efa.md")
```

Check four layers, each with its own evidence and its own `Not observable` state:

1. **NCCL transport.** Search every log source for `NCCL INFO` / `NCCL WARN`. With NCCL
   lines: EFA (`NET/OFI Selected Provider is efa`, `Using network AWS Libfabric`) versus
   silent TCP fallback (`via NET/Socket/`), and NVLink peer access (`via P2P/CUMEM`,
   `NVLS`) versus host memory (`via SHM/`). **With no NCCL lines, NCCL transport is
   `Not observable`.** Never infer it from the instance type or the security group.
2. **NVLink / NVSwitch fabric.** NVLink Xids (74, 71, 155, 156) on the affected nodes, and
   on instance types the capability profile marks as NVSwitch, whether Fabric Manager
   started (and, where the reference says so, found a usable CX bridge device). Exclude the benign systemd `PIDFile=` warning before counting
   Fabric Manager problems. Non-Xid `NVRM:` NVLink lines are listed, not classified.
3. **EFA counters.** `CWAgent` `efa_*` or HyperPod `node_amazonefa_*` retransmit, timeout,
   impaired or unresponsive remote, and work-request error counts, compared with the hang
   start.
4. **EFA preconditions.** `ec2.DescribeSecurityGroups` on `DescribeCluster.VpcConfig` (or
   the instances' groups): a self-referencing all-traffic rule inbound and outbound, as
   EFA requires. Nodes of one job split across subnets or AZs. A failed HyperPod deep
   health check (`InstanceStress` includes EFA loopback; `InstanceConnectivity` runs
   multi-node NCCL `all_reduce`).

A Branch D cause is `Proven` only with a signal from layers 1 to 3 on the affected nodes
before the hang. A missing security group rule is a proven precondition failure. Everything
else is `Hypothesis (to validate)`, and the report gives the NCCL collection command from
the reference.

### Branch E: cluster change

A HyperPod replace (`BatchReplaceClusterNodes`, or `scontrol ... reason="Action:Replace"`)
gives the node a new instance ID in the same instance group, and the node shows `Pending`
until the replacement joins. Match the `nodeIds` in the CloudTrail request to the node's
previous instance ID before treating the new instance as a different node. A reboot keeps
the instance ID.

Evidence: a CloudTrail `UpdateCluster`, `UpdateClusterSoftware`, `UpdateFileSystem`, or
manual `Batch*ClusterNodes` call shortly before the failure; `CurrentImageId` differing
from `DesiredImageId` (update in progress); nodes in `SystemUpdating`.

### Branch F: application (default when A to E are ruled out)

Report this only after A through E are each ruled out with evidence, not by default.
State which signals were checked and clean. Typical indicators: application-class Xids
on many nodes, no node or storage signal, and failure timing tied to a code, data, or
configuration change the operator reports.

## Step 7: Recommend (read-only)

Recommendations must target the branch the evidence supports. Present remediation as
operator actions to review. Do not run them.

| Branch | Typical operator actions (verify against the linked docs before running) |
|--------|---------------------------------------------------------------------------|
| A | Replace the faulty node: `aws sagemaker batch-replace-cluster-nodes --cluster-name <arn> --node-ids <id>`, or on Slurm `scontrol update node=<name> state=fail reason="Action:Replace"`. Use reboot (`batch-reboot-cluster-nodes` / `reason="Action:Reboot"`) only for transient or software faults. Set `NodeRecovery = Automatic` if it is `None`. Enable `OnStartDeepHealthChecks` so replacement nodes are validated before taking work. |
| B | Checkpoint before the Capacity Block end time, subscribe to the `Capacity Block Expiration Warning` EventBridge event, extend or purchase the next block ahead of time, and size `TargetCount` to reserved capacity. |
| C | Throughput-bound: raise throughput capacity or storage size, or stagger checkpoint writes. Metadata-bound: reduce small-file count (shard or pack datasets), and review metadata configuration. Imbalanced OSTs: review striping. |
| D | Fix the EFA security group rule; run an on-demand deep health check with `InstanceConnectivity` on the suspect nodes; collect NCCL debug logs. |
| E | Roll back or pause the change; wait for `SystemUpdating` to finish before resubmitting. |
| F | Hand to the application owner with the clean-signal list, so they do not re-investigate infrastructure. |

The manual force-down command (`state=down reason="Action:Replace"`) kills all jobs on
the node. Only mention it with that warning.
