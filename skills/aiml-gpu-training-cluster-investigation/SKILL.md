---
name: aiml-gpu-training-cluster-investigation
description: Use this skill for GPU training or inference clusters on SageMaker HyperPod (Slurm or
  EKS), ParallelCluster, or self-managed EC2/EKS GPU instances. It adds three things.
  First, a GPU evidence coverage audit that proves per node whether kernel Xid logs and
  HyperPod health-agent detections were actually arriving, hour by hour, so "no errors
  found" is never reported from a silent log. Second, a node verdict (replace, reboot,
  or leave alone) against an explicit evidence bar, so an application Xid is never
  headlined as hardware. Third, a pre-flight readiness check before a long run, covering
  Capacity Block or training plan end time versus run length, spare capacity to replace
  a failed node, NodeRecovery, deep health checks, EFA, log coverage, idle reserved
  GPUs. Activate on Xid or ECC errors, slow training or FSx for Lustre slowness on a GPU
  cluster, NCCL hangs or TCP fallback, NVLink or Fabric Manager errors, nodes in Failure
  or Pending, nodes terminating at once, or "is my cluster ready for a multi- day run".
metadata:
  author: nzuresh
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Incident RCA, Chat tasks"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker HyperPod, AWS ParallelCluster, Amazon EC2, Amazon FSx for Lustre, Elastic Fabric Adapter, Amazon EKS, AWS Health"
  aws-devops-agent-skills.technical-domains: "Machine Learning, GenAI, High Performance Computing"
---

# GPU Cluster Evidence, Readiness, and Fault Verdicts

For GPU clusters on SageMaker HyperPod (Slurm or EKS), AWS ParallelCluster, and self-managed
EC2 or EKS. Generic investigation finds the obvious signals; this skill adds what it gets
wrong: silent evidence, wrong-headline hardware verdicts, and predictable failures before a
long run. **Read-only.** Never reboot, replace, update, or delete anything, and never read
training data, checkpoints, or model weights.

## Critical procedure (always, in this order)

1. **Answer in one pass.** In chat, do not stop to ask a question and do not hand off to a
   separate investigation before answering. If an input is missing, use the default (impact
   window: last 24 hours; run length: evaluate 24, 48, and 72 hours), state the assumption,
   and mark dependent checks `Needs input`. For "slow" or performance questions with no
   time given, use the last 72 hours. Offer follow-ups only after the answer.
2. **Inventory and capability profile.** HyperPod: `sagemaker.DescribeCluster` and
   `ListClusterNodes` (paginate). EC2/ParallelCluster/EKS: `ec2.DescribeInstances`. For every
   GPU instance type: `ec2.DescribeInstanceTypes` (strip HyperPod `ml.`): GPU count,
   `EfaSupported`, `MaximumEfaInterfaces`; per EC2 node, attached `efa`/`efa-only` interfaces.
   Report `<attached> of <max>`, where attached = interfaces with `InterfaceType` `efa` or
   `efa-only` (the primary ENA interface does not count unless it is `efa`). HyperPod nodes
   are not visible to `DescribeInstances`: say so. On NVSwitch types, search every log source
   found in step 4 for `Started "Nvidia Fabric Manager"` before saying it is not confirmed.
3. **Node identity survives replacement.** A HyperPod reboot keeps the instance ID; a replace
   gives the node a **new instance ID in the same instance group**, so the current ID will
   never appear in the replace request. Query CloudTrail **by event name, not by instance
   ID**: `cloudtrail.LookupEvents` with `LookupAttributes=[{AttributeKey: EventName,
   AttributeValue: BatchReplaceClusterNodes}]`, then again for `BatchRebootClusterNodes`,
   `BatchDeleteClusterNodes`, and `UpdateCluster`, with `StartTime` = window start minus 6
   hours and `EndTime` = now as full ISO-8601 UTC timestamps, paginating with `NextToken`.
   Keep events whose `requestParameters.clusterName` is this cluster. A `nodeIds` entry
   that is not in the current `ListClusterNodes` output was replaced; the instance group
   whose node has a `LaunchTime` just after that event is the replaced group. That operator
   or automatic call is the explanation for the node going `Pending` (Branch E), not hardware.
4. **Find every log source by substring, not prefix.** Call `logs.DescribeLogGroups` with
   `logGroupNamePattern` (case-sensitive substring) = the cluster name, then again for
   `kernel`, `messages`, `syslog`, `journal`, and `gpu`, paginating with `nextToken`. Never
   search only `/aws/parallelcluster` or `/aws/sagemaker` prefixes: customer pipelines use
   other names (for example `/aws/<pipeline>/<cluster>/kernel`). Evaluate every source found.
5. **Prove coverage before any "no errors".** For each node and source: find the stream that
   carries `kernel:` lines, then bin **that exact stream** by hour across the window padded by
   one hour. Any empty hour means `Not observable` for that hour. First and last event times
   are not proof, and the time of the **last `kernel:` line** is not when logging stopped:
   a healthy kernel goes quiet. Liveness comes only from the hourly bins of all lines in
   that stream. A node is `Measured` if one source passes. HyperPod: a missing
   `SagemakerHealthMonitoringAgent/<group>/<instance-id>` stream means `No HMA detections`
   when the cluster log group is otherwise live. NCCL transport with no `NCCL INFO` lines
   anywhere is `Not observable`; never infer it from the instance type.
6. **Verdict per node, headline to match.** `REPLACE`, `REBOOT`, `LEAVE ALONE`, `MONITOR`, or
   `NOT OBSERVABLE`, against the evidence bar in `references/incident-branches.md` (Step 4b).
   Application-class Xids (for example 13, 31) or HMA `reason: XidUserAppError` with the node
   `Running` is `LEAVE ALONE`. Never headline "hardware error" unless the verdict is `REPLACE`
   or `REBOOT` on hardware grounds.
7. **Label every cause** `Proven` (measured signal on the affected node, before the failure,
   nothing competing) or `Hypothesis (to validate)` with the one confirming measurement. A
   spike at the same time is correlation. FSx without a saturated metric is not a proven cause.
   Only a `Proven` cause may be called the root cause, in the headline or in a branch table.
   Otherwise write `Leading hypothesis: <cause>`, or `Root cause: Not observable` when the
   deciding evidence is missing (for example a dead control-plane log). Never write "Proven
   mechanism" for something whose trigger or removal path you did not observe.
   Utilization metrics from FSx (`NetworkThroughputUtilization`, `DiskIopsUtilization`, and
   similar) and `GPUPowerUtilization` are already percent from 0 to 100: a value of `0.9` is
   0.9 percent. Quote the raw value with a percent sign.
8. **Recovery questions** always state three things: whether automatic node recovery is on
   (`NodeRecovery`), what it does (reboot or replace the node), and that the **job** resumes
   only with checkpoints plus the orchestrator's auto-resume (Slurm on HyperPod:
   `srun --auto-resume=1`).
9. **Capacity Blocks** begin terminating instances 30 minutes before the end time (60 for
   UltraServers); blocks end at 11:30 UTC and termination starts at 11:00 UTC on the last day.
   For a planned run, write out: usable until = end time minus the lead time; run end = start
   plus run length; hours covered = usable until minus start. Give every value as a full UTC
   date and time, and check the latest safe start is not already in the past.
10. **Rule out the frequent non-GPU causes** in `references/cluster-edge-cases.md` before
   blaming hardware: subnet IP or network interface exhaustion, ParallelCluster bootstrap
   failures and protected mode, EFA nodes in a public subnet, a Capacity Block not yet
   active, and the FSx maintenance window. HyperPod does not export system metrics to
   CloudWatch, so HyperPod GPU activity is `Not observable` there.

## Pick the mode

| The user asks | Mode | Run |
|---------------|------|-----|
| Something failed, hung, slowed, or lost nodes | **I: Incident** | Steps 1 to 6 |
| "Were there GPU errors?", "Can I trust the logs?" | **C: Coverage audit** | Steps 1 to 3, report the coverage table |
| "Is the cluster ready for a long run?", Capacity Block ending | **P: Pre-flight** | Steps 1 to 3, then Mode P |

## Step 1: Scope

Account, region, cluster name or instance IDs, workload, impact window (default last 24 hours,
stated). Classify the symptom to pick a starting branch (Step 5), but collect evidence for all.

## Step 2: Inventory and timeline

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/inventory-and-timeline.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/cluster-edge-cases.md")
```

Build one ordered timeline for the window plus 30 minutes each side: node state, HMA
detections, Xids, AWS Health, EC2 status and scheduled events, Capacity Block and training plan
end times, and CloudTrail cluster changes (critical procedure 3).

## Step 3: Coverage audit

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/coverage-audit.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/nccl-nvlink-efa.md")
```

Produce the coverage table and the node capability and fabric table for every affected node.

## Step 4: Classify faults and give node verdicts

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/xid-triage.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/incident-branches.md")
```

## Step 5: Metrics and root-cause branch

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/signals-and-thresholds.md")
```

Pull FSx (correct dimensions per metric), GPU activity (`AWS/EC2` `GPUPowerUtilization`, unit
Percent, or `CWAgent`), and EFA counters, then evaluate branches A (hardware), B (capacity
lifecycle), C (storage), D (NCCL, NVLink/NVSwitch, EFA), E (cluster change), and F (application,
only after A to E are ruled out), as defined in `incident-branches.md`. Recommend operator
actions only.

## Mode P: Pre-flight readiness

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/preflight.md")
```

Score checks P1 to P16. Lead with FAIL, then RISK.

## Step 6: Report

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/report-format.md")
```

## Success criteria

- Coverage table and node capability table for every affected node; no "no errors" without
  proven coverage.
- One verdict per node with a GPU signal; headline consistent with the verdicts.
- Every cause labelled `Proven` or `Hypothesis (to validate)`.
- Replaced nodes matched to the operator or automatic action that replaced them.
- Mode P: P1 to P16 scored.
- No mutating API call was made.

## References

- [HyperPod health monitoring system](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-eks-resiliency-health-monitoring-agent.html)
- [HyperPod deep health checks](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-resiliency-slurm-deep-health-checks.html)
- [Manually replace or reboot a HyperPod node](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-resiliency-slurm-replace-faulty-instance.html)
- [HyperPod Slurm cluster logging](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-cluster-management-slurm.html)
- [ClusterInstanceStatusDetails](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_ClusterInstanceStatusDetails.html)
- [How Capacity Blocks work](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-how.html)
- [EFA security group requirements](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa-start-nccl.html)
- [Monitor Capacity Blocks using EventBridge](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-monitor.html)
- [FSx for Lustre metrics and dimensions](https://docs.aws.amazon.com/fsx/latest/LustreGuide/fs-metrics.html)
- [NVIDIA Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html)
- [EC2 accelerator metrics (GPUPowerUtilization)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html#accelerator-metrics)
- [DescribeTrainingPlan](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingPlan.html)
- [DescribeCapacityBlockExtensionOfferings](https://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeCapacityBlockExtensionOfferings.html)
