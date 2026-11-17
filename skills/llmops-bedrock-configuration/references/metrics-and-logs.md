# Metrics & Logs Reference

The exact CloudWatch metric set per resource type for Bedrock + SageMaker GenAI workloads, plus the Bedrock invocation-log error-pattern table.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; alarm thresholds are not part of this skill (the llmops-capacity-cost skill carries the alarm reference).

---

## AWS/Bedrock — model invocation metrics

Namespace: `AWS/Bedrock`. Dimensions: `ModelId`; `ModelId + ContextWindow`; `ModelId + ImageSize + BucketedStepSize`. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

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
| `EstimatedTPMQuotaUsage` | Count | Estimated tokens-per-minute quota consumption — an absolute count and an approximation, **not** a percentage. There is no `EstimatedQuotaConsumption` metric | Sum at 60 s |
| `LegacyModelInvocations` | Count | Invocations of Legacy models — direct signal for LLM-INV-003 | Sum |
| `CacheReadInputTokenCount` / `CacheWriteInputTokenCount` | Count | Prompt-cache read / write tokens | Sum |

Log-delivery metrics (dimension `Across all model IDs`), for LLM-INV-005: `ModelInvocationLogsCloudWatchDeliverySuccess` / `...Failure`, `ModelInvocationLogsS3DeliverySuccess` / `...Failure`, `ModelInvocationLargeDataS3DeliverySuccess` / `...Failure`.

Counting rules (same reference):

- Metrics are published **with and without** `ModelId`. Requests that fail before Bedrock resolves the model appear only without it, so query error and throttle metrics with no dimension too.
- `Invocations` excludes throttled requests and requests rejected at input validation. `InvocationClientErrors` includes requests rejected for exceeding a service quota; those are not throttles.
- `ModelId + ContextWindow` is a subset of the `ModelId` series; use `ModelId` alone for totals.
- One model can appear under several `ModelId` values (short id, foundation-model ARN, profile id, profile ARN). Add the forms together.

Token metrics (`InputTokenCount` / `OutputTokenCount`) are the primary signal for cost analysis, which the llmops-capacity-cost skill performs.

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

When model invocation logging is enabled (LLM-INV-001), scan the delivered logs (CloudWatch Logs Insights over the Bedrock log group, or Athena over the S3 destination). The documented record carries `schemaType`, `timestamp`, `region`, `requestId`, `operation`, `modelId`, `identity.arn`, `requestMetadata`, `input.inputBodyJson`, `input.inputTokenCount`, `output.outputBodyJson`, `output.outputTokenCount` (https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html). **It has no `errorCode` field** (0 of 2,745 records in testing), so the logs are a source for usage patterns, not for errors: take error counts from `InvocationClientErrors` / `InvocationServerErrors` / `InvocationThrottles`. Verify any field with `ispresent()` before relying on it. The error rows below apply only to error text you were given (a pasted message, an SDK log).

| Pattern / field value | What it indicates | Linked check |
|---|---|---|
| `ThrottlingException` / `errorCode` throttle | Capacity/quota pressure; consider inference profile or PT | LLM-INV-007, LLM-PT |
| `AccessDeniedException` | IAM deny, SCP deny, model access, or an end-of-life model — classify by the message clause | LLM-INV-013 / 015 / 014 / 003 |
| `ValidationException` | Malformed request / unsupported parameter / context too long | LLM-INV-011 |
| `ModelErrorException` / `ModelNotReadyException` | Model-side failure or warm-up | LLM-INV-005 |
| `ServiceUnavailableException` / 5xx | Transient service errors; needs retry/backoff | LLM-INV-007 |
| High `inputTokenCount` outliers | Prompt bloat / unbounded context — cost + latency | LLM-COST, LLM-INV-011 |
| High `outputTokenCount` outliers | Runaway generations / missing `maxTokens` | LLM-INV-011 |
| `output.outputBodyJson.stopReason` = `guardrail_intervened` (a stop reason, not an error) | Guardrail actively blocking — review for attack vs false-positive | LLM-GRD-002 |
| Missing/empty log stream despite traffic | Logging misconfigured or delivery failing | LLM-INV-001, LLM-INV-005 |
| Deprecated `modelId` appearing in records | Still invoking an end-of-life model | LLM-INV-003 |

Example CloudWatch Logs Insights queries over the invocation log group:

```
stats count(*) as calls by operation, modelId | sort calls desc
```

```
stats count(*) as total,
      sum(ispresent(input.inputBodyJson.inferenceConfig.maxTokens)) as capped,
      sum(ispresent(output.outputBodyJson.stopReason)) as has_stop
  by modelId
```

---

## Finish-reason distribution (quality signal)

The `stopReason` field records why the model stopped generating. In invocation logs it sits at `output.outputBodyJson.stopReason` (Converse responses; native-API bodies differ by provider), not at the top level. Converse values: `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `guardrail_intervened`, `content_filtered`.

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
