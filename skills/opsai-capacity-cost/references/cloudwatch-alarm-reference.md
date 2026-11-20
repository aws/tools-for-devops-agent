# CloudWatch Alarm Reference

Recommended alarms for Bedrock and SageMaker GenAI workloads with exact settings.

Columns: alarm | namespace / metric | statistic | threshold approach | period | datapoints-to-alarm / evaluation-periods | source.

`source` marks each threshold as:
- **AWS-published** — a numeric threshold AWS documents.
- **Derived** — a defensible default from AWS guidance/general operational practice; tune per workload.
- **Workload-specific** — AWS publishes no number; the operator must set a baseline from observed traffic.

> AWS does not publish fixed numeric alarm thresholds for most Bedrock/SageMaker metrics. The vast majority below are **Derived** or **Workload-specific**. Treat the numbers as starting points, not compliance values.

---

## Bedrock — model invocation alarms

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Server errors present | `AWS/Bedrock` / `InvocationServerErrors` | Sum | `> 0` | 300s | 1 of 1 | Derived |
| Elevated throttling | `AWS/Bedrock` / `InvocationThrottles` (also the no-dimension series) | Sum | `>` baseline (e.g. `>5` sustained) | 300s | 3 of 3 | Derived |
| Client-error surge | `AWS/Bedrock` / `InvocationClientErrors` | Sum | `>` 5% of `Invocations` (metric math) | 300s | 3 of 3 | Derived |
| Latency regression | `AWS/Bedrock` / `InvocationLatency` | p90 | `>` baseline p90 (set from history) | 300s | 3 of 3 | Workload-specific |
| First-token latency (chat) | `AWS/Bedrock` / `TimeToFirstToken` | p90 | `>` UX budget (e.g. 1500 ms) | 300s | 3 of 3 | Workload-specific |
| Quota consumption high | `AWS/Bedrock` / `EstimatedTPMQuotaUsage` (per `ModelId`) | Sum | metric math `100 * m1 / <TPM quota>` `> 80` — `<TPM quota>` read from Service Quotas for that model, matching the `ModelId` form (on-demand / cross-region / global); the metric is an absolute count, not a percentage | 60s | 3 of 3 | Derived |
| Quota rejections present | `AWS/Bedrock` / `InvocationClientErrors` (no dimension) | Sum | `>` baseline; split by invocation-log `errorCode` = `ServiceQuotaExceededException` where logs exist | 300s | 3 of 3 | Workload-specific |
| Token-spend spike | `AWS/Bedrock` / `OutputTokenCount` | Sum | `>` daily baseline (anomaly detection) | 3600s | 1 of 1 | Workload-specific |

Prefer **CloudWatch anomaly detection** bands for `Invocations`, `InputTokenCount`, and `OutputTokenCount` rather than static thresholds — traffic and cost patterns are workload-specific.

`EstimatedTPMQuotaUsage` is an approximation that does not reflect the up-front `max_tokens` reservation that drives throttling (AWS: do not use it as the sole capacity indicator). Pair the quota alarm with the throttling and quota-rejection alarms rather than relying on it alone.

---

## Bedrock Guardrails alarms

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Intervention spike | `AWS/Bedrock/Guardrails` / `InvocationsIntervened` | Sum | `>` baseline (anomaly band) | 300s | 3 of 3 | Workload-specific |
| Guardrail latency add | `AWS/Bedrock/Guardrails` / `InvocationLatency` | p90 | `>` tolerance | 300s | 3 of 3 | Workload-specific |

A sudden rise in `InvocationsIntervened` is both a safety signal (possible attack) and a quality signal (prompt/model regression). Route to a security/on-call channel.

---

## Bedrock Agents alarms

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Agent server errors | `AWS/Bedrock/Agents` / `InvocationServerErrors` | Sum | `> 0` | 300s | 1 of 1 | Derived |
| Agent throttling | `AWS/Bedrock/Agents` / `InvocationThrottles` | Sum | `>` baseline | 300s | 3 of 3 | Derived |
| Agent latency | `AWS/Bedrock/Agents` / `InvocationLatency` | p90 | `>` baseline | 300s | 3 of 3 | Workload-specific |

---

## SageMaker inference endpoint alarms

Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html and https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| 5xx errors | `AWS/SageMaker` / `Invocation5XXErrors` | Sum | `> 0` | 60s | 1 of 1 | Derived |
| Model latency | `AWS/SageMaker` / `ModelLatency` | p90 (µs) | `>` latency SLO | 60s | 3 of 3 | Workload-specific |
| Overhead latency | `AWS/SageMaker` / `OverheadLatency` | p90 (µs) | `>` tolerance | 60s | 3 of 3 | Workload-specific |
| Scaling signal | `AWS/SageMaker` / `InvocationsPerInstance` | Sum/Average | target-tracking target value | 60s | n/a (scaling policy) | Workload-specific |
| CPU saturation | `/aws/sagemaker/Endpoints` / `CPUUtilization` | Average | `> 80%` | 60s | 3 of 3 | Derived |
| Memory saturation | `/aws/sagemaker/Endpoints` / `MemoryUtilization` | Average | `> 80%` | 60s | 3 of 3 | Derived |
| GPU under-use (cost) | `/aws/sagemaker/Endpoints` / `GPUUtilization` | Average | `< 30%` sustained | 300s | 12 of 12 | Workload-specific |

For auto-scaling (LLM-SM-001), use a **target-tracking** policy on `InvocationsPerInstance` rather than a step alarm; set the target from a load test / Inference Recommender run.

---

## Evaluation-quality alarms (custom metrics)

Evaluation scores are not native CloudWatch metrics — publish them (LLM-EVAL-005) then alarm:

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Quality regression | `OpsAI/Evaluation` / `<metric>` (e.g. `Accuracy`) | Average | `<` baseline − margin | per eval run | 1 of 1 | Workload-specific |
| Safety regression | `OpsAI/Evaluation` / `Toxicity` | Average | `>` baseline + margin | per eval run | 1 of 1 | Workload-specific |

Baseline + margin are set by the regression gate (LLM-EVAL-007).
