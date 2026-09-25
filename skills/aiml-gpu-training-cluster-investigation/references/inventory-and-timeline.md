# Inventory and Event Timeline

<!-- Loaded by SKILL.md. Content validated live against HyperPod Slurm, HyperPod EKS, and ParallelCluster clusters. -->

## Inventory (Step 2): Inventory the cluster

**HyperPod:**

```
sagemaker.ListClusters                       # find the cluster if only a name fragment is known
sagemaker.DescribeCluster                    # Orchestrator (Slurm|Eks), NodeRecovery, InstanceGroups
                                             # (InstanceType, CurrentCount, TargetCount,
                                             # OnStartDeepHealthChecks, TrainingPlanArn,
                                             # CurrentImageId vs DesiredImageId), VpcConfig
sagemaker.ListClusterNodes                   # paginate with NextToken until exhausted
sagemaker.DescribeClusterNode                # for every node not in Running, and for any node
                                             # named in the symptom
```

Record per node: instance ID, instance group, instance type, `InstanceStatus.Status`
(`Running | Failure | Pending | ShuttingDown | SystemUpdating |
DeepHealthCheckInProgress | NotFound`), `InstanceStatus.Message`, launch time, and
private DNS name (the Slurm node name is derived from the private IP).

Compute per instance group: `CurrentCount` vs `TargetCount`. A persistent shortfall
means nodes are failing to be replaced (branch A or B).

Record `NodeRecovery`. If it is `None`, HyperPod will not reboot or replace faulty
nodes automatically, and any "auto-resume didn't work" complaint starts there.

**AWS ParallelCluster or self-managed EC2 or EKS GPU nodes:**

ParallelCluster nodes carry tags such as `parallelcluster:cluster-name`,
`parallelcluster:node-type` (`HeadNode` or `Compute`), `parallelcluster:queue-name`, and
`parallelcluster:version`. Use them to group compute nodes by cluster and queue, and
keep the head node in scope (it runs `slurmctld` and `clustermgtd`).

```
ec2.DescribeInstances                        # filter by tag, instance IDs, or instance-type
                                             # p4d.*, p5.*, p5e.*, p5en.*, p6*.*, g5.*, g6*.*
ec2.DescribeInstanceStatus                   # IncludeAllInstances=true; status checks and
                                             # scheduled events
eks.DescribeCluster / eks.ListNodegroups / eks.DescribeNodegroup   # if EKS
```

**Instance capability profile (every orchestrator, every GPU instance type in the cluster):**

Do not assume anything from the instance family name. Read it:

```
ec2.DescribeInstanceTypes                    # for each distinct type; strip the HyperPod "ml."
                                             # prefix (ml.p5.48xlarge -> p5.48xlarge).
                                             # Record GpuInfo.Gpus[].Count and Name,
                                             # NetworkInfo.EfaSupported,
                                             # NetworkInfo.EfaInfo.MaximumEfaInterfaces
ec2.DescribeInstances                        # per node: count NetworkInterfaces with
                                             # InterfaceType efa or efa-only
```

Derive, per instance type, which checks apply:

| Property | Source | Checks it turns on |
|----------|--------|--------------------|
| More than one GPU per node | `GpuInfo` count | Intra-node transport (NVLink / P2P vs SHM) |
| `EfaSupported` and more than one node in the job | `NetworkInfo` | Inter-node transport (EFA vs socket fallback), EFA counters, EFA security group |
| EFA interfaces attached per node vs `MaximumEfaInterfaces` | `DescribeInstances` vs `DescribeInstanceTypes` | Fewer attached than the maximum is a RISK: less inter-node bandwidth than the instance supports. Report `<attached> of <max>`. HyperPod nodes run in a SageMaker-managed account, so `DescribeInstances` in the customer account cannot see them: report attached EFA as `Not observable` for HyperPod |
| NVSwitch fabric | `references/nccl-nvlink-efa.md` section 4 (documented families only) | NVLink Xids, Fabric Manager start lines. Unlisted multi-GPU types: `NVSwitch presence unverified`; the operator checks `nvidia-smi topo -m` |
| Software minimums | `references/nccl-nvlink-efa.md` section 5 | Pre-flight P11 |

**For both:**

```
ec2.DescribeCapacityReservations             # capacity reservations the nodes run in:
                                             # ReservationType (capacity-block or default),
                                             # State, StartDate, EndDate, TotalInstanceCount,
                                             # AvailableInstanceCount
fsx.DescribeFileSystems                      # Lustre file systems in the cluster VPC:
                                             # DeploymentType, StorageCapacity,
                                             # PerUnitStorageThroughput, Lifecycle
```

Link each FSx file system to the cluster by VPC and subnet. If none is found, state that
storage was not assessed.

## Event timeline (Step 3): Build the event timeline

Pull all of these for the impact window ±30 minutes, then merge them into one ordered
timeline:

1. **GPU driver (NVRM) messages, from every log source that has them.** The NVIDIA
   driver writes Xids to the OS system log as `NVRM: Xid (PCI:<bus-id>): <code>, ...`.
   EC2 cannot see them from outside the instance, so they reach CloudWatch Logs only
   if something on the node ships them. Find the source for the orchestrator (see
   **Step 3a** below), then run this Logs Insights query against each source:

   ```
   fields @timestamp, @logStream, @message
   | filter @message like /NVRM: Xid/
   | sort @timestamp asc
   | limit 200
   ```

   Extract per Xid: instance (from the stream name or message), code, PCI bus ID, and
   first-occurrence time.

2. **HyperPod health-monitoring agent (HMA) detections** (HyperPod only). Log group
   `/aws/sagemaker/Clusters/<ClusterName>/<ClusterId>`, per-node log stream
   `SagemakerHealthMonitoringAgent/<instance-group>/<instance-id>`:

   ```
   fields @timestamp, @logStream, @message
   | filter @message like /HealthMonitoringAgentDetectionEvent/
   | sort @timestamp asc
   ```

   Extract per event: instance, `reason`, node condition (for example
   `NvidiaErrorReboot`, `NvidiaErrorTerminate`), any `NVRM: Xid (...): <code>` text, and
   DCGM policy violations (`"condition: ":"XID Error"` with `ErrNum`). HMA's own
   `reason` is a strong classification signal: `XidHardwareFailure` points to Branch A,
   while `XidUserAppError` means HMA judged the Xid application-caused and took no node
   action, which points to Branch F.

3. **Other HyperPod log streams** (HyperPod only) in the same log group, including
   `LifecycleConfig/<instance-group>/<instance-id>` for lifecycle script failures on
   replacement nodes, and any deep health check streams. Filter for `ERROR`, `FAIL`,
   `Xid`, `EFA`, `NCCL`.

4. **AWS Health.** `health.DescribeEvents` filtered to services `EC2` and `SAGEMAKER`
   and the region, then `health.DescribeAffectedEntities` for the cluster's instance
   IDs. Scheduled retirement or hardware degradation on an affected instance is a
   strong signal.

5. **EC2 instance status.** From `ec2.DescribeInstanceStatus`: failed system or
   instance status checks, and scheduled events (`instance-retirement`,
   `system-reboot`, `system-maintenance`).

6. **Capacity Block window.** For every capacity reservation with
   `ReservationType = capacity-block`, add its `EndDate` to the timeline. EC2 begins
   terminating instances in a Capacity Block 30 minutes before the end time for
   instance types and 60 minutes before for UltraServer types, and emits a
   `Capacity Block Expiration Warning` event 40 minutes before the end.

7. **Cluster control-plane changes.** `cloudtrail.LookupEvents` with
   `EventSource = sagemaker.amazonaws.com` for `UpdateCluster`,
   `UpdateClusterSoftware`, `BatchReplaceClusterNodes`, `BatchRebootClusterNodes`,
   `BatchDeleteClusterNodes`, and `StartClusterHealthCheck`; with
   `EventSource = ec2.amazonaws.com` for `TerminateInstances`; and with
   `EventSource = fsx.amazonaws.com` for `UpdateFileSystem`. Record who made the
   change and when. If `LookupEvents` needs operator approval in this runtime, ask
   once and continue without it if denied, and name the gap in the report.
