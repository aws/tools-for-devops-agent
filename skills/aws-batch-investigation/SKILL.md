---
name: aws-batch-investigation
description: >-
  AWS Batch expertise for investigating and for explaining job, queue and compute
  environment behaviour. Use for: jobs stuck in RUNNABLE; queues that hold work and never
  launch instances; SpotMaxPriceTooLow launch failures; ordered compute environments and
  whether Batch fails over between them; jobs reporting SUCCEEDED while the work did not
  complete (OutOfMemoryError in container.reason, or "Job attempt duration exceeded
  timeout" in statusReason); which Batch API or IAM permission is needed to detect a job
  condition, including whether ListJobs or DescribeJobs carries a given field; how
  retryStrategy attempts and evaluateOnExit interact to set the effective retry count; how
  fair-share weightFactor affects allocation and why a single snapshot misleads; minvCpus
  holding idle instances. Also use for any question about interpreting a Batch job status,
  field, API choice, permission or compute environment setting, and when a Batch alarm
  fires.
metadata:
  author: AWSGolden
  version: "1.0.0"
  summary: "Investigates AWS Batch jobs, queues and compute environments, including jobs that report SUCCEEDED but did not finish."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_RCA"
  aws-devops-agent-skills.aws-services: "AWS Batch, Amazon EC2, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "High Performance Computing, Observability, Operations"
---

# AWS Batch investigation

AWS Batch reports job outcomes across several fields, and they can disagree. The single
most common mistake when investigating Batch is trusting `status`.

## The invariant

**A Batch job status of `SUCCEEDED` does not mean the work completed.**

Batch can return `status: SUCCEEDED` with `exitCode: 0` for a job it terminated itself on
an out-of-memory condition or on its own attempt timeout. It records what happened in
`container.reason` or `statusReason` while leaving `status` successful.

Before reporting that Batch jobs are healthy, or that a failure is unrelated to job
outcomes, read `statusReason` **and** `container.reason` for the jobs in scope. Reading
only one of the two will miss a whole failure mode: `container.reason` is null for silent
timeouts, and `statusReason` does not carry the OOM text.

## Reference material

Load a reference only when its situation applies — each is self-contained.

- [Silent failure modes](references/silent-failure-modes.md) — load when any job reports
  `SUCCEEDED`, or when you need the exact field values and reproduction steps for the
  three observed modes.
- [Compute environments, capacity and retries](references/capacity-and-compute-environments.md)
  — load when a queue holds work and nothing runs, when `maxvCpus` or `minvCpus` is in
  question, when a `retryStrategy` looks wrong, or for the fair-share weighting detail.
- [Choosing a detection signal](references/detection-signals.md) — load when asked to
  recommend or tune Batch monitoring, not during an active incident.
- [IAM policy notes](references/iam-policy-notes.md) — load when a call is denied and you
  need to say which permission is missing and why. The policy itself is
  [iam-policy.json](references/iam-policy.json).

## Checklist: establish what the queue is doing

Work top to bottom. Complete each item before the next.

- [ ] Call `batch:DescribeJobQueues` for the queue in scope and record `state` and
      `status`. Do **not** stop here — `ENABLED` and `VALID` say nothing about whether the
      queue can acquire capacity.
- [ ] Call `batch:ListJobs` once per relevant status and record the counts.
- [ ] Branch on the counts:
      `RUNNABLE` > 0 and `RUNNING` == 0 → run the *queue holds work* checklist.
      `RUNNING` > 0 → run the *outcomes* checklist.
      both 0 and the complaint is cost → run the *idle capacity* checklist.

## Checklist: queue holds work but nothing runs

Stop at the first item that explains the stall.

- [ ] Call `batch:DescribeComputeEnvironments` for every compute environment on the queue.
      Record `order`, `state`, `status`, `minvCpus`, `desiredvCpus`, `maxvCpus`, and
      `bidPercentage` for Spot.
- [ ] Call `autoscaling:DescribeScalingActivities` for the **order-1** compute
      environment's Auto Scaling group. This is the step most investigations skip and it is
      usually where the answer is. Match what you find:

      | Observation | Conclusion |
      |---|---|
      | `Failed` activities with `SpotMaxPriceTooLow` | Bid below market. Stalls indefinitely rather than erroring. |
      | `Failed` activities with an insufficient-capacity reason | Instance type unavailable in the configured AZs. |
      | `Successful` activities, instances still registering | Cold start, not a stall. Report elapsed time and wait. |
      | No activities at all and `desiredvCpus` 0 | Batch never asked here. Continue to the next item. |

- [ ] Read `MaxSize` on the Auto Scaling groups of the order-2 and later compute
      environments. `MaxSize` 0 with no activity history means **Batch never requested
      capacity there**. Batch does not fail over to a later compute environment when an
      earlier one cannot launch — ordered compute environments are an overflow mechanism,
      not a fault-tolerance mechanism. Report that the order-1 compute environment cannot
      launch and that this blocks the queue by design. Do not report that "Batch failed to
      fail over".
- [ ] Confirm you have not concluded a capacity ceiling from `maxvCpus`. It is a target,
      not a hard boundary; running vCPUs have been observed above it.

## Checklist: jobs run, but outcomes are in question

- [ ] Call `batch:ListJobs` for `SUCCEEDED` jobs in the window and inspect each summary
      object for `container.reason` containing `OutOfMemoryError` (silent OOM) and
      `statusReason` containing `Job attempt duration exceeded timeout` (silent timeout).
      Both fields are on the `ListJobs` summary, so this needs no per-job `DescribeJobs`
      call and works with `batch:ListJobs` alone.
- [ ] If either appears, state explicitly that the work did not complete despite the
      reported success, and name which mode — the remediation differs (memory sizing
      versus timeout sizing).
- [ ] For a genuinely failed job, call `batch:DescribeJobs` and check the resolved
      container `command` and `image`; a failure can come from a bad command or image
      rather than the workload.
- [ ] Compare `attemptDurationSeconds` against actual runtime (`stoppedAt - startedAt`). A
      population of jobs all stopping just under the same duration is a timeout cap, not a
      coincidence.
- [ ] If `retryStrategy.attempts` is greater than 1 but the job failed once and stopped,
      read `evaluateOnExit`. A rule set matching only host-level failures
      (`"onStatusReason": "Host EC2*"`) will not retry an application error, so the job
      exits permanently after one attempt. Report the **effective** retry behaviour, not
      the declared `attempts`.
- [ ] Before attributing two failures to one cause, confirm a shared mechanism. Batch job
      failures on a queue are independent by default — each job has its own image, command
      and exit path. An image-pull failure and a non-zero application exit minutes apart on
      the same queue are two unrelated causes.

## Checklist: fair-share queues

- [ ] Confirm the queue has a scheduling policy before reasoning about weighting.
- [ ] Compare **cumulative share-minutes** across the whole contention window. Do not judge
      allocation from a single sample: `weightFactor` controls which share runs first and
      the instantaneous split under contention, not total allocation when every share
      submits comparable demand and all of it eventually runs. Over a full run,
      share-minutes tend to equalise, so one snapshot can show the opposite of the trend.

## Checklist: idle capacity and cost

- [ ] Check every compute environment for `minvCpus` > 0. Such an environment holds
      registered instances with no work at all, billed continuously, producing no
      job-level signal because there are no jobs.
- [ ] For any with no steady job arrival rate, report the held capacity and its duration.
      Count hours across the succession of instances — Spot reclamation can replace the
      held instance repeatedly, so cumulative billed hours must not be attributed to a
      single instance ID.

## Checklist: if asked to recommend monitoring

Applies to proactive review, not an active incident.

- [ ] Recommend an **unfulfilled-vCPU alarm** as the primary stall signal over a
      stuck-`RUNNABLE` alarm. In measurement it fired sooner *and* identified the cause,
      where a stuck-`RUNNABLE` alarm reports only the symptom.
- [ ] State the cost of widening a stuck-`RUNNABLE` alarm to survive cold starts. It buys
      fewer false positives with real detection latency. Give both numbers.
- [ ] Note that a polling interval shorter than a few minutes cannot distinguish a
      scale-from-zero from a stall, so a fast polled signal is advisory, not an incident.

## Checklist: verify before reporting

Do this before presenting any conclusion. It is the step that keeps the report honest.

- [ ] For every mechanism you name, confirm you can cite the specific API field or ASG
      activity it rests on. If you cannot, downgrade it from a conclusion to a hypothesis.
- [ ] For every failure mode you name, confirm the actual field value you observed matches
      that mode — not that it merely sounds consistent.
- [ ] Re-read the *Do not* list below and confirm none of your conclusions violate it.
- [ ] List explicitly what you could not determine, and which permission or data source
      would settle it. An unstated gap reads as a finding.

## Report format

State, in this order:

1. **What the queue was doing** — the `RUNNABLE`/`RUNNING` counts and the window.
2. **The mechanism**, named specifically. "Order-1 Spot compute environment cannot launch:
   ASG reports SpotMaxPriceTooLow, bid X against market Y" is a mechanism. "Capacity
   issue" is not.
3. **Whether any job reported success without completing**, and which mode.
4. **The evidence** — the API field or ASG activity each conclusion rests on.
5. **What you could not determine**, and what would settle it.

## Do not

- Do not report Batch jobs as healthy on the basis of `status` alone.
- Do not infer `status` from `container.reason`, or `container.reason` from `status`. The
  same OOM condition appears with both `SUCCEEDED` and `FAILED`.
- Do not describe ordered compute environments as providing failover.
- Do not treat `ENABLED` / `VALID` as evidence that a compute environment can acquire
  capacity.
- Do not conclude a capacity ceiling from `maxvCpus`.
- Do not report declared `retryStrategy.attempts` as the effective retry count without
  reading `evaluateOnExit`.
- Do not merge independent job failures into one cause without a shared mechanism.
- Do not judge fair-share behaviour from one snapshot.
- Do not describe a queue scaling from zero as stalled. Check ASG activity first.

## Permissions

Minimum for the silent-failure checks: `batch:ListJobs`, `batch:DescribeJobQueues`.

Additionally for the capacity and job-configuration checklists:
`batch:DescribeComputeEnvironments`, `batch:DescribeJobs`,
`batch:DescribeSchedulingPolicies`, `autoscaling:DescribeScalingActivities`,
`autoscaling:DescribeAutoScalingGroups`.

`batch:DescribeJobs` is not covered by `batch:List*` and is commonly absent from read-only
monitoring roles. Without it the command, timeout and `retryStrategy` checks are
unavailable — report that as a gap rather than guessing. See
[IAM policy notes](references/iam-policy-notes.md).
