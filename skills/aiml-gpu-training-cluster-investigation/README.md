# AI/ML GPU Cluster Evidence, Readiness, and Fault Verdicts Skill

A skill for AWS DevOps Agent for GPU training and inference clusters on Amazon SageMaker
HyperPod (Slurm and EKS orchestrators), AWS ParallelCluster, and self-managed EC2 or EKS GPU
fleets. Strictly **read-only**.

> **Sample code notice:** This skill is sample code and is not intended for production
> use without additional review and testing. Validate it in a non-production
> environment first.

## Purpose

DevOps Agent already finds the obvious signals in a GPU incident. Live testing against
HyperPod Slurm, HyperPod EKS, and ParallelCluster clusters showed three places where it
goes wrong without help, and this skill targets exactly those:

| Gap observed without the skill | What the skill adds |
|--------------------------------|---------------------|
| Reported "full log coverage" for a kernel log stream that was silent for 47 of 49 hours, so "no Xid errors" meant nothing | **Coverage audit**: proves hour by hour, per node and per source, whether Xid evidence was arriving |
| Headlined "GPU hardware error, confirmed" for an Xid 31 caused by an application bug | **Node verdict** (`REPLACE`, `REBOOT`, `LEAVE ALONE`, `MONITOR`, `NOT OBSERVABLE`) against an explicit evidence bar |
| Stated that storage caused slowness when FSx was not saturated | **Cause labels**: every cause is `Proven` or `Hypothesis (to validate)` with the confirming measurement |

It also adds a **pre-flight mode** that catches predictable failures before a long run:
Capacity Block or training plan end time versus run length, extension offerings, spare
capacity to replace a failed node, `NodeRecovery`, deep health checks, the EFA security
group, log coverage, idle reserved GPUs, and an alarm on the expiration warning.

## Key Capabilities

- **HyperPod-aware inventory**: node status, `CurrentCount` vs `TargetCount`,
  `NodeRecovery` mode, on-start deep health checks, AMI drift
- **Xid discovery on any orchestrator**: reads HyperPod health-monitoring agent
  detections, ParallelCluster `system-messages`/`syslog` streams, and customer-shipped
  kernel log groups (found by matching instance IDs in stream names), then classifies
  each Xid using the NVIDIA catalog
- **Log coverage proof**: before reporting "no Xids", confirms kernel lines are actually
  arriving from each affected node, so an unshipped log is reported as *Not observable*
  rather than as a healthy GPU
- **Capacity Block lifecycle detection**: matches mass terminations to the documented
  30/60-minute pre-expiry termination window
- **FSx for Lustre bottleneck classification**: throughput-bound vs metadata-bound vs
  imbalanced OSTs, using the correct per-metric dimensions
- **EFA preconditions**: self-referencing security group check, deep health check
  (`InstanceStress`, `InstanceConnectivity`) results
- **Change correlation**: CloudTrail `UpdateCluster`, `UpdateClusterSoftware`,
  `Batch*ClusterNodes`, `UpdateFileSystem`
- **Evidence discipline**: every branch is marked Root cause, Ruled out, Not assessed, or
  UNVERIFIED. An empty query is never reported as "healthy" without checking scope,
  window, and pagination.

## Prerequisites

### IAM Permissions

**No additional IAM permissions are required.** Every call this skill makes is covered by
the [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
managed policy:

- `sagemaker:Describe*`, `sagemaker:List*` (HyperPod cluster and node state)
- `ec2:Describe*` (instances, instance status, capacity reservations, security groups)
- `fsx:Describe*`
- `cloudwatch:GetMetricData`, `cloudwatch:List*`
- `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`, `logs:Describe*`
- `health:Describe*`
- `cloudtrail:LookupEvents`
- `eks:Describe*`, `eks:List*` (EKS-orchestrated clusters)

There is no CloudFormation template to deploy for this skill.

### AWS Resources

- A GPU cluster to investigate: a HyperPod cluster name, or EC2 instance IDs or tags.
- An impact window (when the job last made progress and when it failed). Without one
  the skill assumes the last 24 hours and says so.
- **Optional:** CloudWatch agent with the NVIDIA plugin publishing
  `nvidia_smi_utilization_gpu` to `CWAgent`, for GPU utilization signals.
- **Optional:** AWS Health requires a Business, Enterprise On-Ramp, or Enterprise
  Support plan for API access.

## Limitations

- **In-guest logs are only as visible as the customer's log shipping.** EC2 cannot see
  Xids from outside the instance. NCCL debug output, kernel messages, and application
  stdout reach the agent only if they are shipped to CloudWatch Logs (HyperPod HMA and
  ParallelCluster CloudWatch logging do this for kernel-level messages). When they are
  not shipped, the skill reports them as not observable and tells the operator what to
  collect locally.
- **No remediation is executed.** Node replacement, reboot, and deep health checks are
  recommended as operator actions only.
- **Xid classification follows the NVIDIA catalog** as of this version. Unknown codes are
  reported raw and marked UNVERIFIED.
- **Capacity availability is not assessed.** The skill can see that a Capacity Block
  expired or a reservation is full. It cannot tell whether more capacity is available.
- **CloudTrail delivery can lag** by up to about 15 minutes, and `LookupEvents` may need
  operator approval in some runtimes. The skill continues without it and names the gap.
- **Thresholds are heuristics.** They flag signals worth reporting. They are not service
  limits.

## Agent Types

- **Incident RCA**: primary use. Triggered by an alarm or incident on a training cluster.
- **Chat tasks**: on-demand ("why did my HyperPod job fail last night?").

## Uploading to AWS DevOps Agent

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html)
in your Agent Space, go to Settings → Add Skill → Import from repository and point to
the `skills/aiml-gpu-training-cluster-investigation` directory.

**Option B: Upload as a zip file**

Zip the skill's **contents** so that `SKILL.md` sits at the root of the archive:

```bash
cd skills/aiml-gpu-training-cluster-investigation
zip -rD ../../aiml-gpu-training-cluster-investigation.zip . \
  -i '*.md' '*.json' '*.yaml' '*.yml' \
  -x './README.md' './CHANGELOG.md' './.skilleval.yaml' './evals/*'
unzip -l ../../aiml-gpu-training-cluster-investigation.zip
```

Expected layout:

```text
aiml-gpu-training-cluster-investigation.zip
├── SKILL.md
└── references/
    ├── report-format.md
    ├── signals-and-thresholds.md
    └── xid-triage.md
```

> **Do not zip the parent directory.** A `skill-name/` prefix in the archive breaks
> `read_skill_resource` path lookups, and the skill silently runs without its references.

After uploading or replacing the skill, wait up to 15 minutes before testing, and confirm the new version by asking the agent to quote a line that only exists in it. In live testing the Agent Space kept serving the previous version for 5 to 12 minutes after an upload, and reads of its reference files could fail during that window.

Upload the zip in the Operator Web App under **Skills**, and select the **Incident RCA**
and **On-demand** agent types. See
[Creating and uploading skills](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html).

## How to Use This Skill

### Incident RCA

- "HyperPod cluster `llm-pretrain` in us-west-2: the training job crashed at 03:10 UTC
  and two nodes are in Failure. Find the root cause."
- "Our 64-node p5 job lost 32 nodes at 11:00 UTC. What happened?"
- "ParallelCluster `training-b200` in us-west-2: a job on the `gpu` queue died at
  14:20 UTC. Were there any GPU Xid errors on the compute nodes?"

### Pre-flight (Chat tasks)

- "Is HyperPod cluster `llm-pretrain` ready for a 5-day run starting tomorrow?"
- "Our Capacity Block ends Friday. What do we need to do before then?"
- "Are we actually using the B200 GPUs we reserved?"

### Chat tasks

- "Training throughput on cluster `ft-cluster` dropped by half since yesterday. Is it
  storage, network, or the GPUs?"
- "Checkpoint saves to FSx are taking 20 minutes instead of 2. Why?"
- "A HyperPod node has been in DeepHealthCheckInProgress for 3 hours. Is it stuck?"
- "Auto-resume isn't replacing the failed node on my HyperPod Slurm cluster. Why?"

## Validation

Tested against live clusters in a non-production account: SageMaker HyperPod Slurm
(ml.g5), SageMaker HyperPod EKS (ml.g5.4xlarge), and AWS ParallelCluster 3.16 with two
p6-b200.48xlarge nodes in a Capacity Block, with two FSx for Lustre file systems. Faults
were injected on test resources only: an application-caused Xid 31 on both HyperPod
orchestrators, an operator node replacement, and a 10-minute FSx metadata load.

Each scenario was asked of DevOps Agent with and without the skill, and answers were
scored blind against measured ground truth (10 points per scenario):

| Round | Runs per scenario | With skill | Without skill |
|-------|-------------------|------------|---------------|
| 2 | 1 | 89 / 100 | 75 / 100 |
| 3 | 2 | 86 / 100 | 74 / 100 |
| 4 | 3 | 91.7 / 100 | 73.3 / 100 |
| 5 | 2 | 87.0 / 100 | 74.5 / 100 |
| 6 (final) | 1 to 3 | 90.0 / 100 | 67.3 / 100 |

Round 6 used corrected ground truth for the FSx bottleneck scenario (the real 5-minute peak was 124.7%, not the 72% an earlier baseline answer reported), which lowered the baseline. A further scenario with no baseline (compute nodes that disappeared with no terminate call and a dead head-node log) scored 7.3 / 10 with the skill: every run kept the unobservable cause labelled a hypothesis.

Largest gains: log coverage gaps (2 to 9), application Xids headlined as hardware
(4.7 to 10), Capacity Block timing (7 to 9.7), pre-flight readiness (6.3 to 8.3), and
unproven storage causes (4 to 8.3). Each round's regressions fed the next revision.

## References

- [HyperPod health monitoring system](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-eks-resiliency-health-monitoring-agent.html)
- [HyperPod deep health checks](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-resiliency-slurm-deep-health-checks.html)
- [Manually replace or reboot a HyperPod node](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-hyperpod-resiliency-slurm-replace-faulty-instance.html)
- [How Capacity Blocks work](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-how.html)
- [FSx for Lustre metrics and dimensions](https://docs.aws.amazon.com/fsx/latest/LustreGuide/fs-metrics.html)
- [EFA and NCCL getting started](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa-start-nccl.html)
- [NVIDIA Xid catalog](https://docs.nvidia.com/deploy/xid-errors/analyzing-xid-catalog.html)
