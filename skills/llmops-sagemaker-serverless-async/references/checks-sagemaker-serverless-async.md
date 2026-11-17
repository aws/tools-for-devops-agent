# Checks — SageMaker serverless & asynchronous inference (LLM-SM-SERVE-*)

Covers Amazon SageMaker serverless and asynchronous inference endpoints serving a GenAI / LLM workload — cold start, concurrency, async queue/notification wiring, and the fit decision.

Each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`

Family code: **SM** = SageMaker for LLMs. Family prefix: `LLM-SM-`; the `LLM-SM-SERVE-*` sub-family covers serverless & asynchronous inference.

Severity scale: CRITICAL > HIGH > MEDIUM > LOW > INFO. A *tuning or right-sizing judgment* with no AWS-published number is marked `workload-specific` at severity INFO; a *binary present/absent/failed* state (a job FAILED, no checkpoint produced, access denied) keeps its catalog severity even when AWS publishes no number.

## Serverless & asynchronous inference (LLM-SM-SERVE-*)

Covers the serverless/async-specific posture the always-on real-time checks (LLM-SM-001..011) cannot — cold start, concurrency, async queue/notification wiring, and the fit decision.

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-SM-SERVE-001 | Performance | MEDIUM | Serverless endpoint shows elevated `ModelSetupTime` (cold-start) in `AWS/SageMaker` with no Provisioned Concurrency configured on the `ServerlessConfig` — first-call latency spikes under bursty traffic. Threshold `workload-specific`. | Set Provisioned Concurrency on the serverless variant sized to the concurrent-request floor, or move latency-critical paths to a real-time endpoint; re-measure `ModelSetupTime`. | https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html |
| LLM-SM-SERVE-002 | Reliability | MEDIUM | Serverless `ServerlessConfig.MaxConcurrency` set at/near the account or config ceiling while invocations are being throttled — concurrency headroom exhausted. Threshold `workload-specific`. | Raise `MaxConcurrency` (within account limits) or add Provisioned Concurrency; if the ceiling is an account quota, request an increase. Confirm throttles are sustained, not a blip. | https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html |
| LLM-SM-SERVE-003 | Reliability | HIGH | Asynchronous endpoint has `AsyncInferenceConfig` present but **no** `OutputConfig.NotificationConfig` (SNS success/error topics) — callers have no completion signal and failures are silent. | Configure `NotificationConfig` with `SuccessTopic` and `ErrorTopic` so completion and failure are observable; verify the endpoint role can publish to the topics. | https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference.html |
| LLM-SM-SERVE-004 | Reliability | MEDIUM | Async endpoint has no scale-to-zero / scaling on the `ApproximateBacklogSizePerInstance` metric — the queue backs up with no instances or pays for idle instances between bursts. Threshold `workload-specific`. | Register Application Auto Scaling on `ApproximateBacklogSizePerInstance` (scale-to-zero supported for async) so instances track queue depth. | https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html |
| LLM-SM-SERVE-005 | Cost Optimization | MEDIUM | Large-payload or long-running LLM inference served on an always-on real-time endpoint where Async (large/long jobs) or Serverless (spiky low-volume) fits better — paying for idle provisioned instances. Owns the serverless/async fit decision, driven by payload size and invocation duration; the real-time idle-cost signal stays LLM-SM-008 in `llmops-sagemaker-inference-endpoints`. Threshold `workload-specific`. | Move large-payload/long-running inference to Asynchronous Inference and spiky low-volume traffic to Serverless; re-validate latency and cost. Complements LLM-SM-008 from the real-time side. | https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html |
