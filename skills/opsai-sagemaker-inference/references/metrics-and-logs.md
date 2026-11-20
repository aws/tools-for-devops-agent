# Metrics & Logs Reference

The CloudWatch metric set and job signals for SageMaker real-time, serverless and asynchronous inference endpoints and batch transform jobs.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds live in `cloudwatch-alarm-reference.md`, not here.

---

## 1. Real-time endpoint metrics (AWS/SageMaker and /aws/sagemaker/Endpoints)

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
| `ModelSetupTime` | Microseconds | Time to launch new compute resources for a serverless endpoint (serverless cold start) |

Instance resource metrics (`/aws/sagemaker/Endpoints`):

| Metric | Meaning |
|---|---|
| `CPUUtilization` | CPU across the container(s) |
| `MemoryUtilization` | Memory utilization |
| `DiskUtilization` | Storage volume utilization |
| `GPUUtilization` | GPU compute utilization (GPU instances) |
| `GPUMemoryUtilization` | GPU memory utilization (GPU instances) |

## 2. Serverless and asynchronous inference signals

Serverless and asynchronous endpoints emit the same invocation metrics in `AWS/SageMaker` (table in §1). Dimensions: `EndpointName`, `VariantName`. Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html

Serverless & asynchronous inference signals (`AWS/SageMaker`): `ModelSetupTime` is the **cold-start** signal for serverless endpoints — a sustained high value with no Provisioned Concurrency on the `ServerlessConfig` is LLM-SM-SERVE-001; `OverheadLatency` also tracks serverless cold start. AWS documents `ModelSetupTime` for serverless endpoints; for async cold starts read `ApproximateBacklogSizePerInstance`/`ApproximateAgeOfOldestRequest` and the container log. Asynchronous endpoints additionally emit `ApproximateBacklogSizePerInstance` (queue depth, the scaling signal for LLM-SM-SERVE-004) and `ApproximateAgeOfOldestRequest` (how long the oldest queued request has waited); a growing backlog or oldest-request age with no scaling policy means the queue is backing up.

## 3. Batch transform job signals

Transform jobs are **one-shot** (they run to completion and stop), so their health is read from the **describe API status plus the job's CloudWatch Logs group**, not a steady inference metric namespace. Thresholds are workload-specific.

Transform jobs: read `DescribeTransformJob` (`TransformJobStatus`, `FailureReason`) plus the CloudWatch **transform-job log group** `/aws/sagemaker/TransformJobs`; a `Failed` status or a `Completed` status with a short output object count maps to LLM-SM-BATCH-001 / LLM-SM-BATCH-003.

Transform jobs are one-shot; alarm on lifecycle via an EventBridge `SageMaker Transform Job State Change` rule matching `TransformJobStatus = Failed` routed to SNS, not on a steady metric.
