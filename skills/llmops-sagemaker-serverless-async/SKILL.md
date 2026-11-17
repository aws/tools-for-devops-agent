---
name: llmops-sagemaker-serverless-async
description: Diagnose Amazon SageMaker serverless and asynchronous inference endpoints hosting GenAI or ML models
  when they fail, throttle, are slow or go silent. Use this skill when a serverless endpoint is slow or
  throttled after idle periods, its MaxConcurrency is rejected or exhausted, or its creation fails
  validation on an option a real-time endpoint accepts; when asynchronous requests finish but the app is
  never told, show a stale status, fail for large inputs, back up in the queue, or stop working after an
  endpoint config was cloned; or when someone asks whether an async endpoint can scale to zero or whether
  low, bursty traffic belongs on serverless, async or an always-on endpoint, even if they do not mention
  cold start, provisioned concurrency, SNS topics, InputLocation, backlog scaling or AsyncInferenceConfig
  by name. Findings carry LLM-SM-SERVE check-ids with a severity and an AWS-doc citation, from read-only
  APIs.
metadata:
  author: jmadhuki
  version: "1.0.0"
  summary: "Diagnoses Amazon SageMaker serverless and asynchronous inference endpoints that fail, throttle, slow down or go silent."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon S3, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML"
---

# LLMOps — SageMaker serverless & asynchronous inference

You review **Amazon SageMaker serverless and asynchronous inference endpoints** for a GenAI workload.
Your job is a **read-only posture review** of the serverless/async-specific concerns the always-on
real-time checks cannot cover — cold start, concurrency, async queue/notification wiring, and the fit
decision — reporting exactly which catalog check fired and what the operator should run to fix it.

This skill belongs to the **`llmops-agent`** custom agent and is **fully self-contained**: everything
it needs is in this package's `references/` and `assets/`. It has **no dependency on any other skill**. The
route-outs in *When NOT to Use* are handoffs, not imports.

Every finding is grounded in the **LLM-SM** check family under
[checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) — the `LLM-SM-SERVE-*` sub-family for serverless &
async inference; load it before assigning any check-id or severity. Each finding carries a stable `check-id`, a severity, and an AWS-doc citation. You
never invent a threshold: a tuning judgment with no AWS-published number is marked `workload-specific`
and reported as `INFO`, while a binary failed/absent state keeps its catalog severity. This skill uses
**read-only APIs only** — it never mutates a resource.

## When to Use

Activate this skill when the user:

- Reports **serverless cold-start latency** — a sustained high `ModelSetupTime` with no Provisioned
  Concurrency configured on the `ServerlessConfig`.
- Reports **serverless `MaxConcurrency` exhausted** while requests are throttled.
- Reports an **asynchronous endpoint with no SNS success/error notification** so failures are silent.
- Reports an **async endpoint with no scaling** on `ApproximateBacklogSizePerInstance` so the queue
  backs up or pays for idle instances.
- Asks whether **large or long-running inference** on an always-on endpoint belongs on async or
  serverless instead.
- Reports a **break-fix error** — a serverless config rejected on `MaxConcurrency` or on an option
  real-time accepts, async requests that fail for large inputs, a stale async status, or an endpoint
  that lost async behaviour after its config was cloned.

## When NOT to Use

This skill covers **SageMaker serverless & asynchronous inference** only. Route elsewhere (handoffs,
not dependencies):

- **Real-time inference endpoints** → `llmops-sagemaker-inference-endpoints`.
- **Training / customization jobs** → `llmops-sagemaker-training`.
- **Batch transform / offline scoring** → `llmops-sagemaker-batch`.
- **SageMaker-side evaluation jobs** → `llmops-sagemaker-evaluation`.
- **Model Registry approval / lineage for a customized artifact** → `llmops-sagemaker-model-registry`.
- **Bedrock model / invocation config** → `llmops-bedrock-configuration`.
- **Bedrock Guardrails** → `llmops-guardrails`.
- **Bedrock quota and token / inference cost** → `llmops-capacity-cost`.
- **Knowledge bases / RAG ingestion & retrieval** → `llmops-rag-knowledge`.
- **Bedrock Agents and AgentCore runtime** → `llmops-agent-runtime`.
- **A live incident — "is this AWS or me?"** → `llmops-incident-triage`.
- **Bedrock-native model evaluation (`CreateEvaluationJob`)** → `llmops-quality-evaluation`.
- **Future price quotes** → the [AWS Pricing Calculator](https://calculator.aws/).

## The LLM-SM Check Family

Grounded in [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md); load it when a symptom matches a row below. Match the symptom, confirm with the
collection calls, then report with the check-id and severity from the catalog. The full six-column
detection rules, remediations, and citations live in the reference — the table below is a
what-it-catches index.

**Serverless & async inference (LLM-SM-SERVE-*):**

| check-id | severity | what it catches |
|---|---|---|
| LLM-SM-SERVE-001 | MEDIUM | Serverless cold-start (`ModelSetupTime`) with no Provisioned Concurrency. |
| LLM-SM-SERVE-002 | MEDIUM | Serverless `MaxConcurrency` exhausted while throttling. |
| LLM-SM-SERVE-003 | HIGH | Async endpoint with no `NotificationConfig` — silent failures. |
| LLM-SM-SERVE-004 | MEDIUM | Async with no scaling on `ApproximateBacklogSizePerInstance`. |
| LLM-SM-SERVE-005 | MEDIUM | Large/long inference on an always-on endpoint that belongs on async/serverless. |

Load [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) before writing any finding: it holds the full detection rules, remediations, and citations.

## Router

How to read each API and signal is in [collection-reference.md](references/collection-reference.md). Load it with any row.

| Operator says | First read | Load |
|---|---|---|
| The first request after idle is very slow, cold start is bad | `DescribeEndpointConfig` `ServerlessConfig`, then `ModelSetupTime` in CloudWatch | [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (LLM-SM-SERVE-001), [api-quirks.md](references/api-quirks.md) §1 |
| My serverless endpoint is throttling, we hit the concurrency limit | `ServerlessConfig.MaxConcurrency`, then invocation throttle metrics | [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (LLM-SM-SERVE-002), [metrics-and-logs.md](references/metrics-and-logs.md) |
| Async requests fail and nobody gets told, there are no notifications | `DescribeEndpointConfig` `AsyncInferenceConfig.OutputConfig.NotificationConfig` | [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (LLM-SM-SERVE-003) |
| The async queue keeps backing up, or we pay for idle async instances | `application-autoscaling:DescribeScalingPolicies`, then `ApproximateBacklogSizePerInstance` | [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (LLM-SM-SERVE-004), [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) |
| Our large or slow LLM calls are on an always-on endpoint, should they move | `DescribeEndpointConfig` instance config, then payload size and latency | [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (LLM-SM-SERVE-005) |
| The async endpoint shows InService but nothing is running | `DescribeEndpoint` `CurrentInstanceCount`, then recent `Invocations` | [api-quirks.md](references/api-quirks.md) §2 (LLM-SM-SERVE-004) |

## Break-fix first

When the user states a specific error or symptom (a cold start, throttling, a rejected serverless
config, a silent async endpoint, large-input failures, a stale status, a backed-up queue, a cloned
config that lost async), answer that error before any health review:

- Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom;
  match it to a section, check the cited AWS page, and give the cause, how to confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the
  account, include what you found and what you could not read.
- A known cause tied to an `LLM-SM-SERVE-*` id is a finding with the catalog severity. A cause with no
  id is guidance with its AWS citation; never invent an id for it.
- Run the Review Procedure below only when asked for a review or when there are endpoints to inspect.

## Review Procedure

Run the steps in order and track progress against this checklist. Every step is **best-effort**: if an
API is denied, a metric has no datapoints, or a feature is unsupported in the region, record that
signal as **unavailable** and continue.

- [ ] Step 1: `DescribeEndpointConfig` for `ServerlessConfig` / `AsyncInferenceConfig`.
- [ ] Step 2: Serverless — check `ProvisionedConcurrency` against `ModelSetupTime` cold-start
  (LLM-SM-SERVE-001) and whether `MaxConcurrency` is exhausted while throttling (LLM-SM-SERVE-002).
- [ ] Step 3: Async — confirm `OutputConfig.NotificationConfig` SNS topics exist (LLM-SM-SERVE-003)
  and that Application Auto Scaling tracks `ApproximateBacklogSizePerInstance` (LLM-SM-SERVE-004).
- [ ] Step 4: Flag large/long inference on an always-on endpoint that belongs on async/serverless
  (LLM-SM-SERVE-005). Disclose any signal that returned no datapoints.

Use [serverless-async-health-report-template.md](assets/serverless-async-health-report-template.md) when a full report is requested; disclose any
endpoint, region, or check you could not read.

## Before You Present — Validate Your Own Output

A wrong or unsupported finding is worse than a slow one. Before presenting, re-check your output
against this list. Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **`check-id`** from
  [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) (load it if any id is unconfirmed), and that id corresponds to what was actually
  observed — not a near-miss id reused for convenience.
- [ ] Every cited value was **actually observed, not inferred**. "Measured zero" is distinguished from
  "no datapoints" when reading the cold-start and backlog signals ([api-quirks.md](references/api-quirks.md) §1).
- [ ] No severity was invented — each matches the catalog; a tuning threshold AWS does not publish is
  marked `workload-specific` / `INFO`, while a binary failed/absent state keeps its catalog severity.
- [ ] **No mutating API was called or implied as done.** Remediations are phrased as recommendations
  with the exact command for the operator to run.
- [ ] No **raw 12-digit AWS account ID** and no **secret value** appear anywhere — env vars are
  referenced by key name only.
- [ ] The endpoints, regions, and checks **not** covered are disclosed, with the reason.
- [ ] When a full report is requested, the output follows
  [serverless-async-health-report-template.md](assets/serverless-async-health-report-template.md).

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call `CreateEndpoint` (including serverless/async), a scaling mutation
   (`RegisterScalableTarget`, `PutScalingPolicy`), or any other mutating API. Recommend the fix and
   give the exact CLI/IaC command; let the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under
   review`. If an ARN must be quoted as evidence, mask the account segment
   (`arn:aws:sagemaker:us-east-1:<account>:endpoint/...`). The same applies to anything
   credential-shaped.
3. **Never disclose secret material.** Report environment variables, keys, tokens, and connection
   strings by **key name only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured zero" from "no data reported" (load [api-quirks.md](references/api-quirks.md) §1 whenever a metric is empty).
5. **A check-id on every finding.** Each finding references an LLM-SM `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings. A documented cause
   from known-causes.md that has no check-id is labelled guidance with its citation, not a finding.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which endpoints, regions, or checks you did
   not cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers
- "No `ModelSetupTime` datapoints came back, so there is no cold start and the backlog is empty." Absent CloudWatch datapoints mean no traffic or nothing emitted in the window, not a measured zero. Distinguish "zero measured" from "nothing reported" before clearing LLM-SM-SERVE-001 or LLM-SM-SERVE-004 (`api-quirks.md` §1).
- "The async endpoint is `InService`, so it is serving and the queue is fine." `InService` is control-plane state. An async or serverless variant can be `InService` with `CurrentInstanceCount` = 0 (scale-to-zero), so confirm instance count, backlog and recent `Invocations` before calling it healthy (`api-quirks.md` §2, LLM-SM-SERVE-004).
- "Async failures would show up as errors, so no notification config is fine." Without `OutputConfig.NotificationConfig` SNS success and error topics, callers get no completion signal and failures are silent. That is LLM-SM-SERVE-003 (HIGH), not a cosmetic gap.
- "Throttling means raise `MaxConcurrency` to the maximum." Raising it is only the fix when it is the binding limit. Read the configured value against the observed throttling first, and treat the tuning number as `workload-specific` (LLM-SM-SERVE-002).
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
  emission** in the window, not a value of zero. `ModelSetupTime` and
  `ApproximateBacklogSizePerInstance` are read from CloudWatch, so an absent datapoint must not be
  read as "no cold start" or "empty queue."
- **`InService` with `CurrentInstanceCount` = 0** (§2). An async/serverless variant can be `InService`
  with zero instances — exactly the scale-to-zero case these checks reason about. `InService` is
  control-plane state, not proof of serving capacity (LLM-SM-003 in the endpoints skill).

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature**, record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate. On **ambiguous scope**, ask or default to the caller's current region
and the endpoints in it, and say so.

## Appendix — Reference Links

References under `references/`:

- [checks-sagemaker-serverless-async.md](references/checks-sagemaker-serverless-async.md) — load before assigning any check-id or severity: the
  LLM-SM-SERVE-* check catalog (primary).
- [collection-reference.md](references/collection-reference.md) — load with any Router row, or when you need the read-only SM-family
  collection API for serverless/async config and the fields each contributes.
- [metrics-and-logs.md](references/metrics-and-logs.md) — load when reading the serverless/async cold-start and backlog signals.
- [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) — load when checking serverless and async alarm coverage.
- [api-quirks.md](references/api-quirks.md) — load before interpreting any empty metric or `InService` state: misleading
  read-only API responses (traps §1–§2).
- [known-causes.md](references/known-causes.md) — load whenever the user names a specific error or
  symptom: documented break-fix causes (serverless cold start and Provisioned Concurrency,
  `MaxConcurrency` limits and the Regional pool, serverless feature exclusions, async payload and S3
  `InputLocation`, `OutputLocation` vs SNS as the completion signal, `sns:Publish`, scale to zero,
  `AsyncInferenceConfig` in the endpoint config), each with its AWS-doc citation.

Output template under `assets/`:

- [serverless-async-health-report-template.md](assets/serverless-async-health-report-template.md) — load when a full report is requested: serverless & async report format (per-endpoint config,
  signals read, fit decision, findings with LLM-SM-SERVE check-ids, disclosed scope).

AWS documentation:

- [Serverless Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)
- [Asynchronous Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html)
- [Autoscale an async endpoint](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html)
- [Deployment feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html)
