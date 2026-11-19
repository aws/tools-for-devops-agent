# Metrics & Logs Reference

The exact CloudWatch metric set per resource type for Bedrock + SageMaker GenAI workloads, plus the Bedrock invocation-log error-pattern table.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## AWS/Bedrock — model invocation metrics

Namespace: `AWS/Bedrock`. Common dimensions: `ModelId` (and for some, operation/region). Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-cw.html

| Metric | Unit | Meaning | Typical statistic |
|---|---|---|---|
| `Invocations` | Count | Number of model invocation requests | Sum |
| `InvocationLatency` | Milliseconds | End-to-end latency of an invocation | Average, p50/p90/p99 |
| `InvocationClientErrors` | Count | 4xx-class client errors (bad request, access denied, validation) | Sum |
| `InvocationServerErrors` | Count | 5xx-class server/service errors | Sum |
| `InvocationThrottles` | Count | Requests throttled (quota / capacity) | Sum |
| `InputTokenCount` | Count | Tokens in the input/prompt | Sum, Average |
| `OutputTokenCount` | Count | Tokens generated in the output | Sum, Average |
| `OutputImageCount` | Count | Images generated (image models) | Sum |
| `TimeToFirstToken` | Milliseconds | Latency to first streamed token (streaming calls) | Average, p90 |
| `CacheReadInputTokenCount` | Count | Input tokens served from the prompt cache (0 when caching is not used; excluded from `InputTokenCount` and from TPM quota) | Sum |
| `CacheWriteInputTokenCount` | Count | Input tokens written to the prompt cache (0 when caching is not used; counts toward TPM quota) | Sum |
| `LegacyModelInvocations` | Count | Invocations of models Bedrock has marked legacy — direct signal for LLM-INV-003 / LLM-PT-003; no datapoints = no legacy calls | Sum |
| `EstimatedTPMQuotaUsage` | Count | Estimated tokens-per-minute quota consumption (absolute count, approximation; ÷ Service Quotas TPM limit for share used — see `api-quirks.md` §18) | Sum at 60 s period, peak over window |

**Dimensions — three behaviors that change totals** (source: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html):

- Metrics are published **both with and without** `ModelId`. Requests that fail before Bedrock resolves the model appear only in the dimensionless series, so per-`ModelId` error and throttle counts undercount. Query `InvocationThrottles` and `InvocationClientErrors` without a dimension too.
- `InvocationClientErrors` **includes requests rejected for exceeding a service quota**; those are not counted as throttles. `Invocations` **excludes** throttled requests.
- `ModelId` + `ContextWindow` is a **subset** of the `ModelId` series (long-context billed requests). Use the `ModelId` series alone for totals; adding both double-counts.
- One model can appear under several `ModelId` values (short profile ID, profile ARN, foundation-model ARN). Each form carries different traffic: add all forms of a model together.
- 1-minute data is kept for 15 days only. Take 60 s `EstimatedTPMQuotaUsage` peaks from the last 15 days.

Token metrics (`InputTokenCount` / `OutputTokenCount`) are the primary signal for cost analysis — see `cost-analysis.md`. Traffic through the bedrock-mantle endpoint is not here: it publishes to `AWS/BedrockMantle` (`TotalInputTokens`, `TotalOutputTokens`, `Inferences`, `InferenceClientErrors`, by `Model`) — see `api-quirks.md` §20.

---

## AWS/Bedrock/Guardrails — guardrail metrics

Namespace: `AWS/Bedrock/Guardrails`. Dimensions typically include guardrail identifier/version. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-monitor.html

| Metric | Meaning |
|---|---|
| `InvocationsIntervened` | Count of invocations where the guardrail took action (blocked/masked) |
| `Invocations` | Count of invocations evaluated by the guardrail |
| `InvocationLatency` | Added latency contributed by guardrail evaluation |
| `TextUnitCount` | Text units processed (billing/throughput signal) |

A spike in `InvocationsIntervened` can indicate an attack campaign or a prompt/model regression — alarm on it (see alarm reference).

---

## AWS/Bedrock/Agents — agent metrics

Namespace: `AWS/Bedrock/Agents`. Dimensions include agent id/alias. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-cw.html

| Metric | Meaning |
|---|---|
| `InvocationCount` / `Invocations` | Number of `InvokeAgent` calls |
| `InvocationLatency` | Agent end-to-end orchestration latency |
| `InvocationClientErrors` | Client-side (4xx) errors on agent invoke |
| `InvocationServerErrors` | Server-side (5xx) errors on agent invoke |
| `InvocationThrottles` | Throttled agent invocations |

Zero invocation data over a long window is the signal for the idle-agent check (LLM-AGT-004).

---

## Knowledge Base signals

Knowledge Base ingestion health is read primarily from the data-plane/control-plane APIs (`GetIngestionJob` statistics), not a dedicated CloudWatch namespace. Underlying vector store (e.g., OpenSearch Serverless) exposes its own metrics in `AWS/AOSS`. Retrieval latency surfaces through the invoking agent/application. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html

---

## aws/sagemaker/Endpoints — SageMaker inference metrics

Two namespaces. Invocation metrics are in `AWS/SageMaker`; instance resource metrics are in `/aws/sagemaker/Endpoints`. Dimensions: `EndpointName`, `VariantName`. Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html

Invocation metrics (`AWS/SageMaker`):

| Metric | Unit | Meaning |
|---|---|---|
| `Invocations` | Count | Requests sent to the variant |
| `InvocationsPerInstance` | Count | Invocations normalized per instance (scaling signal) |
| `ModelLatency` | Microseconds | Time the model/container took to respond |
| `OverheadLatency` | Microseconds | SageMaker overhead added to the request |
| `Invocation4XXErrors` | Count | Client errors |
| `Invocation5XXErrors` | Count | Server errors |
| `ModelSetupTime` | Microseconds | Cold-start/model load time (async/serverless) |

Instance resource metrics (`/aws/sagemaker/Endpoints`):

| Metric | Meaning |
|---|---|
| `CPUUtilization` | CPU across the container(s) |
| `MemoryUtilization` | Memory utilization |
| `DiskUtilization` | Storage volume utilization |
| `GPUUtilization` | GPU compute utilization (GPU instances) |
| `GPUMemoryUtilization` | GPU memory utilization (GPU instances) |

---

## Bedrock invocation-log error-pattern table

When model invocation logging is enabled (LLM-INV-001), scan the delivered logs (CloudWatch Logs Insights over the Bedrock log group, or Athena over the S3 destination) for these patterns. Each log record contains `input`, `output`, `errorCode`, token counts, model ID, and timestamps.

| Pattern / field value | What it indicates | Linked check |
|---|---|---|
| `ThrottlingException` / `errorCode` throttle | Capacity/quota pressure; consider inference profile or PT | LLM-INV-007, LLM-PT |
| `ServiceQuotaExceededException` | Request rejected for exceeding a service quota — counted in `InvocationClientErrors`, **not** `InvocationThrottles`; treat as capacity pressure (only visible here if logs record rejected requests) | LLM-INV-007, LLM-PT-002 |
| `AccessDeniedException` | Model access not granted or IAM too narrow | LLM-INV-004 |
| `ValidationException` | Malformed request / unsupported parameter / context too long | LLM-INV-011 |
| `ModelErrorException` / `ModelNotReadyException` | Model-side failure or warm-up | LLM-INV-005 |
| `ServiceUnavailableException` / 5xx | Transient service errors; needs retry/backoff | LLM-INV-007 |
| High `inputTokenCount` outliers | Prompt bloat / unbounded context — cost + latency | LLM-COST, LLM-INV-011 |
| High `outputTokenCount` outliers | Runaway generations / missing `maxTokens` | LLM-INV-011 |
| `stopReason` = `guardrail_intervened` (a stop reason, not an `errorCode`) | Guardrail actively blocking — review for attack vs false-positive | LLM-GRD-002 |
| Missing/empty log stream despite traffic | Logging misconfigured or delivery failing | LLM-INV-001, LLM-INV-005 |
| Deprecated `modelId` appearing in records | Still invoking an end-of-life model | LLM-INV-003 |

`StartQuery` takes Unix epoch seconds (2026-10-15T00:00Z = 1792022400); compute them with a tool.

Example CloudWatch Logs Insights query to surface error codes. `errorCode` is absent when failed requests aren't logged, so no rows is **not** a measured 0: compare with `InvocationClientErrors` (in testing: 6 client errors, 0 `errorCode` rows). `guardrail_intervened` is a `stopReason`, not an error.

```
fields @timestamp, modelId, errorCode, input.inputTokenCount, output.outputTokenCount
| filter ispresent(errorCode)
| stats count(*) as errors by errorCode, modelId
| sort errors desc
```

Cache tokens in logs: `input.cacheReadInputTokenCount`, `input.cacheWriteInputTokenCount`. LLM-COST-002 confirmation query, run over the same window as the cost data:

```
stats count(*) as records, sum(ispresent(input.cacheReadInputTokenCount)) as cache_field,
      sum(input.cacheReadInputTokenCount) as cache_read, avg(input.inputTokenCount) as avg_in,
      min(input.inputTokenCount) as min_in, pct(input.inputTokenCount, 10) as p10_in by modelId
```

`cache_field` > 0 with `cache_read` = 0 shows caching is not used. It confirms LLM-COST-002 only with a repeated prefix (next query) or a high floor (`p10_in` at or above the model's minimum cache-checkpoint size); see cost-analysis.md §1. A low `min_in`/`p10_in` under a high `avg_in` means mixed prompt sizes.

Repeated-prefix query: `md5` returns a hash, so the prompt text never appears in the results (Converse path; check it with `ispresent()` first):

```
filter ispresent(input.inputBodyJson.system.0.text)
| stats count(*) as calls by modelId, md5(substr(input.inputBodyJson.system.0.text, 0, 2000)) as prefix_hash
| sort calls desc | limit 10
```

A hash on a large share of a model's calls is a repeated prefix. Report counts and shares only, never prompt text.

**Check field paths before trusting a total.** A wrong path returns an empty result, not an error, which would wrongly leave LLM-COST-001/002 unconfirmed. Run `stats count(*) as records, sum(ispresent(<field>)) as present` first. Converse records carry the same counts twice: `input.inputTokenCount` / `output.outputTokenCount` / `input.cacheReadInputTokenCount`, and `output.outputBodyJson.usage.inputTokens` / `outputTokens` / `cacheReadInputTokens`. Embedding records have only `input.inputTokenCount`, so prefer the first form. (Verified on 1,317 records: identical totals.)

---

## Finish-reason distribution (quality signal)

The `stopReason` field in Bedrock invocation logs (Converse: `output.outputBodyJson.stopReason`; check one sample record, the path varies by API) records why the model stopped generating. Possible values: `end_turn` (natural completion), `max_tokens` (hit the token limit), `stop_sequence` (hit a stop sequence), `tool_use` (invoked a tool), `guardrail_intervened` (guardrail blocked).

A shift in the distribution of `stopReason` from `end_turn` toward `max_tokens` is an early indicator that outputs are being truncated — either because prompts grew longer (crowding the output budget), because `maxTokens` was reduced, or because a model version change altered generation behavior. This signal precedes visible quality complaints by hours or days.

Recommended metric filter (CloudWatch Logs):
```
{ $.output.outputBodyJson.stopReason = "max_tokens" }
```
Publish as a custom metric (e.g., `LLMOps/FinishReason/MaxTokens` with dimension `ModelId`) and alarm when the 1-hour rate exceeds the baseline by >10 percentage points. See LLM-TEL-002 and LLM-EVAL-012.

## Telemetry coverage signals

Beyond the per-service metrics above, the strategy requires verifying stage-level telemetry across the agent processing pipeline:

| Stage | What to look for | Source |
|---|---|---|
| Retrieval (KB/RAG) | Retrieval latency, documents returned, relevance scores | AgentCore OTLP spans or application logs |
| Inference (model call) | Model latency, token counts, finish reason | AWS/Bedrock metrics + invocation logs |
| Tool execution | Tool call latency, success/failure per tool | AgentCore OTLP spans |
| Response generation | Post-processing latency, guardrail eval time | AWS/Bedrock/Guardrails metrics |
| End-to-end | Total session latency, trace propagation | AgentCore Observability |

If any stage is invisible (no metrics, no spans, no logs), the operator cannot isolate where slowness or failure originates. See LLM-TEL-001 and LLM-AC-005.
