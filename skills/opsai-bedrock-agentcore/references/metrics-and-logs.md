# Metrics & Logs Reference

The exact CloudWatch metric set per resource type for Bedrock + SageMaker GenAI workloads, plus the Bedrock invocation-log error-pattern table.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## AWS/Bedrock — model invocation metrics

Namespace: `AWS/Bedrock`. Common dimensions: `ModelId` (and for some, operation/region). Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

| Metric | Unit | Meaning | Typical statistic |
|---|---|---|---|
| `Invocations` | Count | Number of model invocation requests | Sum |
| `InvocationLatency` | Milliseconds | End-to-end latency of an invocation | Average, p50/p90/p99 |
| `InvocationClientErrors` | Count | 4xx-class client errors (bad request, access denied, validation), including requests rejected for exceeding a service quota. Throttled requests are **not** counted here | Sum |
| `InvocationServerErrors` | Count | 5xx-class server/service errors. Throttled requests are **not** counted here | Sum |
| `InvocationThrottles` | Count | Requests throttled. Counted only here, not in `Invocations`, `InvocationClientErrors` or `InvocationServerErrors`, so an error total or a per-code reconciliation must add this metric | Sum |
| `InputTokenCount` | Count | Tokens in the input/prompt | Sum, Average |
| `OutputTokenCount` | Count | Tokens generated in the output | Sum, Average |
| `OutputImageCount` | Count | Images generated (image models) | Sum |
| `TimeToFirstToken` | Milliseconds | Latency to first streamed token (streaming calls) | Average, p90 |
| `EstimatedTPMQuotaUsage` | Count | Estimated tokens-per-minute quota consumption across `Converse`, `ConverseStream`, `InvokeModel` and `InvokeModelWithResponseStream`; an approximation in tokens, not a percentage. There is no `EstimatedQuotaConsumption` metric | Sum |

Token metrics (`InputTokenCount` / `OutputTokenCount`) are the primary signal for cost analysis — see `cost-analysis.md`.

---

## AWS/Bedrock/Guardrails — guardrail metrics

Namespace: `AWS/Bedrock/Guardrails`. Dimensions typically include guardrail identifier/version. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html

| Metric | Meaning |
|---|---|
| `InvocationsIntervened` | Count of invocations where the guardrail took action (blocked/masked) |
| `Invocations` | Count of invocations evaluated by the guardrail |
| `InvocationLatency` | Added latency contributed by guardrail evaluation |
| `TextUnitCount` | Text units processed (billing/throughput signal) |

A spike in `InvocationsIntervened` can indicate an attack campaign or a prompt/model regression — alarm on it (see alarm reference).

---

## AWS/Bedrock/Agents — agent metrics

Namespace: `AWS/Bedrock/Agents`. Dimensions include agent id/alias. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-agents-cw-metrics.html

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

Knowledge Base ingestion health is read primarily from the data-plane/control-plane APIs (the per-job `statistics` in `bedrock:ListIngestionJobs`), not a dedicated CloudWatch namespace. Underlying vector store (e.g., OpenSearch Serverless) exposes its own metrics in `AWS/AOSS`. Retrieval latency surfaces through the invoking agent/application. References: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html (ingestion), https://docs.aws.amazon.com/opensearch-service/latest/developerguide/monitoring-cloudwatch.html (`AWS/AOSS`)

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
| `AccessDeniedException` | Model access not granted or IAM too narrow | LLM-INV-004 |
| `ValidationException` | Malformed request / unsupported parameter / context too long | LLM-INV-011 |
| `ModelErrorException` / `ModelNotReadyException` | Model-side failure or warm-up | LLM-INV-005 |
| `ServiceUnavailableException` / 5xx | Transient service errors; needs retry/backoff | LLM-INV-007 |
| High `inputTokenCount` outliers | Prompt bloat / unbounded context — cost + latency | LLM-COST, LLM-INV-011 |
| High `outputTokenCount` outliers | Runaway generations / missing `maxTokens` | LLM-INV-011 |
| Guardrail `intervened`/blocked markers in output | Guardrail actively blocking — review for attack vs false-positive | LLM-GRD-002 |
| Missing/empty log stream despite traffic | Logging misconfigured or delivery failing | LLM-INV-001, LLM-INV-005 |
| Deprecated `modelId` appearing in records | Still invoking an end-of-life model | LLM-INV-003 |

Example CloudWatch Logs Insights query to surface error codes:

```
fields @timestamp, modelId, errorCode, input.inputTokenCount, output.outputTokenCount
| filter ispresent(errorCode)
| stats count(*) as errors by errorCode, modelId
| sort errors desc
```

---

## Finish-reason distribution (quality signal)

The `stopReason` field records why the model stopped generating. In Converse invocation logs it sits under `output.outputBodyJson.stopReason` ([model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)). The Converse API defines nine values ([Converse](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)): `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `guardrail_intervened`, `content_filtered`, `malformed_model_output`, `malformed_tool_use` and `model_context_window_exceeded`.

A shift in the distribution of `stopReason` from `end_turn` toward `max_tokens` is an early indicator that outputs are being truncated — either because prompts grew longer (crowding the output budget), because `maxTokens` was reduced, or because a model version change altered generation behavior. This signal precedes visible quality complaints by hours or days.

Recommended metric filter (CloudWatch Logs):
```
{ $.output.outputBodyJson.stopReason = "max_tokens" }
```
Publish as a custom metric (e.g., `OpsAI/FinishReason/MaxTokens` with dimension `ModelId`) and alarm when the 1-hour rate exceeds the baseline by >10 percentage points. See LLM-TEL-002 and LLM-EVAL-012.

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
