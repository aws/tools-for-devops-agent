# Checks — Model Invocation (LLM-INV)

The two model-invocation checks this skill raises: direct model IDs where a cross-region profile exists (capacity spreading) and sustained throttling or quota rejections (capacity pressure). The rest of the LLM-INV family (logging, model access, IAM scope, lifecycle, Converse migration) belongs to `opsai-bedrock-review` and `opsai-bedrock-security` and is never raised here (see `related-skills.md`).

Each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`

Family code: **INV** = model invocation. Family prefix: `LLM-INV-`.

Severity scale: CRITICAL > HIGH > MEDIUM > LOW > INFO. Thresholds without an AWS-published value are marked `workload-specific`.

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-INV-002 | Reliability | HIGH | Application invokes a foundation model by direct model ID (e.g. `anthropic.claude-3-5-sonnet-20241022-v2:0`) rather than a cross-region inference profile ID (e.g. `us.anthropic.claude-3-5-sonnet-...`), and a system-defined profile exists for that model (check `ListInferenceProfiles`; if none exists, do not raise). No automatic cross-region failover or capacity spreading on throttling. | Switch high-throughput, latency-tolerant workloads to a cross-region (system-defined) inference profile so Bedrock routes across regions and absorbs regional throttling. | https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html |
| LLM-INV-007 | Reliability | MEDIUM | Sustained capacity rejections over the evaluation window — `InvocationThrottles` > 0 and/or quota rejections (`InvocationClientErrors` with `errorCode` `ServiceQuotaExceededException`), counted from both the per-`ModelId` and the no-dimension `AWS/Bedrock` series — with no retry-with-backoff and no inference-profile spreading; requests are being dropped. | Implement exponential backoff with jitter, adopt a cross-region inference profile, and if sustained request a quota increase or Provisioned Throughput (see LLM-PT). Quota increases are not granted for models in Legacy or Deprecated status (scheduled for retirement): check the lifecycle status first and migrate to the successor model instead. | https://docs.aws.amazon.com/bedrock/latest/userguide/quotas-runtime.html#quotas-runtime-increase |
