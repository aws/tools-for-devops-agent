---
name: opsai-sagemaker-inference
description: Diagnose Amazon SageMaker inference that fails, errors, is slow, scales wrong or costs too much across
  real-time, serverless and asynchronous endpoints and batch transform jobs. Use this skill when an endpoint is
  Failed or never passes its health check, cannot read its model artifact from S3 or KMS, is unreachable from a
  private subnet, returns ModelError or 5xx, does not scale out, or sits idle while billed; when a serverless
  endpoint cold-starts or throttles; when async requests never notify, back up or fail on large inputs; when a
  transform job fails to parse records, times out or reports Completed with records missing; or when someone asks
  whether an endpoint is right-sized, what it costs in instance-hours, or whether traffic belongs on real-time,
  serverless, async or batch. It diagnoses the endpoint itself (FailureReason, health check, VPC, scaling,
  ModelError), not whether a live fault sits with the provider, infrastructure or application. Findings carry
  LLM-SM check-ids from read-only APIs.
metadata:
  author: jmadhuki
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Diagnoses Amazon SageMaker real-time, serverless, async and batch transform inference that fails, errors, slows down, mis-scales or costs too much."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon S3, Amazon CloudWatch, Amazon VPC"
  aws-devops-agent-skills.technical-domains: "AI/ML"
---

# OpsAI — SageMaker inference (real-time, serverless/async, batch transform)

You review **Amazon SageMaker inference** serving a GenAI or ML workload, in three areas: **real-time endpoints**
(reliable, observable, secure and sized to their traffic), **serverless and asynchronous endpoints** (cold start,
concurrency, async queue and notification wiring, and the fit decision) and **batch transform jobs** used for
offline scoring (failure, right-sizing, output integrity and encryption). Your job is a **read-only posture and
failure review**: when something degrades, say exactly which catalog check fired and what the operator should run
to fix it.

This skill works on its own: everything it needs is in its `references/` and `assets/` files. Read-only APIs only.
Every finding is grounded in the **LLM-SM** check family in
[checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (`LLM-SM-001..011` real-time,
`LLM-SM-SERVE-*` serverless/async, `LLM-SM-BATCH-*` batch transform); load it before assigning any check-id or
severity. Each finding carries a stable `check-id`, a severity, and an AWS-doc citation. You never invent a
threshold: a tuning/right-sizing judgment with no AWS-published number is marked `workload-specific` and reported
as `INFO`, while a binary failed/absent state keeps its catalog severity. This skill never mutates a resource.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## Scope and boundary

This skill diagnoses the **endpoint or job itself**: `FailureReason`, the health check (`/ping`, port 8080), the VPC
path, scaling, `ModelError`, capacity versus quota, input parsing and output integrity. It also owns **SageMaker
endpoint cost**: instance-hours of always-on variants and idle or abandoned endpoints (LLM-SM-003, LLM-SM-008,
LLM-SM-010, LLM-SM-SERVE-005).

Deciding whether a live fault sits with the provider, the infrastructure or the application belongs to the
live-failure triage area (see Related skills). For a bare "our calls are failing right now, is it AWS or us?" with
no endpoint detail, say that this skill does not decide the fault locus, gather endpoint evidence only if an
endpoint or job is named, and do not rule on the locus.

## When to Use

Activate this skill when the user:

**Real-time endpoints**
- Says a **SageMaker endpoint is slow or erroring** — `ModelLatency` rising, `OverheadLatency` growing,
  **`Invocation5XXErrors`** appearing.
- Asks whether an **endpoint is right-sized** — oversized instance type, under-used GPU, or paying for idle
  capacity — or what it costs in instance-hours.
- Reports the **endpoint is not scaling** or has **no auto-scaling** on its production variant.
- Says the **endpoint looks idle or is wasting money** — a variant with zero current instances, a leftover endpoint
  still billed by config.
- Wants to know whether **model monitoring / data capture** is in place, whether a **second variant for A/B or
  canary** exists, whether **Inference Recommender** was run, whether the endpoint is **inside a VPC** or
  **encrypted**, or whether the model has **registry lineage**.
- Reports a **break-fix error** — endpoint creation or update `Failed`, a custom container that never passes the
  health check, an access error on the model artifact, a private-subnet app that cannot reach the endpoint,
  `ModelError` on some calls, multi-model first-call latency, or a capacity or quota error creating the endpoint.

**Serverless & async**
- Reports **serverless cold-start latency** — a sustained high `ModelSetupTime` with no Provisioned Concurrency on
  the `ServerlessConfig` — or **`MaxConcurrency` exhausted** while requests are throttled.
- Reports an **asynchronous endpoint with no SNS success/error notification** so failures are silent, or **no
  scaling** on `ApproximateBacklogSizePerInstance` so the queue backs up or pays for idle instances.
- Asks whether **large, long-running or low, bursty traffic** on an always-on endpoint belongs on async or
  serverless instead.
- Reports a **break-fix error** — a serverless config rejected on `MaxConcurrency` or on an option real-time
  accepts, async requests that fail for large inputs, a stale async status, or an endpoint that lost async
  behaviour after its config was cloned.

**Batch transform**
- Reports a **transform job that Failed** — an input format or `ContentType` mismatch, or an S3 access error on the
  input/output path.
- Reports a job that is **under-parallelized** — `MaxConcurrentTransforms` of one on a large dataset.
- Reports a job that reports **`Completed` but wrote fewer output objects than input files**, or **transform
  output written without a customer-managed key** where the scored data is sensitive.
- Reports a **break-fix error** — records that fail to parse, timeouts on large records, a capacity or quota error
  at start, intermittent internal errors, or predictions that cannot be matched to their input rows.
- Asks whether a **large periodic scoring run** should use batch transform or a real-time endpoint.

Any area: wants a **health report** for one or more endpoints or transform jobs.

## The LLM-SM check family

Grounded in [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md); load it when a symptom
matches a row below. Match the symptom, confirm with the collection calls, then report with the check-id and
severity from the catalog. The table below is a what-it-catches index.

| check-id | area | severity | what it catches |
|---|---|---|---|
| LLM-SM-001 | Real-time | HIGH | No Application Auto Scaling target on the production variant — fixed capacity. |
| LLM-SM-002 | Real-time | HIGH | No `DataCaptureConfig` and no Model Monitor schedule — drift/quality unmonitored. |
| LLM-SM-003 | Real-time | HIGH | Variant `InService` but `CurrentInstanceCount` = 0 — abandoned or scaled-out leftover. |
| LLM-SM-004 | Real-time | MEDIUM | Single variant where safe rollout matters — no multi-variant A/B or canary. |
| LLM-SM-005 | Real-time | MEDIUM | Instance type/count chosen without an Inference Recommender run. |
| LLM-SM-006 | Real-time | HIGH | No `VpcConfig` where private networking is required. |
| LLM-SM-007 | Real-time | HIGH | Endpoint config `KmsKeyId` absent — storage volume not CMK-encrypted. |
| LLM-SM-008 | Real-time | MEDIUM | Low/bursty traffic on an always-on endpoint — idle-cost signal; the fit decision is LLM-SM-SERVE-005 (Step 4). |
| LLM-SM-009 | Real-time | MEDIUM | Latency growth or 5xx with no CloudWatch alarm — degradation undetected. |
| LLM-SM-010 | Real-time | LOW | GPU endpoint with sustained low GPU utilization — over-provisioned. |
| LLM-SM-011 | Real-time | LOW | Endpoint not deployed from a tracked model-registry version — no lineage. |
| LLM-SM-SERVE-001 | Serverless | MEDIUM | Serverless cold-start (`ModelSetupTime`) with no Provisioned Concurrency. |
| LLM-SM-SERVE-002 | Serverless | MEDIUM | Serverless `MaxConcurrency` exhausted while throttling. |
| LLM-SM-SERVE-003 | Async | HIGH | Async endpoint with no `NotificationConfig` — silent failures. |
| LLM-SM-SERVE-004 | Async | MEDIUM | Async with no scaling on `ApproximateBacklogSizePerInstance`. |
| LLM-SM-SERVE-005 | Serverless / async | MEDIUM | Large/long inference on an always-on endpoint that belongs on async/serverless. |
| LLM-SM-BATCH-001 | Batch | HIGH | Transform job `Failed` (format/`ContentType`/S3 access). |
| LLM-SM-BATCH-002 | Batch | LOW | Under-parallelized (`MaxConcurrentTransforms`=1) on a large dataset. |
| LLM-SM-BATCH-003 | Batch | MEDIUM | `Completed` but output count < input — partial scoring masked. |
| LLM-SM-BATCH-004 | Batch | MEDIUM | Transform output written without a CMK where data is sensitive. |

Load [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) before writing any finding: it holds
the full detection rules, remediations, and citations.

## Router

How to read each API is in [collection-reference.md](references/collection-reference.md); load it with any row.

| Operator says | Area | First read | Load |
|---|---|---|---|
| The endpoint isn't scaling, there's no auto-scaling | Real-time | `application-autoscaling:DescribeScalableTargets` for the variant | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-001), [api-quirks.md](references/api-quirks.md) §2 |
| Is my model being monitored, there's no data capture | Real-time | `DescribeEndpointConfig` `DataCaptureConfig`, `ListMonitoringSchedules` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-002) |
| This endpoint looks idle, a variant shows zero instances | Real-time | `DescribeEndpoint` `CurrentInstanceCount`, then recent `Invocations` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-003), [api-quirks.md](references/api-quirks.md) §1 |
| Do I have an A/B or canary variant | Real-time | `DescribeEndpoint` production-variant count and weights | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-004) |
| Is my endpoint right-sized, did we run inference recommender | Real-time | `ListInferenceRecommendationsJobs`, then both metric namespaces | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-005) |
| Is the endpoint in a VPC, is it encrypted | Real-time | `DescribeModel` `VpcConfig`, `DescribeEndpointConfig` `KmsKeyId` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-006, 007) |
| Am I wasting money on an always-on endpoint | Real-time | `Invocations` volume vs provisioned capacity (idle cost), then the fit decision in Step 4 (LLM-SM-SERVE-005) | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-008) |
| Latency is rising, I'm seeing 5xx errors | Real-time | `ModelLatency`, `Invocation5XXErrors`, then `DescribeAlarms` | [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) (LLM-SM-009) |
| This GPU instance looks oversized | Real-time | `GPUUtilization` from `/aws/sagemaker/Endpoints` | [metrics-and-logs.md](references/metrics-and-logs.md) §1 (LLM-SM-010) |
| Does my model have registry lineage | Real-time | `ListModelPackages` / `DescribeModelPackage` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-011) |
| The first request after idle is very slow, cold start is bad | Serverless | `DescribeEndpointConfig` `ServerlessConfig`, then `ModelSetupTime` in CloudWatch | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-SERVE-001), [api-quirks.md](references/api-quirks.md) §3 |
| My serverless endpoint is throttling, we hit the concurrency limit | Serverless | `ServerlessConfig.MaxConcurrency`, then invocation throttle metrics | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-SERVE-002), [metrics-and-logs.md](references/metrics-and-logs.md) §2 |
| Async requests fail and nobody gets told, there are no notifications | Async | `DescribeEndpointConfig` `AsyncInferenceConfig.OutputConfig.NotificationConfig` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-SERVE-003) |
| The async queue keeps backing up, or we pay for idle async instances | Async | `application-autoscaling:DescribeScalingPolicies`, then `ApproximateBacklogSizePerInstance` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-SERVE-004), [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) |
| Our large or slow LLM calls are on an always-on endpoint, should they move | Serverless / async | `DescribeEndpointConfig` instance config, then payload size and latency | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-SERVE-005) |
| The async endpoint shows InService but nothing is running | Async | `DescribeEndpoint` `CurrentInstanceCount`, then recent `Invocations` | [api-quirks.md](references/api-quirks.md) §1 (LLM-SM-SERVE-004) |
| My batch transform job failed, input format or content type error | Batch | `DescribeTransformJob` `FailureReason`, `TransformInput.ContentType` and `SplitType` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-BATCH-001), [metrics-and-logs.md](references/metrics-and-logs.md) §3 |
| The job failed with access denied on the input or output bucket | Batch | `DescribeTransformJob` `FailureReason`, then the job role against the S3 prefixes | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-BATCH-001) |
| Bulk scoring is slow, it runs one record at a time | Batch | `MaxConcurrentTransforms`, `MaxPayloadInMB`, `BatchStrategy` from `DescribeTransformJob` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-BATCH-002) |
| It says Completed but I'm missing results, some records weren't scored | Batch | `ListObjectsV2` on the output prefix vs the input file count | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-BATCH-003), [api-quirks.md](references/api-quirks.md) §4 |
| Is the scored output encrypted, is the data protected | Batch | `DescribeTransformJob` `TransformOutput.KmsKeyId` | [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (LLM-SM-BATCH-004) |
| No errors in the metrics, so is the job healthy | Batch | CloudWatch job metrics, then the transform logs | [api-quirks.md](references/api-quirks.md) §3, [metrics-and-logs.md](references/metrics-and-logs.md) §3 |

## Break-fix first

When the user states a specific error or symptom, answer that error before any health review. Symptoms include a
`Failed` endpoint, a health check that never passes, an access or KMS error on the artifact or on transform output,
an unreachable endpoint, `ModelError`, a capacity or quota error, a scale-out that never happens, a deploy that must
not drop traffic, a cold start, serverless throttling, a rejected serverless config, a silent async endpoint,
large-input failures, a stale async status, a backed-up queue, a cloned config that lost async, a parsing error, a
transform timeout, missing output records, an internal error, or unmatched predictions.

- Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom; match it to a
  section, check the cited AWS page, and give the cause, how to confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the account, include
  what you found and what you could not read.
- A known cause tied to a catalog id (`LLM-SM-001`..`LLM-SM-011`, `LLM-SM-SERVE-*`, `LLM-SM-BATCH-*`) is a finding
  with the catalog severity. A cause with no id is guidance with its AWS citation; never invent an id for it.
- Run the Review Procedure below only when asked for a review or when there are endpoints or jobs to inspect.

## Review Procedure

Run the steps in order and track progress against this checklist. Each step depends on state gathered by the one
before it, and each branches by area: run only the branches for the areas in scope. Every step is
**best-effort**: if an API is denied, a metric has no datapoints, or a feature is unsupported in the region, record
that signal as **unavailable** and continue — a review built on the checks you *could* run plus a disclosure of
what you skipped is correct and useful.

- [ ] Step 1: Identify the area and enumerate resources.
- [ ] Step 2: Read the configuration for the area.
- [ ] Step 3: Check reliability and scaling.
- [ ] Step 4: Check right-sizing, fit and lineage.
- [ ] Step 5: Read the metrics over the window.
- [ ] Step 6: State the endpoint cost picture.
- [ ] Step 7: Compare the alarm set.
- [ ] Step 8: Assemble findings and the report.

### Step 1 — Identify the area

**Endpoints.** `ListEndpoints` → `DescribeEndpoint` for each in scope, then `DescribeEndpointConfig`. A variant
with `ServerlessConfig` is **serverless**, an endpoint config with `AsyncInferenceConfig` is **async**, otherwise
the variant is **real-time**. For every production variant read `CurrentInstanceCount`, variant weights, and
`DataCaptureConfig` status. Do **not** trust `EndpointStatus: InService` as proof of serving — load
[api-quirks.md](references/api-quirks.md) §1 before calling any variant serving.

**Batch transform.** `ListTransformJobs` / `DescribeTransformJob` for status and `FailureReason`.

### Step 2 — Read the configuration

**Real-time endpoint.** `DescribeEndpointConfig` for instance type/count, `KmsKeyId` (LLM-SM-007) and
`DataCaptureConfig` (LLM-SM-002); `DescribeModel` for `VpcConfig` (LLM-SM-006). Report container environment
variables by **key name only** — never a value (Guardrail 3).

**Serverless / async.** `ServerlessConfig` (`MemorySizeInMB`, `MaxConcurrency`, `ProvisionedConcurrency`);
`AsyncInferenceConfig.OutputConfig.NotificationConfig` — no `SuccessTopic`/`ErrorTopic` is LLM-SM-SERVE-003.

**Batch transform.** A `Failed` job with its `FailureReason` is LLM-SM-BATCH-001; read `TransformInput`
`ContentType`/`SplitType`, `MaxConcurrentTransforms` / `MaxPayloadInMB` / `BatchStrategy` sizing
(LLM-SM-BATCH-002), and `TransformOutput.KmsKeyId` where data is sensitive (LLM-SM-BATCH-004).

### Step 3 — Check reliability and scaling

**Real-time endpoint.** `application-autoscaling:DescribeScalableTargets` / `DescribeScalingPolicies` for the
variant (LLM-SM-001); `ListMonitoringSchedules` for Model Monitor (LLM-SM-002); count variants for A/B / canary
(LLM-SM-004). An empty scalable-targets response on a production variant is **fixed capacity**, not "scaling
intentionally off" ([api-quirks.md](references/api-quirks.md) §2).

**Serverless.** Check whether `MaxConcurrency` is exhausted while throttling (LLM-SM-SERVE-002).

**Async.** Confirm Application Auto Scaling tracks `ApproximateBacklogSizePerInstance` (LLM-SM-SERVE-004).

**Batch transform.** Reconcile the output `.out` object count against input files via `ListObjectsV2`
(LLM-SM-BATCH-003) — a `Completed` status can mask partial scoring ([api-quirks.md](references/api-quirks.md) §4).

### Step 4 — Check right-sizing, fit and lineage

**Real-time endpoint.** `ListInferenceRecommendationsJobs` (LLM-SM-005); `ListModelPackages` / `DescribeModelPackage`
for registry lineage (LLM-SM-011). A right-sizing conclusion needs **both** metric namespaces — see Step 5.

**Fit decision (one decision, made here).** Low or bursty traffic on an always-on real-time endpoint is the
idle-cost signal LLM-SM-008. Whether that traffic belongs on serverless (spiky, low volume, tolerates cold starts)
or async (large payloads, long invocations) is LLM-SM-SERVE-005, driven by payload size and invocation duration.
Whether a periodic bulk scoring run with no live caller belongs on batch transform instead of a persistent endpoint
is guidance from [known-causes.md](references/known-causes.md) §18. Report the fit with the observed config and
metric values.

### Step 5 — Read the metrics over the window

Load [metrics-and-logs.md](references/metrics-and-logs.md) at this step. Treat **no datapoints** as "no traffic /
not emitted," not a measured zero ([api-quirks.md](references/api-quirks.md) §3).

**Real-time endpoint — the two-namespace rule.** Pull invocation metrics from **`AWS/SageMaker`** (`Invocations`,
`InvocationsPerInstance`, `ModelLatency`, `OverheadLatency`, `Invocation5XXErrors`) and instance resource metrics
from **`/aws/sagemaker/Endpoints`** (`CPUUtilization`, `MemoryUtilization`, `GPUUtilization`,
`GPUMemoryUtilization`). You **cannot** conclude an endpoint is oversized, under-used, or idle from one namespace.
The invocation metrics (`AWS/SageMaker`) tell you *how much traffic and how fast*; the instance resource metrics
(`/aws/sagemaker/Endpoints`) tell you *how hard the hardware is working*. A GPU endpoint with healthy `Invocations`
but sustained `GPUUtilization` under its band is over-provisioned (LLM-SM-010); an endpoint with
`CurrentInstanceCount` = 0 and no recent `Invocations` is idle/abandoned (LLM-SM-003). Report a right-sizing
finding only when you have read **both** namespaces, and say so if one was unavailable.

**Serverless.** `ModelSetupTime` (and `OverheadLatency`) against `ProvisionedConcurrency`: sustained cold-start
latency with no Provisioned Concurrency is LLM-SM-SERVE-001.

**Async.** `ApproximateBacklogSizePerInstance` and `ApproximateAgeOfOldestRequest`; a growing backlog with no
scaling policy confirms LLM-SM-SERVE-004.

**Batch transform.** Jobs are one-shot: read the describe status plus the `/aws/sagemaker/TransformJobs` log group,
not a steady metric namespace.

### Step 6 — State the endpoint cost picture

For always-on variants state instance type × instance count × hours in service over the window. Then name the cost
findings that apply: idle or abandoned variants (LLM-SM-003), the idle-cost signal (LLM-SM-008), GPU under-use
(LLM-SM-010) and the serverless/async fit (LLM-SM-SERVE-005). Async endpoints can scale to zero
([known-causes.md](references/known-causes.md) §11), and a transform job stops billing when it ends while an
endpoint keeps incurring charges until it is deleted (§18). Never invent a price; for future price quotes point to
the [AWS Pricing Calculator](https://calculator.aws/).

### Step 7 — Compare the alarm set

Load [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) at this step and compare
`DescribeAlarms` against it. **Real-time:** missing alarms on `ModelLatency` or `Invocation5XXErrors` while
degradation is present fires LLM-SM-009. **Serverless / async:** cold-start, backlog and oldest-request-age
alarms. **Batch transform:** lifecycle via an EventBridge rule on `TransformJobStatus = Failed`, not a metric.

### Step 8 — Assemble findings and the report

Give each finding its catalog `check-id`, the catalog severity, the concrete observed value that triggered it, and
the exact remediation command — **as a recommendation only** (Guardrail 1). Disclose every endpoint, job, region,
S3 prefix or check you did not cover and why. When a full report is requested, use the template for the area:

- [endpoint-health-report-template.md](assets/endpoint-health-report-template.md) — load when a full real-time
  endpoint report is requested.
- [serverless-async-health-report-template.md](assets/serverless-async-health-report-template.md) — load when a
  full serverless or async report is requested.
- [batch-job-health-report-template.md](assets/batch-job-health-report-template.md) — load when a full batch
  transform report is requested.

If asked where a live fault sits, report the endpoint findings and say the locus is decided by the live-failure
triage area (see Related skills).

## Before You Present — Validate Your Own Output

A wrong or unsupported finding is worse than a slow one. Before presenting, re-check your output against this list.
Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **`check-id`** from
  [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) (load it if any id is unconfirmed), and
  that id corresponds to what was actually observed — not a near-miss id reused for convenience.
- [ ] Every cited value was **actually observed, not inferred**. "Measured zero" is distinguished from "no
  datapoints", including for the cold-start and backlog signals (load [api-quirks.md](references/api-quirks.md) §3
  if a metric returned nothing); `InService` is never reported as "serving" without a non-zero
  `CurrentInstanceCount` or recent `Invocations` (§1); a `Completed` transform job is reconciled against its output
  count before it is called complete (§4).
- [ ] Any **right-sizing or idle conclusion** cites **both** metric namespaces (`AWS/SageMaker` and
  `/aws/sagemaker/Endpoints`), or discloses that one was unavailable.
- [ ] No severity was invented — each matches the catalog; a tuning/right-sizing threshold AWS does not publish is
  marked `workload-specific` / `INFO`, while a binary failed/absent state keeps its catalog severity.
- [ ] **No mutating API was called or implied as done.** Remediations are phrased as recommendations with the exact
  command for the operator to run.
- [ ] No **raw 12-digit AWS account ID** and no **secret value** (including container env-var values and
  scored-data content) appear anywhere — env vars are referenced by key name only.
- [ ] The endpoints, jobs, regions, S3 prefixes and checks **not** covered are disclosed, with the reason.
- [ ] When a full report is requested, the output follows the template for the area (Step 8).

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call `UpdateEndpoint`, `UpdateEndpointWeightsAndCapacities`, `DeleteEndpoint`,
   `CreateEndpoint` (including serverless/async), `CreateTransformJob`, a scaling mutation
   (`RegisterScalableTarget`, `PutScalingPolicy`), or any other mutating API. Recommend the fix and give the exact
   CLI/IaC command; let the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under review`. If an ARN
   must be quoted as evidence, mask the account segment (`arn:aws:sagemaker:us-east-1:<account>:endpoint/...`,
   `arn:aws:sagemaker:us-east-1:<account>:transform-job/...`). The same applies to anything credential-shaped.
3. **Never disclose secret material.** Report container environment variables, keys, tokens, connection strings,
   and scored-data content by **key name / reference only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish "measured zero"
   from "no data reported" (load [api-quirks.md](references/api-quirks.md) §3 whenever a metric is empty), and
   reconcile a `Completed` transform job against its output object count (§4).
5. **A check-id on every finding.** Each finding references an LLM-SM `check-id` and carries that check's severity
   and AWS-doc citation. No freelance findings. A documented cause from known-causes.md that has no check-id is
   labelled guidance with its citation, not a finding.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`, marked
   `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which endpoints, jobs, regions, or checks you did not
   cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers

- "The endpoint is `InService`, so it's serving traffic and the queue is fine." `InService` is control-plane state; a real-time, async or serverless variant can be `InService` with `CurrentInstanceCount` = 0 (scaled in, scale-to-zero, or a leftover). Confirm a non-zero instance count, recent `Invocations` and, for async, the backlog before calling it healthy (api-quirks §1, LLM-SM-003, LLM-SM-SERVE-004).
- "No datapoints came back, so there are zero errors, no cold start, an empty backlog and a clean run." Absent CloudWatch datapoints mean no traffic or nothing emitted in the window, not a measured zero. A healthy endpoint has datapoints present; an abandoned one has none. Distinguish "zero measured" from "nothing reported" before clearing LLM-SM-SERVE-001 or LLM-SM-SERVE-004, and for a transform job read the logs and the output count too (api-quirks §3).
- "GPU utilization looks low, so this endpoint is over-provisioned." Invocation metrics live in `AWS/SageMaker` and instance resource metrics in `/aws/sagemaker/Endpoints` — a right-sizing conclusion needs both namespaces. Low GPU use alone cannot separate over-provisioned from simply idle (LLM-SM-010, LLM-SM-005).
- "`DescribeScalableTargets` returned empty, so auto-scaling is intentionally off — low severity." On a production variant empty means fixed capacity that cannot absorb spikes or scale in, which is LLM-SM-001 (HIGH). Also confirm the lookup used resource id `endpoint/<name>/variant/<variant>`; a wrong id also returns empty (api-quirks §2).
- "Inference Recommender returned nothing, so the instance type is wrong." In a region that does not support the feature, empty or an error is not evidence of a finding. Record region-unsupported as a disclosed assumption, not an LLM-SM-005 finding.
- "Async failures would show up as errors, so no notification config is fine." Without `OutputConfig.NotificationConfig` SNS success and error topics, callers get no completion signal and failures are silent. That is LLM-SM-SERVE-003 (HIGH), not a cosmetic gap.
- "Throttling means raise `MaxConcurrency` to the maximum." Raising it is only the fix when it is the binding limit. Read the configured value against the observed throttling first, and treat the tuning number as `workload-specific` (LLM-SM-SERVE-002).
- "The job is `Completed`, so every record was scored." `Completed` means the job ran to the end. Batch transform writes one `.out` per input file, only when every record in that file succeeded, so the `.out` count can be short of the input file count. Reconcile with `ListObjectsV2` before clearing it (api-quirks §4, LLM-SM-BATCH-003).
- "It failed, so the model container is broken." A `Failed` job is often an input `ContentType` or `SplitType` mismatch or an S3 access error on the input or output path. Read `FailureReason` and fix the data or role before blaming the container (LLM-SM-BATCH-001).
- "`MaxConcurrentTransforms` is 1, so the job is misconfigured and high severity." It is under-parallelization with a workload-specific threshold, catalogued LOW. Report the observed value against dataset size and do not invent a target (LLM-SM-BATCH-002).
- "A collection call returned AccessDenied, so the check doesn't apply." AccessDenied is a gap, not a clean result. Report the specific API and resource you could not read, continue with the rest, and disclose the gap — never infer the finding either way.

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

Before interpreting any response, consult [api-quirks.md](references/api-quirks.md) — load it before reading any
response that looks clean, empty, `InService` or `Completed`. It enumerates the misleading read-only responses that
cause false positives and false negatives in this review (traps §1–§4):

- **`InService` with `CurrentInstanceCount` = 0** (§1). `EndpointStatus: InService` is control-plane state, **not**
  proof of serving capacity. A variant can be `InService` yet have zero instances (scaled in, scale-to-zero
  async/serverless, or a misconfigured leftover) — exactly the scale-to-zero case the serverless/async checks
  reason about. Always confirm instance count and recent `Invocations` (LLM-SM-003).
- **`DescribeScalableTargets` empty ≠ scaling intentionally off** (§2). On a production variant, empty means **fixed
  capacity** (LLM-SM-001, HIGH). Also confirm the lookup used the right resource id
  (`endpoint/<name>/variant/<variant>`); a wrong id also returns empty.
- **CloudWatch "no datapoints" ≠ a measured zero** (§3). Absent datapoints mean **no traffic or no emission** in the
  window, not a value of zero. This is how you tell a *healthy* endpoint (datapoints present, low errors) from an
  *abandoned* one (no datapoints at all). For error metrics absence is benign; for `Invocations` it points at an
  idle endpoint; an absent `ModelSetupTime` or `ApproximateBacklogSizePerInstance` must not be read as "no cold
  start" or "empty queue".
- **A transform job `Completed` ≠ every record scored** (§4). The output `.out` object count can be short of the
  input file count (one `.out` per fully scored input file); reconcile output against input with `ListObjectsV2` and treat `Completed` as "ran to the
  end", not "scored everything" (LLM-SM-BATCH-003).

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource you could not
read, continue with the rest, and list the gap — never guess. On a **region unsupported for a feature** (e.g.,
Inference Recommender), record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate. On **ambiguous scope**, ask or default to the caller's current region and the
endpoints or jobs in it, and say so.

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
| Output quality, regressions, evaluation jobs (Bedrock or SageMaker), truncation, finish reasons | opsai-ml-eval-check |
| SageMaker training, fine-tuning, Model Registry | opsai-sagemaker-training |

Future price quotes: use the [AWS Pricing Calculator](https://calculator.aws/).

## Appendix — Reference Links

References under `references/`:

- [checks-sagemaker-inference.md](references/checks-sagemaker-inference.md) — load before assigning any check-id or
  severity: the LLM-SM-001..011, LLM-SM-SERVE-* and LLM-SM-BATCH-* check catalog (primary).
- [collection-reference.md](references/collection-reference.md) — load with any Router row, or when you need the
  read-only collection API for endpoints, serverless/async config or transform jobs and the fields each contributes.
- [metrics-and-logs.md](references/metrics-and-logs.md) — load at Step 5, when reading the `AWS/SageMaker` and
  `/aws/sagemaker/Endpoints` metric sets, the serverless/async cold-start and backlog signals, or the transform-job
  describe/log signals.
- [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) — load at Step 7, when comparing the
  alarm set against the recommended real-time, serverless and async alarms and the batch lifecycle rule.
- [api-quirks.md](references/api-quirks.md) — load before interpreting any response that looks clean, empty,
  `InService` or `Completed`: misleading read-only API responses (traps §1–§4).
- [known-causes.md](references/known-causes.md) — load whenever the user names a specific error or symptom:
  documented break-fix causes, each with its AWS-doc citation — real-time (§1–§8: `FailureReason`, the `/ping` and
  port 8080 container contract, artifact S3 and KMS access, VPC endpoint, security group and Availability Zone
  coverage, `ModelError`, multi-model loading, autoscaling policy, zero-downtime updates), capacity versus quota
  (§9), serverless (§10: cold start and Provisioned Concurrency, `MaxConcurrency` and the Regional pool, feature
  exclusions), async (§11: payload and S3 `InputLocation`, `OutputLocation` vs SNS, `sns:Publish`, scale to zero,
  `AsyncInferenceConfig`), and batch transform (§12–§18: JSON Lines and `SplitType`, `ModelClientConfig` timeouts
  and `MaxPayloadInMB`, one file per instance, the `CreateModel` role and KMS key policy, `.out` files and
  transform logs, `DataProcessing` joins, batch vs endpoint).

Output templates under `assets/` (one per area; load the one for the area when a full report is requested):

- [endpoint-health-report-template.md](assets/endpoint-health-report-template.md) — load for a real-time report:
  per-endpoint state, findings with check-ids and severities, right-sizing conclusion citing both namespaces,
  disclosed scope.
- [serverless-async-health-report-template.md](assets/serverless-async-health-report-template.md) — load for a
  serverless/async report: per-endpoint config, signals read, fit decision, findings, disclosed scope.
- [batch-job-health-report-template.md](assets/batch-job-health-report-template.md) — load for a batch transform
  report: per-job state, failure classification, output reconciliation, findings, disclosed scope.

AWS documentation:

- [Real-time inference endpoints](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html)
- [Endpoint auto scaling](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html)
- [Model Monitor](https://docs.aws.amazon.com/sagemaker/latest/dg/model-monitor.html)
- [Production variants / A/B testing](https://docs.aws.amazon.com/sagemaker/latest/dg/model-ab-testing.html)
- [SageMaker CloudWatch metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html)
- [Inference Recommender](https://docs.aws.amazon.com/sagemaker/latest/dg/inference-recommender.html)
- [Host endpoints in a VPC](https://docs.aws.amazon.com/sagemaker/latest/dg/host-vpc.html)
- [Encryption at rest](https://docs.aws.amazon.com/sagemaker/latest/dg/encryption-at-rest.html)
- [Serverless Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html)
- [Asynchronous Inference](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html)
- [Autoscale an async endpoint](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html)
- [Deployment feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html)
- [Batch transform](https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html)
- [Model Registry](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
