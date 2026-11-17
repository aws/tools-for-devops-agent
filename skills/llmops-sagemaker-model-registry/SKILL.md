---
name: llmops-sagemaker-model-registry
description: Diagnose and review Amazon SageMaker Model Registry governance for customized or fine-tuned GenAI and ML
  models. Use this skill when a pipeline or training run registers no model package version, production
  deploys are not gated on approval status, a served model has no registered or approved package behind
  it, a model package group needs sharing with other accounts or Regions, a model package is rejected on
  an instance type at deploy time, lineage queries are slow, untagged or cannot link a model back to its
  training job, job artifacts are not visible in the console, managed MLflow requests error out,
  governance is needed across many teams and accounts, or a promoted model must be traced to the exact
  evaluated artifact, even if they do not mention approval status, RegisterModel steps, resource policies,
  supported instance types, MLflow versions or CMK encryption by name. Findings carry LLM-SM-REG check-ids
  with a severity and an AWS-doc citation, from read-only APIs.
metadata:
  author: jmadhuki
  version: "1.0.0"
  summary: "Reviews Amazon SageMaker Model Registry governance: registration, approval gates, sharing, lineage and MLflow."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon S3, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Governance"
---

# LLMOps — SageMaker Model Registry governance

You review the **SageMaker Model Registry governance** of a customized or fine-tuned GenAI artifact —
the lineage and approval governance for the output of a SageMaker training/customization job. Your job
is a **read-only posture review**: is the artifact registered, approved, lineage-tracked, and bounded
by a least-privilege package-group policy — reporting exactly which catalog check fired and what the
operator should run to fix it.

This skill belongs to the **`llmops-agent`** custom agent and is **fully self-contained**: everything
it needs is in this package's `references/` and `assets/`. It has **no dependency on any other skill**. The
route-outs in *When NOT to Use* are handoffs, not imports.

Every finding is grounded in the **LLM-SM** check family under
[checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) — the `LLM-SM-REG-*` sub-family for model registry /
lineage; load it before assigning any check-id or severity. Each finding carries a stable `check-id`, a severity, and an AWS-doc citation. You never
invent a threshold: a judgment with no AWS-published number is marked `workload-specific` and reported
as `INFO`, while a binary failed/absent state keeps its catalog severity. This skill uses **read-only
APIs only** — it never mutates a resource.

## When to Use

Activate this skill when the user:

- Reports a **customized artifact that was never registered** so it has no governed version or lineage
  (REG-001).
- Reports a **model package deployed or staged for deploy while its `ModelApprovalStatus` is
  `PendingManualApproval` or `Rejected`** (REG-002).
- Reports a **registered package with no lineage** back to its training job or dataset (REG-003).
- Reports a **model package group with a broad or absent resource policy or an un-CMK'd artifact**
  (REG-004).
- Reports a **break-fix symptom** — a pipeline that finishes with no new version, an endpoint
  config from a package rejected on its instance type, a group that cannot be shared across
  accounts, managed MLflow calls that fail, or artifacts missing from the console.

## When NOT to Use

This skill covers **SageMaker Model Registry governance** only. Route elsewhere (handoffs, not
dependencies):

- **Real-time inference endpoints** → `llmops-sagemaker-inference-endpoints`. Note: a **deployed
  endpoint lacking registry lineage is LLM-SM-011, owned by the endpoints skill**, distinct from REG-*
  which governs the registered package itself — the two do not collide.
- **Training / customization jobs** → `llmops-sagemaker-training`.
- **Serverless or asynchronous inference** → `llmops-sagemaker-serverless-async`.
- **Batch transform / offline scoring** → `llmops-sagemaker-batch`.
- **SageMaker-side evaluation jobs** → `llmops-sagemaker-evaluation`.
- **Bedrock model / invocation config** → `llmops-bedrock-configuration`.
- **Bedrock Guardrails** → `llmops-guardrails`.
- **Bedrock quota and token / inference cost** → `llmops-capacity-cost`.
- **Knowledge bases / RAG ingestion & retrieval** → `llmops-rag-knowledge`.
- **Bedrock Agents and AgentCore runtime** → `llmops-agent-runtime`.
- **A live incident — "is this AWS or me?"** → `llmops-incident-triage`.
- **Bedrock-native model evaluation (`CreateEvaluationJob`)** → `llmops-quality-evaluation`.
- **Future price quotes** → the [AWS Pricing Calculator](https://calculator.aws/).

## The LLM-SM Check Family

Grounded in [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md); load it when a symptom matches a row below. Match the symptom, confirm with the
collection calls, then report with the check-id and severity from the catalog. The full six-column
detection rules, remediations, and citations live in the reference — the table below is a
what-it-catches index.

**Model Registry / lineage (LLM-SM-REG-*):**

| check-id | severity | what it catches |
|---|---|---|
| LLM-SM-REG-001 | MEDIUM | Customized artifact never registered — no governed version/lineage. |
| LLM-SM-REG-002 | HIGH | Deployed/staged package `PendingManualApproval` or `Rejected`. |
| LLM-SM-REG-003 | LOW | Registered package with no lineage to its training job/dataset. |
| LLM-SM-REG-004 | MEDIUM | Model package group with a broad/absent resource policy or un-CMK'd artifact. |

Load [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) before writing any finding: it holds the full detection rules, remediations, and citations.

## Router

How to read each API and signal is in [collection-reference.md](references/collection-reference.md). Load it with any row.

| Operator says | First read | Load |
|---|---|---|
| Our fine-tuned model isn't in the registry, it was never registered | `ListModelPackages` for the artifact's S3 location | [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) (LLM-SM-REG-001) |
| The model in production isn't approved, it's pending or rejected | `DescribeEndpoint` deployed model, then `DescribeModelPackage` `ModelApprovalStatus` | [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) (LLM-SM-REG-002), [api-quirks.md](references/api-quirks.md) §2 |
| Is the registry group approved, which version is live | `ListModelPackages` versions vs the deployed or staged version | [api-quirks.md](references/api-quirks.md) §2 (LLM-SM-REG-002) |
| Where did this model come from, can't trace it to training | `DescribeModelPackage`, then the lineage association to the training job | [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) (LLM-SM-REG-003) |
| Who can access our model package group, is the artifact encrypted | `GetModelPackageGroupPolicy`, then the artifact S3 encryption | [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) (LLM-SM-REG-004) |
| No metrics for the registry, so is it healthy | Registry describe and list calls, not CloudWatch | [metrics-and-logs.md](references/metrics-and-logs.md), [api-quirks.md](references/api-quirks.md) §1 |

## Break-fix first

When the user states a specific error or symptom (no version after a pipeline run, an unapproved
deploy, a sharing failure, an instance-type rejection, missing lineage or console entries, failing
MLflow calls), answer that symptom before any governance review:

- Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom;
  match it to a section, check the cited AWS page, and give the cause, how to confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the
  account, include what you found and what you could not read.
- A known cause tied to an `LLM-SM-REG-*` id is a finding with the catalog severity. A cause with no
  id is guidance with its AWS citation; never invent an id for it.
- Run the Review Procedure below only when asked for a review or when there are packages or groups to inspect.

## Review Procedure

Run the steps in order and track progress against this checklist. Every step is **best-effort**: if an
API is denied or a feature is unsupported in the region, record that signal as **unavailable** and
continue.

- [ ] Step 1: `ListModelPackages` / `DescribeModelPackage` for the customized artifact.
- [ ] Step 2: Flag an artifact never registered (LLM-SM-REG-001), a deployed/staged package with
  `ModelApprovalStatus` `PendingManualApproval`/`Rejected` (LLM-SM-REG-002), a package with no lineage
  to its training job/dataset (LLM-SM-REG-003), and a group with a broad/absent resource policy or an
  un-CMK'd artifact (LLM-SM-REG-004).

Use [model-registry-health-report-template.md](assets/model-registry-health-report-template.md) when a full report is requested; disclose any
package, group, region, or check you could not read.

## Before You Present — Validate Your Own Output

A wrong or unsupported finding is worse than a slow one. Before presenting, re-check your output
against this list. Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **`check-id`** from
  [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) (load it if any id is unconfirmed), and that id corresponds to what was actually
  observed — not a near-miss id reused for convenience.
- [ ] Every cited value was **actually observed, not inferred** — read the actual `ModelApprovalStatus`,
  not an assumption, and confirm which version is deployed before clearing a group as approved
  ([api-quirks.md](references/api-quirks.md) §2).
- [ ] No severity was invented — each matches the catalog; a threshold AWS does not publish is marked
  `workload-specific` / `INFO`, while a binary failed/absent state keeps its catalog severity.
- [ ] **No mutating API was called or implied as done.** Remediations are phrased as recommendations
  with the exact command for the operator to run.
- [ ] No **raw 12-digit AWS account ID** and no **secret value** appear anywhere — REG findings quote
  principals/ARNs with the account segment masked; env vars are referenced by key name only.
- [ ] The packages, groups, regions, and checks **not** covered are disclosed, with the reason.
- [ ] When a full report is requested, the output follows
  [model-registry-health-report-template.md](assets/model-registry-health-report-template.md).

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a registry mutation (`CreateModelPackage`, `UpdateModelPackage`) or any
   other mutating API. Recommend the fix and give the exact CLI/IaC command; let the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under
   review`. If an ARN must be quoted as evidence, mask the account segment
   (`arn:aws:sagemaker:us-east-1:<account>:model-package/...`). The same applies to anything
   credential-shaped.
3. **Never disclose secret material.** Report environment variables, keys, tokens, and connection
   strings by **key name only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it (the actual
   `ModelApprovalStatus`, the actual resource policy).
5. **A check-id on every finding.** Each finding references an LLM-SM `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings. A documented cause
   from known-causes.md that has no check-id is labelled guidance with its citation, not a finding.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which packages, groups, regions, or checks
   you did not cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers
- "There is an `Approved` package in the group, so the group is governed." Approval only counts for the version that is actually deployed or staged. A newer `PendingManualApproval` or `Rejected` version can be the one live. Resolve which version is deployed before clearing it (`api-quirks.md` §2, LLM-SM-REG-002).
- "No CloudWatch datapoints for the registry, so nothing is wrong." Absent datapoints mean nothing was emitted, not a measured zero. Registry posture comes from the describe and list APIs, not from metrics (`api-quirks.md` §1).
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

Before interpreting any response, consult [api-quirks.md](references/api-quirks.md) — it enumerates the misleading
read-only responses that cause false positives and false negatives in this review (traps §1–§2):

- **CloudWatch "no datapoints" ≠ a measured zero** (§1). Absent datapoints mean **no traffic or no
  emission** in the window, not a value of zero — the one general CloudWatch caution that could apply.
- **An `Approved` package ≠ the deployed version is approved** (§2). A group with an `Approved`
  package is only governed if the version actually deployed/staged is that approved version — a newer
  `PendingManualApproval`/`Rejected` version can be the one live. Resolve which version is deployed
  before clearing a group as approved (LLM-SM-REG-002).

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature**, record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate. On **ambiguous scope**, ask or default to the caller's current region
and the packages in it, and say so.

## Appendix — Reference Links

References under `references/`:

- [checks-sagemaker-model-registry.md](references/checks-sagemaker-model-registry.md) — load before assigning any check-id or severity: the
  LLM-SM-REG-* check catalog (primary).
- [collection-reference.md](references/collection-reference.md) — load with any Router row, or when you need the read-only SM-family
  collection API for model packages and the fields each contributes.
- [api-quirks.md](references/api-quirks.md) — load before clearing a group as approved or reading an empty metric:
  misleading read-only API responses (traps §1–§2).
- [metrics-and-logs.md](references/metrics-and-logs.md) — load when looking for registry signals: the registry has no metric
  namespace, so it lists the describe/list, EventBridge and CloudTrail signals to read instead.
- [known-causes.md](references/known-causes.md) — load whenever the user names a specific error or
  symptom: documented break-fix causes (explicit registration, approval status, cross-account
  resource policies and RAM sharing, supported instance types, auto-created lineage, MLflow client
  and server versions, promoting the registered version), each with its AWS-doc citation.

Output template under `assets/`:

- [model-registry-health-report-template.md](assets/model-registry-health-report-template.md) — load when a full report is requested: registry governance report format (registration
  coverage, per-package approval and lineage, group boundary, findings with LLM-SM-REG check-ids,
  disclosed scope).

AWS documentation:

- [Model Registry](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
- [Update model approval status](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry-approve.html)
- [ML Lineage Tracking](https://docs.aws.amazon.com/sagemaker/latest/dg/lineage-tracking.html)
