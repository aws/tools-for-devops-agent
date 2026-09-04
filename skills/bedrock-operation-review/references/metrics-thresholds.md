# Amazon Bedrock CloudWatch Metrics Thresholds Reference

Metrics are retrieved via `cloudwatch.ListMetrics` (to discover invoked models) and
`cloudwatch.GetMetricData` over the selected window (default 7 days). Severity reflects
sustained values, not single spikes. `cloudwatch.GetMetricData` allows up to 500
metric-data queries per call — batch and paginate for accounts with many models.

## Bedrock Model Metrics (Namespace: `AWS/Bedrock`, Dimension: `ModelId`)

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| Invocations | Sum | baseline | — | — | Volume; denominator for rate calculations |
| InvocationThrottles | Sum | throttle rate ~0% | > 1% of Invocations | > 5% of Invocations | Add retries w/ backoff+jitter, request quota increase, use CRIS |
| InvocationServerErrors | Sum | ~0% | > 2% of Invocations | > 5% of Invocations | Investigate service-side failures / problematic content |
| InvocationClientErrors | Sum | < 1% | > 5% of Invocations | > 15% of Invocations | Bad or blocked input reaching models; add guardrails |
| InvocationLatency | Average | task-dependent | rising trend | sustained high | Use smaller model / streaming; deploy in-region |
| InvocationLatency | p95 | task-dependent | > 2000 ms | > 3000 ms | Latency-sensitive UX risk; distillation candidate |
| TimeToFirstToken | Average, p95 | low | rising | high | Perceived latency — prefer streaming |
| InputTokenCount | Sum | baseline | high | very high | Input-heavy = prompt-caching / distillation candidate |
| OutputTokenCount | Sum | baseline | — | — | Output volume; cost driver |
| InvocationsIntervened | Sum | 5–15% of Invocations | < 5% (under-config) | > 15% (over-tuned) | Review guardrail policy configuration |
| TextUnitCount | Sum | tracked | approaching quota | at quota | Guardrail consumption maps to billing + quota |
| CacheReadInputTokenCount | Sum | present | writes without reads | — | Prompt-cache reads; used for offload % |
| CacheWriteInputTokenCount | Sum | present | high vs reads | — | Prompt-cache writes; used for offload % |

**Derived rates:**
- Throttle rate = `InvocationThrottles / Invocations`
- Server error rate = `InvocationServerErrors / Invocations`
- Client error rate = `InvocationClientErrors / Invocations`
- Intervened rate = `InvocationsIntervened / Invocations`
- Cache offload % = `CacheReadInputTokenCount / (CacheReadInputTokenCount + CacheWriteInputTokenCount) * 100`
- CRIS adoption % = `Profile InputTokenCount / (Profile InputTokenCount + Base Model InputTokenCount) * 100`

## Prompt Caching Status (derived)

| Status | Condition |
|---|---|
| Not Supported | Model not eligible for prompt caching |
| Not Enabled | Caching supported but no cache activity detected |
| Misconfigured | Cache writes occurring but no cache reads (prompts may not share a common prefix) |
| Underutilized | Cache offload % below 50% |
| Optimized | Cache offload % 50% or higher |

`cachingPotential` from output/input ratio: High (< 0.2), Medium (0.2–0.5), Low (> 0.5).

## Service Quota Utilization

| Quota family | Source | Warning | Critical | Finding |
|---|---|---|---|---|
| Model RPM / CRIS RPM / Global CRIS RPM | `servicequotas.GetServiceQuota` vs observed P95 invocations/min | > 75% | sustained near 100% | Request increase; spread load; adopt CRIS |
| Model TPM / CRIS TPM / Global CRIS TPM | `servicequotas.GetServiceQuota` vs observed P95 tokens/min | > 75% | sustained near 100% | Request increase; optimize token usage |
| Guardrail ApplyGuardrail + policy text units | quota vs text-unit consumption | > 75% | near 100% | Request increase; optimize policies; distribute regionally |

> Guardrail CloudWatch metrics do not distinguish Classic vs Standard policy versions.
> When both are configured, utilization can be inaccurate — review manually.

## EC2 GPU Utilization (Namespace: `CWAgent`, NVIDIA DCGM plugin, 7-day min window)

| Signal | Metric | Threshold | Recommendation |
|---|---|---|---|
| Low GPU utilization | `nvidia_smi_utilization_gpu` avg | < 40% | Migrate training to Trainium2 (~30–50% savings) |
| High GPU memory pressure | `nvidia_smi_memory_util` avg | > 90% | Model/tensor parallelism or larger instance (p5en/p6) |
| Bursty / intermittent usage | CV = StdDev/Mean of GPU util | > 0.5 | EC2 Spot Instances (up to 90%) / Capacity Blocks |
| High sustained utilization | `nvidia_smi_utilization_gpu` avg | > 80% | ML Savings Plans / Reserved Instances (up to 64%) |

If "CloudWatch Agent Installed" = No, `nvidia_smi_*` metrics are absent and GPU signals cannot be evaluated.

## Data Automation

| Metric | Production target | Finding |
|---|---|---|
| Success rate | > 95% | Below target → investigate IAM/input/limits |
| Error rate | < 5% | Above → check permissions and input format |
| Throttle rate | < 1% | Above → client-side rate limiting / quota increase |
| Average latency | baseline | Degradation → reduce input size, use async |

## Model Lifecycle (Invoked Model Versions)

| State | Meaning | Action |
|---|---|---|
| Active | Fully supported | No action |
| Legacy | Retirement announced; ≥ 6 months before EOL | MEDIUM — plan upgrade, test new version in non-prod |
| End-of-Life | No longer available | HIGH — migrate immediately |
