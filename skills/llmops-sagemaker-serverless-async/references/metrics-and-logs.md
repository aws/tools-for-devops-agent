# Metrics & Logs Reference

The CloudWatch metric set for SageMaker serverless & asynchronous inference.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## aws/sagemaker/Endpoints — serverless & async inference metrics

Invocation metrics are in `AWS/SageMaker`. Dimensions: `EndpointName`, `VariantName`. Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html

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

Serverless & asynchronous inference signals (`AWS/SageMaker`): `ModelSetupTime` is the **cold-start** signal for serverless and async endpoints — a sustained high value with no Provisioned Concurrency on the `ServerlessConfig` is LLM-SM-SERVE-001. Asynchronous endpoints additionally emit `ApproximateBacklogSizePerInstance` (queue depth, the scaling signal for LLM-SM-SERVE-004) and `ApproximateAgeOfOldestRequest` (how long the oldest queued request has waited); a growing backlog or oldest-request age with no scaling policy means the queue is backing up.
