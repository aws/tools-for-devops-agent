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
| `InvocationClientErrors` | Count | 4xx-class client errors (bad request, access denied, validation) | Sum |
| `InvocationServerErrors` | Count | 5xx-class server/service errors | Sum |
| `InvocationThrottles` | Count | Requests throttled (quota / capacity) | Sum |
| `InputTokenCount` | Count | Tokens in the input/prompt | Sum, Average |
| `OutputTokenCount` | Count | Tokens generated in the output | Sum, Average |
| `OutputImageCount` | Count | Images generated (image models) | Sum |
| `TimeToFirstToken` | Milliseconds | Latency to first streamed token (streaming calls) | Average, p90 |
| `EstimatedQuotaConsumption` | Count/percent | Estimated consumption against the invocation quota | Maximum |

Token metrics (`InputTokenCount` / `OutputTokenCount`) are the primary signal for cost analysis — see `cost-analysis.md`.

---

## AWS/Bedrock/Guardrails — guardrail metrics

Namespace: `AWS/Bedrock/Guardrails`. Dimensions: `GuardrailArn` + `GuardrailVersion` (version number or `DRAFT`), `Operation` (`ApplyGuardrail`), `GuardrailContentSource` (`Input` / `Output`), `GuardrailPolicyType` (`ContentPolicy`, `TopicPolicy`, `WordPolicy`, `SensitiveInformationPolicy`, `ContextualGroundingPolicy`). `Invocations` by `GuardrailArn` + `GuardrailVersion` is the per-version traffic read in the Guardrails section of `guardrails-collection-reference.md` (row (d)). Series that carry `GuardrailArn` carry only `GuardrailArn` + `GuardrailVersion`; series with `Operation`, `GuardrailContentSource` or `GuardrailPolicyType` carry no `GuardrailArn`, so they are account-wide, and the `Operation` series also counts inline evaluations (measured on `Converse`), not only standalone `ApplyGuardrail` calls. Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html

| Metric | Meaning |
|---|---|
| `InvocationsIntervened` | AWS: "Number of invocations where the guardrails intervened". Read here as the guardrail evaluations where it intervened (blocked or masked), in the same unit as `Invocations`, so not a count of model calls |
| `Invocations` | AWS: "Number of requests to the ApplyGuardrail API operation". Measured on non-streaming inline `Converse`, one model, one Region, it counted guardrail evaluations, not model calls: an allowed call counted 2, a call blocked at the input counted 1 |
| `InvocationLatency` | AWS defines it as the time from when a request is sent to when the last token is received. AWS does not document it as only the latency the guardrail adds (`documented-behavior.md` §3) |
| `TextUnitCount` | Text units processed (billing/throughput signal) |

A spike in `InvocationsIntervened` can indicate an attack campaign or a prompt/model regression — alarm on it (see alarm reference).

**Intervention rate.** Divide `InvocationsIntervened` by `Invocations` for the same `GuardrailArn`, `GuardrailVersion` and window, and write it as "x of y evaluations", never "x of y calls": `Invocations` counts guardrail evaluations (an allowed non-streaming inline `Converse` call counted as two when measured, on one model in one Region; other paths were not measured) and `InvocationsIntervened` counts the ones where the guardrail intervened. Lead with that rate. A per-call rate taken from logs (requests with `stopReason` `guardrail_intervened` over requests) has a different denominator; if you give one, label it and keep the two apart.

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
| `AccessDeniedException` | Model access not granted or IAM too narrow | LLM-INV-004 |
| `ValidationException` | Malformed request / unsupported parameter / context too long | LLM-INV-011 |
| `ModelErrorException` / `ModelNotReadyException` | Model-side failure or warm-up | LLM-INV-005 |
| `ServiceUnavailableException` / 5xx | Transient service errors; needs retry/backoff | LLM-INV-007 |
| High `inputTokenCount` outliers | Prompt bloat / unbounded context — cost + latency | LLM-COST, LLM-INV-011 |
| High `outputTokenCount` outliers | Runaway generations / missing `maxTokens` | LLM-INV-011 |
| Guardrail `intervened`/blocked markers in output | Guardrail actively blocking — review for attack vs false-positive | LLM-GRD-002 |
| A guardrail id under `inputAssessment` holding only `appliedGuardrailDetails` and `invocationMetrics` | Normal when nothing was detected. The guardrail was applied to that side; the entry does not show which policy ran. Read the `detected` booleans and `usage` integers, not the key (`guardrails-api-quirks.md` §18) | none: not a finding by itself |
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

The `stopReason` field in Bedrock invocation logs records why the model stopped generating. Possible values: `end_turn` (natural completion), `max_tokens` (hit the token limit), `stop_sequence` (hit a stop sequence), `tool_use` (invoked a tool), `guardrail_intervened` (guardrail blocked).

A shift in the distribution of `stopReason` from `end_turn` toward `max_tokens` is an early indicator that outputs are being truncated — either because prompts grew longer (crowding the output budget), because `maxTokens` was reduced, or because a model version change altered generation behavior. This signal precedes visible quality complaints by hours or days.

Recommended metric filter (CloudWatch Logs):
```
{ $.stopReason = "max_tokens" }
```
Publish as a custom metric (e.g., `OpsAI/FinishReason/MaxTokens` with dimension `ModelId`) and alarm when the 1-hour rate exceeds the baseline by >10 percentage points. See LLM-TEL-002 and LLM-EVAL-012.

## Telemetry coverage signals

Beyond the per-service metrics above, the strategy requires verifying stage-level telemetry across the agent processing pipeline:

| Stage | What to look for | Source |
|---|---|---|
| Retrieval (KB/RAG) | Retrieval latency, documents returned, relevance scores | AgentCore OTLP spans or application logs |
| Inference (model call) | Model latency, token counts, finish reason | AWS/Bedrock metrics + invocation logs |
| Tool execution | Tool call latency, success/failure per tool | AgentCore OTLP spans |
| Response generation | Post-processing latency; guardrail processing time per call (trace `invocationMetrics.guardrailProcessingLatency`, unit not given); guardrail `InvocationLatency` is request to last token, not only the guardrail's share | AWS/Bedrock/Guardrails metrics, guardrail trace |
| End-to-end | Total session latency, trace propagation | AgentCore Observability |

If any stage is invisible (no metrics, no spans, no logs), the operator cannot isolate where slowness or failure originates. See LLM-TEL-001 and LLM-AC-005.
