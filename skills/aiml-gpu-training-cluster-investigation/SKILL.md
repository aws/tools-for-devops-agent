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
  or Pending, nodes terminating at once, or "is my cluster ready for a multi-day run".
metadata:
  author: nzuresh
  version: "1.0.4"
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

## Critical rules R1 to R11 (apply in every mode, in this order)

R1. **Answer in one pass, and always leave room to answer.** In chat, do not stop to ask a
   question and do not hand off to a separate investigation before answering. If an input is
   missing, use the default (impact window: last 24 hours; run length: evaluate 24, 48, and
   72 hours), state the assumption, and mark dependent checks `Needs input`. For "slow" or
   performance questions with no time given, use the last 72 hours. Offer follow-ups only
   after the answer.
   **Budget the evidence gathering so the answer always gets written.** An investigation that
   runs out of room before it reports is worth nothing to the operator, and it is worse than a
   partial answer because it looks like a failure rather than a finding. So: collect the
   mandatory evidence for the mode first (R2, R4, R5, and for Mode P the P1 to P6 core), then
   write the report. Pick up the optional checks only with what is left. If you notice you are
   deep into tool calls and have not yet produced an answer, **stop collecting and report what
   you have**, marking everything unreached as `Not checked` with the call that would close
   it. Never end a turn with evidence gathered and no verdict.
R2. **Inventory and capability profile.** HyperPod: `sagemaker.DescribeCluster` and
   `ListClusterNodes` (paginate). Read `NodeProvisioningMode` from `DescribeCluster`: if it is
   `Continuous`, also pull `sagemaker.ListClusterEvents` for the window (see rule R11), which
   is the only timeline source that survives broken log delivery. On any other value the call
   is unsupported and must be skipped, not retried.
   EC2/ParallelCluster/EKS: `ec2.DescribeInstances`. For every
   GPU instance type: `ec2.DescribeInstanceTypes` (strip HyperPod `ml.`): GPU count,
   `EfaSupported`, `MaximumEfaInterfaces`; per EC2 node, attached `efa`/`efa-only` interfaces.
   Report `<attached> of <max>`, where attached = interfaces with `InterfaceType` `efa` or
   `efa-only` (the primary ENA interface does not count unless it is `efa`). HyperPod nodes
   are not visible to `DescribeInstances`: say so. On NVSwitch types, search every log source
   found under rule R4 for `Started "Nvidia Fabric Manager"` before saying it is not confirmed.
R3. **Node identity survives replacement.** A HyperPod reboot keeps the instance ID; a replace
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
R4. **Find every log source by substring, not prefix.** Call `logs.DescribeLogGroups` with
   `logGroupNamePattern` (case-sensitive substring) = the cluster name, then again for
   `kernel`, `messages`, `syslog`, `journal`, and `gpu`, paginating with `nextToken`. Never
   search only `/aws/parallelcluster` or `/aws/sagemaker` prefixes: customer pipelines use
   other names (for example `/aws/<pipeline>/<cluster>/kernel`). Evaluate every source found.
R5. **Prove coverage before any "no errors".** For each node and source: find the stream that
   carries `kernel:` lines, then bin **that exact stream** by hour across the window padded by
   one hour. **Always name the evidence you used: quote the full log group name and the exact
   log stream name for every node in the coverage table, and again in the answer text.** A
   coverage claim without the group and stream it rests on is not auditable, so the operator
   cannot re-run it. Any empty hour means `Not observable` for that hour. First and last event times
   are not proof, and the time of the **last `kernel:` line** is not when logging stopped:
   a healthy kernel goes quiet. Liveness comes only from the hourly bins of all lines in
   that stream. A node is `Measured` if one source passes. HyperPod: a missing
   `SagemakerHealthMonitoringAgent/<group>/<instance-id>` stream means `No HMA detections`
   when the cluster log group is otherwise live. NCCL transport with no `NCCL INFO` lines
   anywhere is `Not observable`; never infer it from the instance type.
R5a. **Name every resource you looked at, by ID.** A finding the operator cannot re-run is
   not a finding. Whatever you analysed, put its identifier in the answer: the FSx file system
   (`fs-...`) behind any storage claim, the instance IDs (`i-...`) behind any node claim, the
   cluster name, the capacity reservation (`cr-...`) behind any capacity claim, and the log
   group and stream behind any log claim as R5 already requires. "The file system was
   saturated" or "the metrics looked fine" names nothing and cannot be checked. This applies
   to the resource you cleared as much as the one you blamed, since ruling something out is
   only useful if the reader knows what was ruled out.
R6. **Verdict per node, headline to match.** `REPLACE`, `REBOOT`, `LEAVE ALONE`, `MONITOR`, or
   `NOT OBSERVABLE`, against the evidence bar in `references/incident-branches.md` (Step 4b).
   Application-class Xids (for example 13, 31) or HMA `reason: XidUserAppError` with the node
   `Running` is `LEAVE ALONE`. Never headline "hardware error" unless the verdict is `REPLACE`
   or `REBOOT` on hardware grounds.
R7. **Label every cause** `Proven` (measured signal on the affected node, before the failure,
   nothing competing) or `Hypothesis (to validate)` with the one confirming measurement. A
   spike at the same time is correlation. FSx without a saturated metric is not a proven cause.
   Only a `Proven` cause may be called the root cause, in the headline or in a branch table.
   Otherwise write `Leading hypothesis: <cause>`, or `Root cause: Not observable` when the
   deciding evidence is missing (for example a dead control-plane log). Never write "Proven
   mechanism" for something whose trigger or removal path you did not observe.
   Utilization metrics from FSx (`NetworkThroughputUtilization`, `DiskIopsUtilization`, and
   similar) and `GPUPowerUtilization` are already percent from 0 to 100: a value of `0.9` is
   0.9 percent. Quote the raw value with a percent sign.
R8. **Recovery questions** always state three things: whether automatic node recovery is on
   (`NodeRecovery`), what it does (reboot or replace the node), and that the **job** resumes
   only with checkpoints plus the orchestrator's auto-resume (Slurm on HyperPod:
   `srun --auto-resume=1`).
R9. **Capacity Blocks** begin terminating instances 30 minutes before the end time (60 for
   UltraServers); blocks end at 11:30 UTC and termination starts at 11:00 UTC on the last day.
   For a planned run, write out: usable until = end time minus the lead time; run end = start
   plus run length; hours covered = usable until minus start. Give every value as a full UTC
   date and time, and check the latest safe start is not already in the past.
R10. **Rule out the frequent non-GPU causes** in `references/cluster-edge-cases.md` before
   blaming hardware: subnet IP or network interface exhaustion, ParallelCluster bootstrap
   failures and protected mode, EFA nodes in a public subnet, a Capacity Block not yet
   active, and the FSx maintenance window. HyperPod does not export system metrics to
   CloudWatch, so HyperPod GPU activity is `Not observable` there.
R11. **When the logs are dead, ask the control plane.** On a HyperPod cluster with
   `NodeProvisioningMode = Continuous`, `sagemaker.ListClusterEvents` gives you a node and
   cluster timeline that owes nothing to a log agent, so it keeps answering when a stream has
   gone silent or a node has disappeared. Filter the window with `EventTimeAfter` and
   `EventTimeBefore`, narrow with `NodeId` or `InstanceGroupName`, sort with
   `SortBy=EventTime`, and page through `NextToken`. Where a `Description` is not
   self-explanatory, `DescribeClusterEvent` has the detail. Note that the response has no
   severity or level field at all, so any grouping you apply is your own and should be
   described that way. If `NodeProvisioningMode` is anything other than `Continuous` the call
   is not supported; write `ListClusterEvents not supported` in the coverage table and carry
   on. What you must not do is report a dead log as "no events" without either trying this
   source or saying it was unavailable.

## Pick the mode

| The user asks | Mode | Steps to run |
|---------------|------|--------------|
| Something failed, hung, slowed, or lost nodes | **I: Incident** | Steps 1 to 7 |
| "Were there GPU errors?", "Can I trust the logs?" | **C: Coverage audit** | Steps 1 to 3, then 6 and 7 |
| "Is the cluster ready for a long run?", Capacity Block ending | **P: Pre-flight** | Steps 1 to 3, then 5P, 6 and 7 |

## Workflow checklist

Work through these in order and tick each one as it completes. Skip only the steps the
mode table excludes. Every step below has a matching `## Step N` section with its detail.

- [ ] Step 1: Scope the request: account, region, cluster or instance IDs, impact window
- [ ] Step 2: Build the inventory, capability profile, and one ordered timeline
- [ ] Step 3: Prove GPU log coverage per node before looking for errors
- [ ] Step 4: Classify each fault and give every node a verdict
- [ ] Step 5: Pull metrics and settle the root-cause branch
- [ ] Step 5P: Score pre-flight checks P1 to P16 (Mode P only, replaces Steps 4 and 5)
- [ ] Step 6: Write the report in the required format
- [ ] Step 7: Self-check the finished output, then present it

## Step 1: Scope

Account, region, cluster name or instance IDs, workload, impact window (default last 24 hours,
stated). Classify the symptom to pick a starting branch (Step 5), but collect evidence for all.

## Step 2: Inventory and timeline

Load [references/inventory-and-timeline.md](references/inventory-and-timeline.md) for the
inventory API calls and the eight timeline sources, and
[references/cluster-edge-cases.md](references/cluster-edge-cases.md) for the frequent non-GPU
causes to rule out under rule R10:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/inventory-and-timeline.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/cluster-edge-cases.md")
```

Build one ordered timeline for the window plus 30 minutes each side: node state, HMA
detections, Xids, AWS Health, EC2 status and scheduled events, Capacity Block and training plan
end times, and CloudTrail cluster changes (rule R3).

## Step 3: Coverage audit

Load [references/coverage-audit.md](references/coverage-audit.md) for the log-source discovery
and hourly coverage queries, and
[references/nccl-nvlink-efa.md](references/nccl-nvlink-efa.md) for NCCL transport, NVLink and
NVSwitch, and EFA signals:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/coverage-audit.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/nccl-nvlink-efa.md")
```

Produce the coverage table and the node capability and fabric table for every affected node.
Every row names the full log group name and the exact log stream name that row's verdict rests
on, so the operator can re-run the same query. Where no stream carries kernel lines, say which
groups you searched and that none did.

## Step 4: Classify faults and give node verdicts

Load [references/xid-triage.md](references/xid-triage.md) for the Xid catalog and per-code
verdicts, and [references/incident-branches.md](references/incident-branches.md) for the node
verdict evidence bar and branches A to F:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/xid-triage.md")
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/incident-branches.md")
```

## Step 5: Metrics and root-cause branch

Load [references/signals-and-thresholds.md](references/signals-and-thresholds.md) for metric
names, dimensions, and thresholds:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/signals-and-thresholds.md")
```

Pull FSx (correct dimensions per metric), GPU activity (`AWS/EC2` `GPUPowerUtilization`, unit
Percent, or `CWAgent`), and EFA counters, then evaluate branches A (hardware), B (capacity
lifecycle), C (storage), D (NCCL, NVLink/NVSwitch, EFA), E (cluster change), and F (application,
only after A to E are ruled out), as defined in `incident-branches.md`. Recommend operator
actions only.

## Step 5P: Pre-flight readiness (Mode P)

Load [references/preflight.md](references/preflight.md) for pre-flight checks P1 to P16:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/preflight.md")
```

Score checks P1 to P16. Lead with FAIL, then RISK. In Mode P this step replaces
Steps 4 and 5.

**Work the core first, then extend.** All sixteen checks together cost more tool calls than
a single answer usually has room for, and a readiness question with no verdict is a failed
answer however much evidence sits behind it (see R1). So run them in two passes.

The core, which decides whether the run can start at all:

| Check | Question it settles |
|-------|---------------------|
| P1 | Does the Capacity Block or training plan outlast the run? |
| P2 | Is there an extension, if it does not? |
| P3 | Is there a spare node to replace a failure? |
| P4 | Is `NodeRecovery` on? |
| P5 | Are deep health checks enabled? |
| P6 | Is GPU error logging arriving, so a failure during the run is visible? |

Write the readiness verdict as soon as those six are scored. P7 to P16 then refine it, and
each one you reach can only add a `RISK`, never change a `FAIL` already found in the core.
Anything you do not reach is reported `Not checked` with the call that would settle it, which
is an honest answer; silence is not. If the core itself is incomplete, say which part and
give the verdict you can support.

## Step 6: Report

Load [references/report-format.md](references/report-format.md) for the report template and its rules:

```
read_skill_resource(skill_id="aiml-gpu-training-cluster-investigation", path="references/report-format.md")
```

## Step 7: Self-check before presenting

Before showing the answer to the user, re-read your own draft and verify each of these.
Fix the draft where a check fails; do not present an output that fails one.

- [ ] Every "no errors found" statement is backed by a node whose coverage you proved in
      Step 3. If coverage was not proven, the wording is `Not observable`, not healthy.
- [ ] Every coverage row names its full log group and exact log stream (rule R5). A coverage
      claim with no named source is not auditable and must be fixed before presenting.
- [ ] Stream names appear as the service writes them, not paraphrased. Search your own draft
      for phrases like "the HMA log stream" or "the health agent log" and replace each with
      the real name, for example
      `SagemakerHealthMonitoringAgent/<instance-group>/<instance-id>`. This is the easiest
      check to skip in a short answer and the one that most often makes a finding
      unreproducible.
- [ ] Every node verdict still meets the evidence bar that justifies it, re-read from
      [references/incident-branches.md](references/incident-branches.md) Step 4b.
- [ ] The headline matches the verdicts. It does not say "hardware error" unless a verdict
      is `REPLACE` or `REBOOT` on hardware grounds (rule R6).
- [ ] Every cause carries a `Proven` or `Hypothesis (to validate)` label, and anything
      labelled `Proven` has a measured signal on the affected node before the failure
      (rule R7). Nothing unproven is called the root cause.
- [ ] Every percentage came straight from the metric without rescaling (rule R7).
- [ ] Every absent signal is reported as `Not observable` with what to collect, never as
      zero or as healthy.
- [ ] Each recommendation names an operator action, and no mutating API call was made.
- [ ] Every number in the answer can be traced to a call you actually made this run.
- [ ] Every resource you analysed appears by ID (rule R5a): the `fs-...` behind a storage
      claim, the `i-...` behind a node claim, the `cr-...` behind a capacity claim, the
      cluster name, the log group and stream. This holds for resources you cleared, not just
      the one you blamed.
- [ ] **There is an actual answer.** A verdict or root cause is written down, not just
      evidence. If you ran out of room before finishing, the draft still leads with the
      verdict you can support and marks the rest `Not checked` (rule R1).

State the outcome of this self-check in one line, naming anything you could not verify.

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
