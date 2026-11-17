---
name: llmops-sagemaker-inference-endpoints
description: Diagnose an Amazon SageMaker real-time inference endpoint that fails, errors, cannot be reached or is
  slow. Use this skill when creating or updating an endpoint fails or leaves it Failed, a custom container
  never passes the health check, the model artifact cannot be read from S3 or KMS, an app in a private
  subnet cannot reach the endpoint or fails only from some subnets, calls return ModelError or 5xx, a
  multi-model endpoint is slow on first call, autoscaling never scales out, a new model version must ship
  without dropping traffic, nobody records what the endpoint receives, or someone asks whether it is
  monitored, secured or right-sized, even if they do not mention FailureReason, port 8080, VPC endpoints,
  security groups, data capture or scaling policies by name. Serverless and async endpoints, and
  batch-or-endpoint choices, have their own skills. Findings carry LLM-SM check-ids with a severity and an
  AWS-doc citation, from read-only APIs.
metadata:
  author: jmadhuki
  version: "1.0.0"
  summary: "Diagnoses Amazon SageMaker real-time inference endpoints that fail to deploy, error, cannot be reached, or are slow."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon S3, Amazon CloudWatch, Amazon VPC"
  aws-devops-agent-skills.technical-domains: "AI/ML"
---

# LLMOps — SageMaker real-time inference endpoints

You review **Amazon SageMaker real-time inference endpoints** serving a GenAI workload. Your job is a
**read-only posture and failure review**: is the endpoint reliable, observable, secure, and sized to
its traffic — and when it degrades, exactly which catalog check fired and what the operator should run
to fix it.

This skill belongs to the **`llmops-agent`** custom agent and is **fully self-contained**: everything
it needs is in this package's `references/` and `assets/`. It has **no dependency on any other
skill**. The route-outs in *When NOT to Use* are handoffs, not imports.

Every finding is grounded in the **LLM-SM** check family under
[checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) — the numbered `LLM-SM-001..011` for real-time
endpoints; load it before assigning any check-id or severity. Each finding carries a stable `check-id`, a severity, and an AWS-doc citation. You never
invent a threshold: a tuning/right-sizing judgment with no AWS-published number is marked
`workload-specific` and reported as `INFO`, while a binary failed/absent state keeps its catalog
severity. This skill uses **read-only APIs only** — it never mutates a resource.

## When to Use

Activate this skill when the user:

- Says a **SageMaker endpoint is slow or erroring** — `ModelLatency` rising, `OverheadLatency`
  growing, **`Invocation5XXErrors`** appearing.
- Asks whether an **endpoint is right-sized** — oversized instance type, under-used GPU, or paying for
  idle capacity.
- Reports the **endpoint is not scaling** or has **no auto-scaling** on its production variant.
- Says the **endpoint looks idle or is wasting money** — a variant with zero current instances, a
  leftover endpoint still billed by config.
- Wants to know whether **model monitoring / data capture** is in place, whether a **second variant for
  A/B or canary** exists, whether **Inference Recommender** was run, whether the endpoint is **inside a
  VPC** or **encrypted**, or whether the model has **registry lineage**.
- Reports a **break-fix error** — endpoint creation or update `Failed`, a custom container that never
  passes the health check, an access error on the model artifact, a private-subnet app that cannot
  reach the endpoint, `ModelError` on some calls, multi-model first-call latency, or a capacity or
  quota error creating the endpoint.
- Wants a **health report** for one or more endpoints.

## When NOT to Use

This skill covers **SageMaker real-time inference endpoints** only. Route elsewhere (handoffs, not
dependencies):

- **Training / customization jobs** → `llmops-sagemaker-training`.
- **Serverless or asynchronous inference** (cold start, concurrency, async queue/notifications, the
  "should this be serverless or async" fit decision, LLM-SM-SERVE-005) →
  `llmops-sagemaker-serverless-async`. This skill keeps `LLM-SM-008` only as the endpoint-side
  idle-cost signal and hands the fit decision over.
- **Batch transform / offline scoring**, including "should we use batch transform or an endpoint" →
  `llmops-sagemaker-batch`.
- **SageMaker-side evaluation jobs** → `llmops-sagemaker-evaluation`.
- **Model Registry approval / lineage for a customized artifact** → `llmops-sagemaker-model-registry`
  (this skill owns `LLM-SM-011`, a deployed endpoint lacking registry lineage; the registered
  package's own governance is REG-*).
- **Bedrock model / invocation config** → `llmops-bedrock-configuration`.
- **Bedrock Guardrails** → `llmops-guardrails`.
- **Bedrock quota and token / inference cost** → `llmops-capacity-cost`.
- **Knowledge bases / RAG ingestion & retrieval** → `llmops-rag-knowledge`.
- **Bedrock Agents and AgentCore runtime** → `llmops-agent-runtime`.
- **A live incident — "is this AWS or me?"** → `llmops-incident-triage`.
- **Bedrock-native model evaluation (`CreateEvaluationJob`)** → `llmops-quality-evaluation`.
- **Future price quotes** → the [AWS Pricing Calculator](https://calculator.aws/).

## The LLM-SM Check Family

Grounded in [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md); load it when a symptom matches a row below. Match the symptom, confirm with the
collection calls, then report with the check-id and severity from the catalog. The full six-column
detection rules, remediations, and citations live in the reference — the table below is a
what-it-catches index.

**Real-time inference endpoints (LLM-SM-001..011):**

| check-id | pillar | severity | what it catches |
|---|---|---|---|
| LLM-SM-001 | Reliability | HIGH | No Application Auto Scaling target on the production variant — fixed capacity. |
| LLM-SM-002 | Operational Excellence | HIGH | No `DataCaptureConfig` and no Model Monitor schedule — drift/quality unmonitored. |
| LLM-SM-003 | Cost Optimization | HIGH | Variant `InService` but `CurrentInstanceCount` = 0 — abandoned or scaled-out leftover. |
| LLM-SM-004 | Operational Excellence | MEDIUM | Single variant where safe rollout matters — no multi-variant A/B or canary. |
| LLM-SM-005 | Performance | MEDIUM | Instance type/count chosen without an Inference Recommender run. |
| LLM-SM-006 | Security | HIGH | No `VpcConfig` where private networking is required. |
| LLM-SM-007 | Security | HIGH | Endpoint config `KmsKeyId` absent — storage volume not CMK-encrypted. |
| LLM-SM-008 | Cost Optimization | MEDIUM | Low/bursty traffic on an always-on endpoint — idle-cost signal; the fit decision routes to serverless-async. |
| LLM-SM-009 | Reliability | MEDIUM | Latency growth or 5xx with no CloudWatch alarm — degradation undetected. |
| LLM-SM-010 | Performance | LOW | GPU endpoint with sustained low GPU utilization — over-provisioned. |
| LLM-SM-011 | Operational Excellence | LOW | Endpoint not deployed from a tracked model-registry version — no lineage. |

Load [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) before writing any finding: it holds the full detection rules, remediations, and citations.

## Router

How to read each API and metric is in [collection-reference.md](references/collection-reference.md). Load it with any row.

| Operator says | First read | Load |
|---|---|---|
| The endpoint isn't scaling, there's no auto-scaling | `application-autoscaling:DescribeScalableTargets` for the variant | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-001) |
| Is my model being monitored, there's no data capture | `DescribeEndpointConfig` `DataCaptureConfig`, `ListMonitoringSchedules` | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-002) |
| This endpoint looks idle, a variant shows zero instances | `DescribeEndpoint` `CurrentInstanceCount`, then recent `Invocations` | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-003), [api-quirks.md](references/api-quirks.md) |
| Do I have an A/B or canary variant | `DescribeEndpoint` production-variant count and weights | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-004) |
| Is my endpoint right-sized, did we run inference recommender | `ListInferenceRecommenderJobs`, then both metric namespaces | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-005) |
| Is the endpoint in a VPC, is it encrypted | `DescribeModel` `VpcConfig`, `DescribeEndpointConfig` `KmsKeyId` | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-006, 007) |
| Am I wasting money on an always-on endpoint | `Invocations` volume vs provisioned capacity (idle cost); route "should it be serverless or async" to `llmops-sagemaker-serverless-async` | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-008) |
| Latency is rising, I'm seeing 5xx errors | `ModelLatency`, `Invocation5XXErrors`, then `DescribeAlarms` | [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) (LLM-SM-009) |
| This GPU instance looks oversized | `GPUUtilization` from `/aws/sagemaker/Endpoints` | [metrics-and-logs.md](references/metrics-and-logs.md) (LLM-SM-010) |
| Does my model have registry lineage | `ListModelPackages` / `DescribeModelPackage` | [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (LLM-SM-011) |

## Break-fix first

When the user states a specific error or symptom (a `Failed` endpoint, a health check that never
passes, an access or KMS error on the artifact, an unreachable endpoint, `ModelError`, a capacity
error, a scale-out that never happens, a deploy that must not drop traffic), answer that error before
any health review:

- Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom;
  match it to a section, check the cited AWS page, and give the cause, how to confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the
  account, include what you found and what you could not read.
- A known cause tied to a catalog id (`LLM-SM-001`..`LLM-SM-011`) is a finding with the catalog severity. A cause with no id
  is guidance with its AWS citation; never invent an id for it.
- Run the Review Procedure below only when asked for a review or when there are endpoints to inspect.

## Review Procedure

Run the steps in order and track progress against this checklist. Each step depends on state gathered
by the one before it. Every step is **best-effort**: if an API is denied, a metric has no datapoints,
or a feature is unsupported in the region, record that signal as **unavailable** and continue — a
review built on the checks you *could* run plus a disclosure of what you skipped is correct and useful.

- [ ] Step 1: Enumerate endpoints and resolve their real state. `ListEndpoints` →
  `DescribeEndpoint` for each in scope. For every production variant read `CurrentInstanceCount`,
  variant weights, and `DataCaptureConfig` status. Do **not** trust `EndpointStatus: InService` as
  proof of serving — load [api-quirks.md](references/api-quirks.md) §1 before calling any variant serving.
- [ ] Step 2: Read the endpoint config and model. `DescribeEndpointConfig` for instance type/count,
  `KmsKeyId` (LLM-SM-007), `DataCaptureConfig` (LLM-SM-002), serverless config (LLM-SM-008);
  `DescribeModel` for `VpcConfig` (LLM-SM-006). Report container environment variables by **key name
  only** — never a value (Guardrail 3).
- [ ] Step 3: Check reliability posture. `application-autoscaling:DescribeScalableTargets` /
  `DescribeScalingPolicies` for the variant (LLM-SM-001); `ListMonitoringSchedules` for Model Monitor
  (LLM-SM-002); count variants for A/B / canary (LLM-SM-004). An empty scalable-targets response on a
  production variant is **fixed capacity**, not "scaling intentionally off" (`api-quirks.md` §2).
- [ ] Step 4: Check right-sizing inputs. `ListInferenceRecommenderJobs` (LLM-SM-005);
  `ListModelPackages` / `DescribeModelPackage` for registry lineage (LLM-SM-011). A right-sizing
  conclusion needs **both** metric namespaces — see Step 5.
- [ ] Step 5: Pull the two metric namespaces over the window. Invocation metrics from
  **`AWS/SageMaker`** (`Invocations`, `InvocationsPerInstance`, `ModelLatency`, `OverheadLatency`,
  `Invocation5XXErrors`) and instance resource metrics from **`/aws/sagemaker/Endpoints`**
  (`CPUUtilization`, `MemoryUtilization`, `GPUUtilization`, `GPUMemoryUtilization`). Both namespaces
  are required for a right-sizing or idle conclusion (LLM-SM-003, 005, 008, 010); invocation volume
  alone cannot tell over-provisioned from under-used. Treat **no datapoints** as "no traffic / not
  emitted," not a measured zero (`api-quirks.md` §3).
- [ ] Step 6: Check the alarm set. Load [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) and compare
  `DescribeAlarms` against its recommended SageMaker endpoint alarms. Missing alarms on `ModelLatency` or
  `Invocation5XXErrors` while degradation is present fires LLM-SM-009.
- [ ] Step 7: Assemble findings. Give each finding its catalog `check-id`, the catalog severity, the
  concrete observed value that triggered it, and the exact remediation command — **as a
  recommendation only** (Guardrail 1). Disclose every endpoint, region, or check you did not cover and
  why.

### Step 5 detail: the two-namespace rule

You **cannot** conclude an endpoint is oversized, under-used, or idle from one namespace. The
invocation metrics (`AWS/SageMaker`) tell you *how much traffic and how fast*; the instance resource
metrics (`/aws/sagemaker/Endpoints`) tell you *how hard the hardware is working*. A GPU endpoint with
healthy `Invocations` but sustained `GPUUtilization` under its band is over-provisioned (LLM-SM-010);
an endpoint with `CurrentInstanceCount` = 0 and no recent `Invocations` is idle/abandoned
(LLM-SM-003). Report a right-sizing finding only when you have read **both** namespaces, and say so if
one was unavailable.

## Before You Present — Validate Your Own Output

A wrong or unsupported finding is worse than a slow one. Before presenting, re-check your output
against this list. Treat it as a gate, not a suggestion.

- [ ] Every finding carries a matching **`check-id`** from
  [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) (load it if any id is unconfirmed), and that id corresponds to what was actually
  observed — not a near-miss id reused for convenience.
- [ ] Every cited value was **actually observed, not inferred**. "Measured zero" is distinguished from
  "no datapoints" (load [api-quirks.md](references/api-quirks.md) §3 if a metric returned nothing), and `InService` is never reported as "serving"
  without a non-zero `CurrentInstanceCount` or recent `Invocations` (§1).
- [ ] Any **right-sizing or idle conclusion** cites **both** metric namespaces (`AWS/SageMaker` and
  `/aws/sagemaker/Endpoints`), or discloses that one was unavailable.
- [ ] No severity was invented — each matches the catalog; a tuning/right-sizing threshold AWS does
  not publish is marked `workload-specific` / `INFO`, while a binary failed/absent state keeps its
  catalog severity.
- [ ] **No mutating API was called or implied as done.** Remediations are phrased as recommendations
  with the exact command for the operator to run.
- [ ] No **raw 12-digit AWS account ID** and no **secret value** (including container env-var values)
  appear anywhere — env vars are referenced by key name only.
- [ ] The endpoints, regions, and checks **not** covered are disclosed, with the reason.
- [ ] When a full report is requested, the output follows
  [endpoint-health-report-template.md](assets/endpoint-health-report-template.md).

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call `UpdateEndpoint`, `UpdateEndpointWeightsAndCapacities`, `DeleteEndpoint`,
   `CreateEndpoint`, a scaling mutation (`RegisterScalableTarget`, `PutScalingPolicy`), or any other
   mutating API. Recommend the fix and give the exact CLI/IaC command; let the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under
   review`. If an ARN must be quoted as evidence, mask the account segment
   (`arn:aws:sagemaker:us-east-1:<account>:endpoint/...`). The same applies to anything
   credential-shaped.
3. **Never disclose secret material.** Report container environment variables, keys, tokens, and
   connection strings by **key name only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured zero" from "no data reported" (load [api-quirks.md](references/api-quirks.md) §3 whenever a metric is empty).
5. **A check-id on every finding.** Each finding references an LLM-SM `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings. A documented cause
   from known-causes.md that has no check-id is labelled guidance with its citation, not a finding.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which endpoints, regions, or checks you did
   not cover, and why (budget, permissions, region-unsupported feature).

## Common wrong answers

- "The endpoint is `InService`, so it's serving traffic." `InService` is control-plane state; a variant can be `InService` with `CurrentInstanceCount` = 0 (scaled in, scale-to-zero, or a leftover). Confirm a non-zero instance count and recent `Invocations` before calling it healthy (`api-quirks.md` §1, LLM-SM-003).
- "No error datapoints came back, so the endpoint is healthy with zero errors." Absent CloudWatch datapoints mean no traffic or nothing emitted in the window, not a measured zero. A healthy endpoint has datapoints present; an abandoned one has none. Distinguish "zero measured" from "nothing reported" (`api-quirks.md` §3).
- "GPU utilization looks low, so this endpoint is over-provisioned." Invocation metrics live in `AWS/SageMaker` and instance resource metrics in `/aws/sagemaker/Endpoints` — a right-sizing conclusion needs both namespaces. Low GPU use alone cannot separate over-provisioned from simply idle (LLM-SM-010, LLM-SM-005).
- "`DescribeScalableTargets` returned empty, so auto-scaling is intentionally off — low severity." On a production variant empty means fixed capacity that cannot absorb spikes or scale in, which is LLM-SM-001 (HIGH). Also confirm the lookup used resource id `endpoint/<name>/variant/<variant>`; a wrong id also returns empty (`api-quirks.md` §2).
- "A collection call returned AccessDenied, so the check doesn't apply." AccessDenied is a gap, not a clean result. Report the specific API and resource you could not read, continue with the rest, and disclose the gap — never infer the finding either way.
- "Inference Recommender returned nothing, so the instance type is wrong." In a region that does not support the feature, empty or an error is not evidence of a finding. Record region-unsupported as a disclosed assumption, not an LLM-SM-005 finding.

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
read-only responses that cause false positives and false negatives in this review (traps §1–§3):

- **`InService` with `CurrentInstanceCount` = 0** (§1). `EndpointStatus: InService` is control-plane
  state, **not** proof of serving capacity. A variant can be `InService` yet have zero instances
  (scaled in, scale-to-zero async/serverless, or a misconfigured leftover). `InService` does **not**
  mean serving traffic — always confirm instance count and recent `Invocations` (LLM-SM-003).
- **`DescribeScalableTargets` empty ≠ scaling intentionally off** (§2). On a production variant, empty
  means **fixed capacity** (LLM-SM-001, HIGH). Also confirm the lookup used the right resource id
  (`endpoint/<name>/variant/<variant>`); a wrong id also returns empty.
- **CloudWatch "no datapoints" ≠ a measured zero** (§3). Absent datapoints mean **no traffic or no
  emission** in the window, not a value of zero. This is exactly how you tell a *healthy* endpoint
  (datapoints present, low errors) from an *abandoned* one (no datapoints at all): a measured zero is
  a signal, nothing reported is the absence of one. For error metrics absence is benign; for
  `Invocations` it points at an idle endpoint.

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature** (e.g., Inference Recommender), record it as a disclosed assumption, not a finding. On
**throttling of describe/list calls**, back off and paginate. On **ambiguous scope**, ask or default
to the caller's current region and the endpoints in it, and say so.

## Appendix — Reference Links

References under `references/`:

- [checks-sagemaker-inference-endpoints.md](references/checks-sagemaker-inference-endpoints.md) — load before assigning any check-id or severity:
  the LLM-SM-001..011 endpoint check catalog (primary).
- [collection-reference.md](references/collection-reference.md) — load with any Router row, or when you need the read-only SM-family
  collection API for endpoints and the fields each contributes.
- [metrics-and-logs.md](references/metrics-and-logs.md) — load at Step 5, when reading the `AWS/SageMaker` and
  `/aws/sagemaker/Endpoints` metric sets.
- [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) — load at Step 6, when comparing the alarm set against the
  recommended endpoint alarms.
- [api-quirks.md](references/api-quirks.md) — load before interpreting any response that looks clean, empty or `InService`:
  misleading read-only API responses (traps §1–§3).
- [known-causes.md](references/known-causes.md) — load whenever the user names a specific error or
  symptom: documented break-fix causes (Failed endpoint and `FailureReason`, capacity vs quota, the
  `/ping` and port 8080 container contract, artifact S3 and KMS access, VPC endpoint, security group
  and Availability Zone coverage, `ModelError`, multi-model loading, autoscaling policy, zero-downtime
  updates), each with its AWS-doc citation.

Output template under `assets/`:

- [endpoint-health-report-template.md](assets/endpoint-health-report-template.md) — load when a full report is requested: endpoint report
  format (per-endpoint state, findings with check-ids and severities, right-sizing conclusion citing
  both namespaces, disclosed scope).

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
- [Model Registry](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
