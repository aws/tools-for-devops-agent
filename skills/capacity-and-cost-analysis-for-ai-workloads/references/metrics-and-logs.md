# Metrics & Logs Reference

The CloudWatch metrics and Bedrock invocation-log fields this skill reads for token, cost, Provisioned Throughput and quota analysis. Guardrail, Agents, Knowledge Base, AgentCore and SageMaker metrics belong to the sibling skills in `related-skills.md` and are not listed here.

All metric names are as published by AWS. Thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## AWS/Bedrock — model invocation metrics

Namespace: `AWS/Bedrock`, published by the `bedrock-runtime` endpoint. Dimension: `ModelId` (every metric), plus `ModelId + ContextWindow` for long-context billed requests. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

| Metric | Unit | Meaning (per the reference) | Statistic used here |
|---|---|---|---|
| `Invocations` | Count | Requests Bedrock accepted for processing (Converse, ConverseStream, InvokeModel, InvokeModelWithResponseStream, OpenAI-compatible Responses and Chat Completions). Includes requests that later failed; **excludes** throttled requests and requests rejected in input validation | Sum |
| `InvocationLatency` | Milliseconds | Request sent to last token received | Average, p50/p90/p99 |
| `InvocationClientErrors` | Count | Client-side errors; also counted in `Invocations`. **Includes requests rejected for exceeding a service quota; those are not counted as throttles** | Sum |
| `InvocationServerErrors` | Count | AWS server-side errors; also counted in `Invocations` | Sum |
| `InvocationThrottles` | Count | Throttled invocations. Throttled requests are **not** counted in `Invocations`, `InvocationClientErrors` or `InvocationServerErrors`; the count depends on SDK retry settings | Sum |
| `InputTokenCount` | Count | Tokens in the input (excludes cached tokens) | Sum |
| `OutputTokenCount` | Count | Tokens in the output | Sum |
| `OutputImageCount` | Count | Images generated (image models) | Sum |
| `TimeToFirstToken` | Milliseconds | Request sent to first token, streaming operations only | Average, p90 |
| `CacheReadInputTokenCount` | Count | Input tokens read from the prompt cache: charged at a reduced rate, not counted toward the TPM quota; 0 when caching is not used | Sum |
| `CacheWriteInputTokenCount` | Count | Input tokens written to the prompt cache: count toward the TPM quota; 0 when caching is not used | Sum |
| `LegacyModelInvocations` | Count | Invocations of models with Legacy lifecycle status: signal for LLM-PT-003; no datapoints = no legacy calls | Sum |
| `EstimatedTPMQuotaUsage` | Count | Estimated TPM quota consumption, an approximation that does not reflect the reservation (input tokens + `max_tokens`) that drives throttling; AWS says not to use it as the sole indicator of quota use (`api-quirks.md` §18) | Sum at 60 s period, peak over the trailing 15 days |

Log-delivery metrics, same namespace, dimension `Across all model IDs`: `ModelInvocationLogsCloudWatchDeliverySuccess` / `Failure`, `ModelInvocationLogsS3DeliverySuccess` / `Failure`, `ModelInvocationLargeDataS3DeliverySuccess` / `Failure`. A delivery failure explains an empty log group despite traffic (report it; the logging configuration itself is `opsai-bedrock-review`'s check).

**Dimensions — behaviours that change totals** (same reference):

- Metrics are published **both with and without** `ModelId`. A request that fails before Bedrock determines the target model is published without the dimension, so per-`ModelId` error and throttle counts undercount. Query `InvocationThrottles` and `InvocationClientErrors` without a dimension too.
- `ModelId + ContextWindow` (value `1M`, requests billed at a long-context rate) is a **subset** of the `ModelId` series. Use the `ModelId` series alone for totals; adding both double-counts. Subtract it from the `ModelId` series for standard-context usage.
- One model can appear under several `ModelId` values (short profile ID, profile ARN, foundation-model ARN). Each form carries different traffic: add all forms of a model together.
- CloudWatch keeps 1-minute datapoints for 15 days: take 60 s `EstimatedTPMQuotaUsage` peaks from the trailing 15 days (https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/cloudwatch_concepts.html#Metric).

Token metrics are the primary signal for cost analysis (`cost-analysis.md`). Traffic through the bedrock-mantle endpoint is not here: it publishes to `AWS/BedrockMantle` (`Inferences`, `TotalInputTokens`, `TotalOutputTokens`, `InferenceClientErrors`, by `Model`; https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-mantle-metrics.html), see `api-quirks.md` §20. Batch inference publishes to `AWS/Bedrock/Batch`; Provisioned Throughput traffic appears under the provisioned-model ARN as `ModelId`.

---

## Bedrock invocation logs — fields this skill reads

When model invocation logging is enabled, each record in the CloudWatch log group (or S3 prefix) named by `GetModelInvocationLoggingConfiguration` carries `modelId`, `input.inputTokenCount`, `output.outputTokenCount`, `input.cacheReadInputTokenCount`, `input.cacheWriteInputTokenCount`, `errorCode` (when failed requests are logged) and, for Converse, `output.outputBodyJson.stopReason`. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html. Whether logging is enabled or scoped correctly is `opsai-bedrock-review`'s check; here the logs are only a confirmation signal.

| Pattern / field value | What it indicates | Linked check |
|---|---|---|
| `errorCode` = `ThrottlingException` | Capacity or quota pressure | LLM-INV-007, LLM-PT-002 |
| `errorCode` = `ServiceQuotaExceededException` | Rejected for exceeding a service quota; counted in `InvocationClientErrors`, **not** `InvocationThrottles`; capacity pressure (visible only if rejected requests are logged) | LLM-INV-007, LLM-PT-002 |
| `stopReason` = `max_tokens` on records with a heavy `output.outputTokenCount` tail | Runaway or uncapped generations | LLM-COST-001 |
| `input.cacheReadInputTokenCount` measured 0 with a repeated prefix or a high input floor; or cache writes far above reads | Prompt caching not used, or not paying off | LLM-COST-002 |
| High `input.inputTokenCount` floor (10th percentile) | Candidate for prompt caching | LLM-COST-002 |

`StartQuery` takes Unix epoch seconds (2026-10-15T00:00Z = 1792022400); compute them with a tool. Records start at the log group's `creationTime` (`api-quirks.md` §19).

Error-code query. `errorCode` is absent when failed requests aren't logged, so no rows is **not** a measured 0: compare with `InvocationClientErrors` (in testing: 6 client errors, 0 `errorCode` rows). `guardrail_intervened` is a `stopReason`, not an error.

```
fields @timestamp, modelId, errorCode, input.inputTokenCount, output.outputTokenCount
| filter ispresent(errorCode)
| stats count(*) as errors by errorCode, modelId
| sort errors desc
```

LLM-COST-002 confirmation query, run over the same window as the cost data:

```
stats count(*) as records, sum(ispresent(input.cacheReadInputTokenCount)) as cache_field,
      sum(input.cacheReadInputTokenCount) as cache_read, avg(input.inputTokenCount) as avg_in,
      min(input.inputTokenCount) as min_in, pct(input.inputTokenCount, 10) as p10_in by modelId
```

`cache_field` > 0 with `cache_read` = 0 shows caching is not used. It confirms LLM-COST-002 only with a repeated prefix (next query) or a high floor (`p10_in` at or above the model's minimum cache-checkpoint size); see `cost-analysis.md` §1. A low `min_in`/`p10_in` under a high `avg_in` means mixed prompt sizes.

Repeated-prefix query: `md5` returns a hash, so the prompt text never appears in the results (Converse path; check it with `ispresent()` first):

```
filter ispresent(input.inputBodyJson.system.0.text)
| stats count(*) as calls by modelId, md5(substr(input.inputBodyJson.system.0.text, 0, 2000)) as prefix_hash
| sort calls desc | limit 10
```

A hash on a large share of a model's calls is a repeated prefix. Report counts and shares only, never prompt text.

LLM-COST-001 confirmation query (output tail by stop reason):

```
filter ispresent(output.outputBodyJson.stopReason)
| stats count(*) as records, sum(output.outputTokenCount) as out_tokens,
      pct(output.outputTokenCount, 99) as p99_out, max(output.outputTokenCount) as max_out
      by modelId, output.outputBodyJson.stopReason
| sort out_tokens desc
```

**Check field paths before trusting a total.** A wrong path returns an empty result, not an error, which would wrongly leave LLM-COST-001/002 unconfirmed. Run `stats count(*) as records, sum(ispresent(<field>)) as present` first. Converse records carry the same counts twice: `input.inputTokenCount` / `output.outputTokenCount` / `input.cacheReadInputTokenCount`, and `output.outputBodyJson.usage.inputTokens` / `outputTokens` / `cacheReadInputTokens`. Embedding records have only `input.inputTokenCount`, so prefer the first form. (Verified on 1,317 records: identical totals.)

---

## Finish-reason distribution (LLM-COST-001 signal)

`stopReason` records why the model stopped generating. In Converse invocation logs it sits under `output.outputBodyJson.stopReason` (a top-level `$.stopReason` filter matches nothing); for `InvokeModel` the field name and path are the model provider's, so check one sample record first. Converse values (https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html): `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `guardrail_intervened`, `content_filtered`, `malformed_model_output`, `malformed_tool_use`, `model_context_window_exceeded`.

For this skill only `max_tokens` matters: a shift toward it, **together with** a heavy `output.outputTokenCount` tail made of those records, confirms LLM-COST-001 (`cost-analysis.md` §1). Long outputs that stop on `tool_use` or `end_turn`, or a `max_tokens` share with uniformly small outputs, do not. Output quality and truncation as a quality problem are `opsai-ml-eval-check`'s area.

Metric filter for an alarm on the share of capped generations (threshold `workload-specific`, `cloudwatch-alarm-reference.md`):

```
{ $.output.outputBodyJson.stopReason = "max_tokens" }
```
