# CloudWatch Alarm Reference

Recommended alarms for Bedrock token spend, quota use and throttling (SKILL.md Step 7). Guardrail, Agents, SageMaker and evaluation-quality alarms belong to the sibling skills in `related-skills.md`.

Columns: alarm | namespace / metric | statistic | threshold approach | period | datapoints-to-alarm / evaluation-periods | source.

`source` marks each threshold as:
- **AWS-published** — a numeric threshold AWS documents.
- **Derived** — a defensible default from AWS guidance or general operational practice (for example "any server error"); tune per workload.
- **Workload-specific** — AWS publishes no number; the operator sets a baseline from observed traffic. A figure in brackets is an illustration of the form, not a recommended value.

> AWS publishes no fixed numeric alarm thresholds for Bedrock metrics. Every row below is **Derived** or **Workload-specific**; present the numbers as starting points, never as compliance values, and name the source class next to each one (SKILL.md "Guardrails — details", Thresholds).

Metric reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html. Alarm mechanics: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Alarms.html.

---

## Bedrock — capacity and throttling alarms

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Elevated throttling | `AWS/Bedrock` / `InvocationThrottles` (per `ModelId` **and** the no-dimension series) | Sum | `> 0` sustained; raise the threshold to the observed retry-absorbed baseline | 300s | 3 of 3 | Derived |
| Quota rejections present | `AWS/Bedrock` / `InvocationClientErrors` (no dimension) | Sum | `>` baseline; split by invocation-log `errorCode` = `ServiceQuotaExceededException` where logs exist, because quota rejections are counted here and not in `InvocationThrottles` | 300s | 3 of 3 | Workload-specific |
| Quota consumption high | `AWS/Bedrock` / `EstimatedTPMQuotaUsage` (per `ModelId`) | Sum | metric math `100 * m1 / <TPM quota>` `> <percent>` (80 is a common starting point); `<TPM quota>` read from Service Quotas for that model and form (on-demand / cross-region / global, `api-quirks.md` §18); the metric is an absolute count, not a percentage | 60s | 3 of 3 | Workload-specific |
| Server errors present | `AWS/Bedrock` / `InvocationServerErrors` | Sum | `> 0` | 300s | 1 of 1 | Derived |

`EstimatedTPMQuotaUsage` is an approximation that does not reflect the up-front input + `max_tokens` reservation that drives throttling (AWS: do not use it as the sole indicator of quota use). Pair the quota alarm with the throttling and quota-rejection alarms rather than relying on it alone. Models on the bedrock-mantle endpoint publish no throttle or quota metric (`api-quirks.md` §20): no alarm covers their rejections.

---

## Bedrock — token spend alarms

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Output-token spike | `AWS/Bedrock` / `OutputTokenCount` (per `ModelId`) | Sum | anomaly-detection band, or `>` the observed daily baseline | 3600s | 1 of 1 | Workload-specific |
| Input-token spike | `AWS/Bedrock` / `InputTokenCount` (per `ModelId`) | Sum | anomaly-detection band | 3600s | 1 of 1 | Workload-specific |
| Cache not paying off | metric math `CacheWriteInputTokenCount / CacheReadInputTokenCount` (per `ModelId`) | Sum | `>` the ratio at which the model's write and read rates stop saving money (price them per `cost-analysis.md` §1b) | 86400s | 1 of 1 | Workload-specific |
| Capped generations | custom metric from the metric filter `{ $.output.outputBodyJson.stopReason = "max_tokens" }` on the invocation log group (`metrics-and-logs.md`) | Sum | `>` baseline share of records | 3600s | 3 of 3 | Workload-specific |
| Legacy-model traffic | `AWS/Bedrock` / `LegacyModelInvocations` | Sum | `> 0` | 3600s | 1 of 1 | Derived |

Prefer **CloudWatch anomaly detection** bands for `Invocations`, `InputTokenCount` and `OutputTokenCount` over static thresholds: traffic and cost patterns are workload-specific. For spend itself, recommend an AWS Budgets cost budget filtered to the Bedrock service names read in Step 3 (https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-create.html); Cost Explorer figures lag CloudWatch by up to a day, so a token alarm fires first.
