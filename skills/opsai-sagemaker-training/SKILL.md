---
name: opsai-sagemaker-training
description: Diagnose an Amazon SageMaker training or customization job, including Nova and JumpStart fine-tuning,
  and review Model Registry governance of the models it produces. Use this skill when a training job is denied
  access to S3, a KMS key or iam:PassRole, fails with InsufficientCapacityError, ResourceLimitExceeded or out
  of memory, goes to Failed with no logs, restarts after a spot interruption or skips its checkpoints, stalls as a
  multi-node run, times out in VPC mode, finds no input files, hides loss metrics or bills GPU time for a run with no model, and when a pipeline registers no model package version, deploys are not gated on approval
  status, a served model has no approved package, a package group must be shared across accounts, a package is
  rejected on an instance type, lineage is missing, or managed MLflow calls fail. Not for evaluation jobs of a fine-tuned model (Nova eval recipe, LLM-as-judge), even when one fails. Findings carry LLM-SM-TRAIN and LLM-SM-REG check-ids and AWS-doc citations, read-only.
metadata:
  author: jmadhuki
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Diagnoses Amazon SageMaker training and fine-tuning jobs that fail, hang or waste GPU time, and reviews Model Registry registration, approval and lineage."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon S3, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Governance"
---

# OpsAI — SageMaker training, customization and Model Registry

You review two connected areas of a SageMaker GenAI workload. **Training / customization**: Nova
fine-tuning/SFT/LoRA recipes and JumpStart fine-tuning jobs that fail, stall, or will not start; you say
exactly which catalog check fired and what the operator should run to fix it, and you tell a true failure apart
from a job that is merely waiting on capacity. **Model Registry**: the governance of the artifact that training
produces; is it registered, approved, lineage-tracked, and bounded by a least-privilege package-group policy.
Both are **read-only failure and posture reviews**.

This skill works on its own: everything it needs is in its `references/` and `assets/` files. Read-only APIs only.

Every finding is grounded in the **LLM-SM** check family in
[checks-sagemaker-training.md](references/checks-sagemaker-training.md): the `LLM-SM-TRAIN-*` sub-family for
training / customization and the `LLM-SM-REG-*` sub-family for model registry / lineage; load it before assigning
any check-id or severity. Each finding carries a stable `check-id`, a severity, and an AWS-doc citation. You never
invent a threshold: a tuning judgment with no AWS-published number is marked `workload-specific` and reported as
`INFO`, while a binary failed/absent state keeps its catalog severity. This skill never mutates a resource.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## When to Use

Activate this skill when the user:

**Training / customization**

- Says a **Nova SFT+LoRA (or JumpStart) training/customization job failed or is stuck** and wants to know why.
- Reports **corrupt or malformed training data**: a Bedrock Converse JSONL that does not parse, a wrong schema,
  or the invalid-sample tolerance exceeded.
- Reports a job that **will not start**: `InsufficientCapacityError`, a training instance quota of zero, or a
  job **stuck Pending on capacity**.
- Reports a **recipe / hyperparameter validation error**, an **IAM/S3 access** failure on the training or recipe
  data, or an **empty / misconfigured data channel**.
- Asks whether a **completed** job actually produced a **checkpoint**, or about **GPU cost billed for a failed or
  empty run**.
- Wants a **health report** for one or more training/customization jobs.

**Model Registry**

- Reports a **customized artifact that was never registered**, so it has no governed version or lineage
  (REG-001).
- Reports a **model package deployed or staged for deploy while its `ModelApprovalStatus` is
  `PendingManualApproval` or `Rejected`** (REG-002).
- Reports a **registered package with no lineage** back to its training job or dataset (REG-003).
- Reports a **model package group with a broad or absent resource policy or an un-CMK'd artifact** (REG-004).
- Reports a **break-fix symptom**: a pipeline that finishes with no new version, an endpoint config from a
  package rejected on its instance type, a group that cannot be shared across accounts, managed MLflow calls that
  fail, or artifacts missing from the console.

## The LLM-SM check family

Grounded in [checks-sagemaker-training.md](references/checks-sagemaker-training.md); load it when a symptom
matches a row below. Match the symptom, confirm with the collection calls, then report with the check-id and
severity from the catalog. The full six-column detection rules, remediations, and citations live in the
reference; the table below is a what-it-catches index.

| check-id | area | severity | what it catches |
|---|---|---|---|
| LLM-SM-TRAIN-001 | Training | HIGH | Job `Failed` on malformed/corrupt training data (JSONL parse, missing keys, invalid-sample tolerance exceeded). |
| LLM-SM-TRAIN-002 | Training | HIGH | `InsufficientCapacityError`: AWS-side GPU shortfall (retry/alternate, not a quota fix). |
| LLM-SM-TRAIN-003 | Training | HIGH | Training instance-type service quota = 0: customer quota (request an increase). |
| LLM-SM-TRAIN-004 | Training | HIGH | Recipe/hyperparameter validation failure (null or out-of-range `HyperParameters`). |
| LLM-SM-TRAIN-005 | Training | HIGH | Execution-role `AccessDenied` on the training/recipe/output S3 (or KMS). |
| LLM-SM-TRAIN-006 | Training | HIGH | Empty or wrong-URI input data channel. |
| LLM-SM-TRAIN-007 | Training | MEDIUM | Job `InProgress`/`Pending` on capacity, **not** Failed; a false-positive trap. |
| LLM-SM-TRAIN-008 | Training | HIGH | Job `Completed` but no checkpoint at the output path: billed, unusable. |
| LLM-SM-REG-001 | Model Registry | MEDIUM | Customized artifact never registered: no governed version/lineage. |
| LLM-SM-REG-002 | Model Registry | HIGH | Deployed/staged package `PendingManualApproval` or `Rejected`. |
| LLM-SM-REG-003 | Model Registry | LOW | Registered package with no lineage to its training job/dataset. |
| LLM-SM-REG-004 | Model Registry | MEDIUM | Model package group with a broad/absent resource policy or un-CMK'd artifact. |

Load [checks-sagemaker-training.md](references/checks-sagemaker-training.md) before writing any finding: it holds
the full detection rules, remediations, and citations.

## Router

How to read each API and signal is in [collection-reference.md](references/collection-reference.md). Load it with
any row.

| Operator says | Area | First read | Load |
|---|---|---|---|
| My training job failed, the data looks corrupt or won't parse | Training | `DescribeTrainingJob` `FailureReason`, then the JSONL sample | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-001), [api-quirks.md](references/api-quirks.md) |
| The job won't start, there's no GPU capacity | Training | `DescribeTrainingJob` `FailureReason` and `SecondaryStatus` | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-002, 003), [api-quirks.md](references/api-quirks.md) |
| It says the quota is exceeded, do I need a quota increase | Training | `service-quotas get-service-quota` for the training instance type | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-003) |
| The recipe or hyperparameters were rejected | Training | `DescribeTrainingJob` `HyperParameters` and the S3 recipe object | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-004), [api-quirks.md](references/api-quirks.md) |
| The job got access denied on S3 or KMS | Training | `DescribeTrainingJob` `RoleArn`, then the role's policies evaluated statically for the data and output prefixes (`iam:SimulatePrincipalPolicy` is never called) | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-005) |
| The job ran but read no data, the channel is empty | Training | `InputDataConfig` S3 URIs, then `ListObjectsV2` on each prefix | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-006) |
| The job has been Pending for hours, is it broken | Training | `TrainingJobStatus` and `SecondaryStatus` | [api-quirks.md](references/api-quirks.md) §1 (LLM-SM-TRAIN-007) |
| It says Completed but I can't find the model | Training | `ModelArtifacts.S3ModelArtifacts`, then `ListObjectsV2` on that prefix | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-008), [metrics-and-logs.md](references/metrics-and-logs.md) |
| Why was I billed for a run that gave nothing | Training | `BillableTimeInSeconds`, status and artifact check | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-TRAIN-007, 008; a capacity failure, LLM-SM-TRAIN-002, is not billed) |
| Our fine-tuned model isn't in the registry, it was never registered | Model Registry | `ListModelPackages` for the artifact's S3 location | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-REG-001) |
| The model in production isn't approved, it's pending or rejected | Model Registry | `DescribeEndpoint` deployed model, then `DescribeModelPackage` `ModelApprovalStatus` | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-REG-002), [api-quirks.md](references/api-quirks.md) §7 |
| Is the registry group approved, which version is live | Model Registry | `ListModelPackages` versions vs the deployed or staged version | [api-quirks.md](references/api-quirks.md) §7 (LLM-SM-REG-002) |
| Where did this model come from, can't trace it to training | Model Registry | `DescribeModelPackage`, then the lineage association to the training job | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-REG-003) |
| Who can access our model package group, is the artifact encrypted | Model Registry | The artifact S3 encryption; the group policy is reported as not evaluated (`sagemaker:GetModelPackageGroupPolicy` is not called: it is not in the managed policy) | [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (LLM-SM-REG-004) |
| No metrics for the registry, so is it healthy | Model Registry | Registry describe and list calls, not CloudWatch | [metrics-and-logs.md](references/metrics-and-logs.md), [api-quirks.md](references/api-quirks.md) §6 |

## Break-fix first

When the user states a specific error or symptom, answer that error before any health or governance review.
Training symptoms: an access denied, a PassRole or KMS error, a capacity or quota error, out of memory, no logs,
a spot restart, a checkpoint that does not resume, a hang, missing metrics. Model Registry symptoms: no version
after a pipeline run, an unapproved deploy, a sharing failure, an instance-type rejection, missing lineage or
console entries, failing MLflow calls.

- Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom (training
  §1–§7, Model Registry §8–§14); match it to a section, check the cited AWS page, and give the cause, how to
  confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the account,
  include what you found and what you could not read.
- A known cause tied to an `LLM-SM-TRAIN-*` or `LLM-SM-REG-*` id is a finding with the catalog severity. A cause
  with no id is guidance with its AWS citation; never invent an id for it.
- Run the Review Procedure below only when asked for a review or when there are jobs, packages or groups to
  inspect.

## Review Procedure

Classify **before** prescribing anything. Run the steps in order and track progress against this checklist.
Every step is **best-effort**: if an API is denied or a feature is unsupported in the region, record that signal
as **unavailable** and continue.

- [ ] Step 1: Identify the area: a training/customization job, or a model package / package group.
- [ ] Step 2: Describe the training job (`TrainingJobStatus`, `SecondaryStatus`, `FailureReason`).
- [ ] Step 3: Classify Pending versus Failed.
- [ ] Step 4: Bucket the `FailureReason` into exactly one cause.
- [ ] Step 5: Confirm the artifact and note billed GPU cost.
- [ ] Step 6: Review Model Registry governance (LLM-SM-REG-001..004).
- [ ] Step 7: Assemble findings and the report; disclose scope.

### Step 1 — Identify the area

**Training / customization.** A job that failed, stalled, will not start, or completed without a usable model:
run Steps 2–5, then Step 7.

**Model Registry.** A package or group whose registration, approval, lineage or boundary is in question: go to
Step 6, then Step 7.

**Both.** A fine-tuned model that is about to ship (or is already served): run the training steps first, then
Step 6, so the registry review starts from a confirmed artifact.

### Step 2 — Describe the training job

**Training / customization.** `ListTrainingJobs` / `DescribeTrainingJob` for `TrainingJobStatus`,
`SecondaryStatus`, and `FailureReason`. A Nova customization job runs as a recipe-driven training job; describe it
by its training-job name.

### Step 3 — Classify Pending versus Failed

**Training / customization.** If the job is `InProgress` with `SecondaryStatus` `Starting`/`Pending` waiting on
capacity, it is **NOT** Failed ([api-quirks.md](references/api-quirks.md) §1, LLM-SM-TRAIN-007). Report the true
status and **stop here**; prescribe no config change.

### Step 4 — Bucket the FailureReason into one cause

**Training / customization.** If `Failed`, bucket the `FailureReason` into exactly one cause and cite the check:
malformed data (LLM-SM-TRAIN-001) / AWS-side capacity (LLM-SM-TRAIN-002) / customer quota = 0, cross-checking
`service-quotas get-service-quota` (LLM-SM-TRAIN-003) / recipe-hyperparameter (LLM-SM-TRAIN-004) / IAM-S3
(LLM-SM-TRAIN-005) / empty-or-wrong channel URI (LLM-SM-TRAIN-006). The capacity-vs-quota split is opposite
remediations: read **both** the `FailureReason` and the quota value ([api-quirks.md](references/api-quirks.md)
§2).

### Step 5 — Confirm the artifact and note billed GPU cost

**Training / customization.** If `Completed`, confirm an artifact exists: `s3:ListBucket` (the ListObjectsV2 call; contents not read) on
`ModelArtifacts.S3ModelArtifacts` / the recipe output path. A succeeded job with no checkpoint is
LLM-SM-TRAIN-008. Note that `allow_percentage_invalid_samples` can let a job `Complete` while silently dropping
corrupt records ([api-quirks.md](references/api-quirks.md) §3); a "success" is not proof all data was used.

**Cost.** Note billed GPU cost (`BillableTimeInSeconds`) for any failed, empty, or stalled run that
started on instances (LLM-SM-TRAIN-007/008). Billing runs from `TrainingStartTime` to `TrainingEndTime`,
so a job that never started, such as a capacity failure (LLM-SM-TRAIN-002), was not billed.

### Step 6 — Review Model Registry governance

**Model Registry.** `ListModelPackages` / `DescribeModelPackage` for the customized artifact. Flag an artifact
never registered (LLM-SM-REG-001), a deployed/staged package with `ModelApprovalStatus`
`PendingManualApproval`/`Rejected` (LLM-SM-REG-002), a package with no lineage to its training job/dataset
(LLM-SM-REG-003), and a group with a broad/absent resource policy or an un-CMK'd artifact (LLM-SM-REG-004).

An `Approved` package in the group is not proof that the deployed version is approved: resolve which version is
deployed or staged before clearing a group ([api-quirks.md](references/api-quirks.md) §7). A **deployed
endpoint** lacking registry lineage is a finding of the SageMaker endpoint area, not a REG-* finding; REG-*
governs the registered package itself.

### Step 7 — Assemble findings and the report

Produce the result in one turn; disclose any job, package, group, region, S3 prefix or check you could not read.
When a full report is requested, load the template for the area:

- **Training / customization.** [training-job-health-report-template.md](assets/training-job-health-report-template.md)
  (load when a full training report is requested).
- **Model Registry.** [model-registry-health-report-template.md](assets/model-registry-health-report-template.md)
  (load when a full registry governance report is requested).
- **Both.** Use both templates, training first.

## Before You Present — Validate Your Own Output

A wrong or unsupported finding is worse than a slow one. Before presenting, re-check your output against this
list. Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **`check-id`** from
  [checks-sagemaker-training.md](references/checks-sagemaker-training.md) (load it if any id is unconfirmed), and
  that id corresponds to what was actually observed, not a near-miss id reused for convenience.
- [ ] Every cited value was **actually observed, not inferred**. A training job that is `InProgress`/`Pending` on
  capacity is **never reported as a failure** (load [api-quirks.md](references/api-quirks.md) §1 if the job is
  not `Failed`, LLM-SM-TRAIN-007). Read the actual `ModelApprovalStatus`, not an assumption, and confirm which
  version is deployed before clearing a group as approved ([api-quirks.md](references/api-quirks.md) §7).
- [ ] A **training-failure classification** names exactly one bucket with its `LLM-SM-TRAIN-*` id, and a
  capacity-vs-quota call reads **both** the `FailureReason` and the `service-quotas` value (§2).
- [ ] No severity was invented: each matches the catalog; a threshold AWS does not publish is marked
  `workload-specific` / `INFO`, while a binary failed/absent state keeps its catalog severity.
- [ ] **No mutating API was called or implied as done.** Remediations are phrased as recommendations with the
  exact command for the operator to run.
- [ ] No **raw 12-digit AWS account ID** and no **secret value** (including raw training-data content) appear
  anywhere. REG findings quote principals/ARNs with the account segment masked; env vars are referenced by key
  name only.
- [ ] The jobs, packages, groups, regions, S3 prefixes and checks **not** covered are disclosed, with the reason.
- [ ] When a full report is requested, the output follows the area's template from Step 7.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a training mutation (`CreateTrainingJob`, `StopTrainingJob`), a registry mutation
   (`CreateModelPackage`, `UpdateModelPackage`), or any other mutating API. Recommend the fix and give the exact
   CLI/IaC command; let the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under review`. If an ARN
   must be quoted as evidence, mask the account segment (`arn:aws:sagemaker:us-east-1:<account>:training-job/...`,
   `arn:aws:sagemaker:us-east-1:<account>:model-package/...`). The same applies to anything credential-shaped.
3. **Never disclose secret material.** Report environment variables, keys, tokens, connection strings, and raw
   training-data content by **key name / reference only**; never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it (the actual `FailureReason`,
   the actual `ModelApprovalStatus`, the actual resource policy). Distinguish a true `Failed` from a
   Pending-on-capacity job (load [api-quirks.md](references/api-quirks.md) §1 whenever a job is not `Failed`).
5. **A check-id on every finding.** Each finding references an LLM-SM `check-id` and carries that check's
   severity and AWS-doc citation. No freelance findings. A documented cause from known-causes.md that has no
   check-id is labelled guidance with its citation, not a finding.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`, marked
   `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which jobs, packages, groups, regions, or checks you
   did not cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers

- "The job is `InProgress` with `Pending`, so it is failing." A job waiting on GPU capacity is control-plane-healthy, not `Failed`. Report the true status and prescribe no config change (`api-quirks.md` §1, LLM-SM-TRAIN-007).
- "It won't get instances, so request a quota increase." `InsufficientCapacityError` is an AWS-side shortfall and the fix is retry or an alternate instance type or region; a quota of zero is a customer limit and needs `request-service-quota-increase`. Read both the `FailureReason` and `service-quotas get-service-quota` before choosing (`api-quirks.md` §2, LLM-SM-TRAIN-002, 003).
- "The job `Completed`, so all the training data was used." With an invalid-sample tolerance such as `allow_percentage_invalid_samples`, corrupt records are silently dropped and the job still completes. Check the drop count in the log, not just the status (`api-quirks.md` §3, LLM-SM-TRAIN-001).
- "A required hyperparameter was left out, so it falls back to a default." Nova rejects a null or omitted required `HyperParameters` value at create time. It is a hard validation failure (`api-quirks.md` §4, LLM-SM-TRAIN-004).
- "The recipe error is in the launch call parameter." Recipes are passed by S3 reference because the inline field is capped near 2500 characters. Inspect the S3 recipe object and confirm the execution role can read it (`api-quirks.md` §5, LLM-SM-TRAIN-004, 005, 006).
- "There is an `Approved` package in the group, so the group is governed." Approval only counts for the version that is actually deployed or staged. A newer `PendingManualApproval` or `Rejected` version can be the one live. Resolve which version is deployed before clearing it (`api-quirks.md` §7, LLM-SM-REG-002).
- "No CloudWatch datapoints for the registry, so nothing is wrong." Absent datapoints mean nothing was emitted, not a measured zero. Registry posture comes from the describe and list APIs, not from metrics (`api-quirks.md` §6).
- "The model is registered, so it has lineage." Registration and lineage are separate. A registered package can have no association back to its training job or dataset, which is LLM-SM-REG-003 (LOW, `workload-specific`).
- "The group has a resource policy, so its boundary is governed." Check the breadth: overly broad cross-account access, or an artifact location that is not CMK-encrypted, is LLM-SM-REG-004 even when a policy exists.
- "A collection call returned AccessDenied, so the check doesn't apply." AccessDenied is a gap, not a clean result. Name the API and resource you could not read, continue, and disclose the gap.

## Severity Definitions

| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active production impact or total review blindness | 24–48 hours |
| **HIGH** | Serious reliability / security / cost risk | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are operational guidance (derived), not AWS-published commitments.

## Error Handling

Before interpreting any response, consult [api-quirks.md](references/api-quirks.md): it enumerates the misleading
read-only responses that cause false positives and false negatives in this review (traps §1–§5 for training,
§6–§7 for the Model Registry):

- **`InProgress`/`SecondaryStatus Pending` is NOT `Failed`** (§1). A job waiting on GPU capacity is
  control-plane-healthy; report Pending-on-capacity and prescribe no config change (LLM-SM-TRAIN-007).
- **`InsufficientCapacityError` (AWS-side) ≠ instance-type quota = 0 (customer)** (§2). Opposite remediations:
  retry/alternate for capacity (LLM-SM-TRAIN-002) vs a quota-increase request for a zero quota
  (LLM-SM-TRAIN-003). Read both the `FailureReason` and `service-quotas get-service-quota`.
- **`allow_percentage_invalid_samples` silently drops records** (§3). A job can report `Completed` while dropping
  corrupt JSONL up to the tolerance; "succeeded" is not proof all data was used (LLM-SM-TRAIN-001). Check the
  drop count, not just the status.
- **Nova rejects a null `HyperParameters` map** (§4). A null/omitted required hyperparameter is a hard validation
  failure at create time, not a silent default (LLM-SM-TRAIN-004).
- **The recipe is referenced from S3, not inlined** (§5). The inline field is capped (~2500 chars), so a recipe
  error points at the **S3 recipe object** and the role must be able to read it (LLM-SM-TRAIN-004/005/006).
- **CloudWatch "no datapoints" ≠ a measured zero** (§6). Absent datapoints mean **no traffic or no emission** in
  the window, not a value of zero. The Model Registry publishes no metric namespace, so absent datapoints say
  nothing about registry health.
- **An `Approved` package ≠ the deployed version is approved** (§7). A group with an `Approved` package is only
  governed if the version actually deployed/staged is that approved version; a newer
  `PendingManualApproval`/`Rejected` version can be the one live. Resolve which version is deployed before
  clearing a group as approved (LLM-SM-REG-002).

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource you could
not read, continue with the rest, and list the gap; never guess. On a **region unsupported for a feature**, record
it as a disclosed assumption, not a finding. On **throttling of describe/list calls**, back off and paginate. On
**ambiguous scope**, ask or default to the caller's current region and the jobs or packages in it, and say so.

## Related skills (optional)

**Related skills (optional).** This skill works on its own. When a question reaches into an area listed below:
- If that skill is in your available skills, load it and use it for that part.
- If it isn't, handle that part yourself with the read-only checks in this skill and general AWS knowledge.
  Label findings that come from general knowledge, and don't give them a check-id.
- At the end of the answer, recommend installing the missing skill once, and name what it would add.

| Area | Skill |
|---|---|
| Live failures right now: errors, 5xx, throttling, latency, "is it AWS or us" | opsai-incident-triage |
| Bedrock model access, invocation logging, model lifecycle, inference profiles, Knowledge Bases / RAG | opsai-bedrock-review |
| Who can call Bedrock (IAM users, long-lived keys), Bedrock Guardrails | opsai-bedrock-security |
| Bedrock spend, quotas, Provisioned Throughput | opsai-capacity-cost |
| Bedrock AgentCore and Bedrock Agents | opsai-bedrock-agentcore |
| SageMaker real-time, serverless and async endpoints, batch transform, SageMaker endpoint cost | opsai-sagemaker-inference |
| Output quality, regressions, evaluation jobs (Bedrock or SageMaker), truncation, finish reasons | opsai-ml-eval-check |

Future price quotes: use the [AWS Pricing Calculator](https://calculator.aws/).

## Appendix — Reference Links

References under `references/`:

- [checks-sagemaker-training.md](references/checks-sagemaker-training.md) — load before assigning any check-id or
  severity: the LLM-SM-TRAIN-* and LLM-SM-REG-* check catalog (primary).
- [collection-reference.md](references/collection-reference.md) — load with any Router row, or when you need the
  read-only collection API (training describe, service-quotas, S3-read, IAM-read, model packages) and the fields
  each contributes.
- [metrics-and-logs.md](references/metrics-and-logs.md) — load when mapping a `FailureReason` to a TRAIN check or
  reading the training-job describe/log signals (including the EventBridge lifecycle note for one-shot jobs), or
  when looking for registry signals: the registry has no metric namespace, so it lists the describe/list,
  EventBridge and CloudTrail signals to read instead.
- [api-quirks.md](references/api-quirks.md) — load before interpreting any status, `FailureReason` or quota value,
  before clearing a group as approved, or when reading an empty metric: misleading read-only API responses
  (traps §1–§7).
- [known-causes.md](references/known-causes.md) — load whenever the user names a specific error or symptom:
  documented break-fix causes, each with its AWS-doc citation. Training (§1–§7): PassRole vs execution role, KMS
  key policy, missing logs, capacity vs quota, spot and checkpoint resume, host vs GPU memory, distributed and VPC
  networking, metric definitions. Model Registry (§8–§14): explicit registration, approval status, cross-account
  resource policies and RAM sharing, supported instance types, auto-created lineage, MLflow client and server
  versions, promoting the registered version.

Output templates under `assets/` (one per area; load the one for the area when a full report is requested):

- [training-job-health-report-template.md](assets/training-job-health-report-template.md) — load for a training
  report: per-job state, failure classification, findings, cost note, disclosed scope.
- [model-registry-health-report-template.md](assets/model-registry-health-report-template.md) — load for a
  registry governance report: registration coverage, per-package approval and lineage, group boundary, findings
  with LLM-SM-REG check-ids, disclosed scope.

AWS documentation:

- [Fine-tuning Amazon Nova models](https://docs.aws.amazon.com/nova/latest/userguide/nova-fine-tune-1.html)
- [Preparing data for Nova fine-tuning](https://docs.aws.amazon.com/nova/latest/userguide/fine-tune-prepare-data-understanding.html)
- [DescribeTrainingJob](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingJob.html)
- [How SageMaker provides training information](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-training-algo-running-container.html)
- [Training environment variables](https://docs.aws.amazon.com/sagemaker/latest/dg/your-algorithms-training-algo-running-container.html)
- [SageMaker execution roles](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-roles.html)
- [SageMaker endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/sagemaker.html)
- [Model Registry](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
- [Update model approval status](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html)
- [ML Lineage Tracking](https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking.html)
