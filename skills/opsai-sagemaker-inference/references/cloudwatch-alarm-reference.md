# CloudWatch Alarm Reference

Recommended alarms for SageMaker real-time, serverless and asynchronous inference endpoints with exact settings, plus the lifecycle alarm for batch transform jobs.

Columns: alarm | namespace / metric | statistic | threshold approach | period | datapoints-to-alarm / evaluation-periods | source.

`source` marks each threshold as:
- **AWS-published** — a numeric threshold AWS documents.
- **Derived** — a defensible default from AWS guidance/general operational practice; tune per workload.
- **Workload-specific** — AWS publishes no number; the operator must set a baseline from observed traffic.

> AWS does not publish fixed numeric alarm thresholds for most SageMaker metrics. The vast majority below are **Derived** or **Workload-specific**. Treat the numbers as starting points, not compliance values.

---

## Real-time endpoint alarms

Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html and https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling.html

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| 5xx errors | `AWS/SageMaker` / `Invocation5XXErrors` | Sum | `> 0` | 60s | 1 of 1 | Derived |
| Model latency | `AWS/SageMaker` / `ModelLatency` | p90 (µs) | `>` latency SLO | 60s | 3 of 3 | Workload-specific |
| Overhead latency | `AWS/SageMaker` / `OverheadLatency` | p90 (µs) | `>` tolerance | 60s | 3 of 3 | Workload-specific |
| Scaling signal | `AWS/SageMaker` / `InvocationsPerInstance` | Sum/Average | target-tracking target value | 60s | n/a (scaling policy) | Workload-specific |
| CPU saturation | `/aws/sagemaker/Endpoints` / `CPUUtilization` | Average | `> 80%` | 60s | 3 of 3 | Derived |
| Memory saturation | `/aws/sagemaker/Endpoints` / `MemoryUtilization` | Average | `> 80%` | 60s | 3 of 3 | Derived |
| GPU under-use (cost) | `/aws/sagemaker/Endpoints` / `GPUUtilization` | Average | `< 30%` sustained | 300s | 12 of 12 | Workload-specific |

For auto-scaling (LLM-SM-001), use a **target-tracking** policy on `InvocationsPerInstance` rather than a step alarm; set the target from a load test / Inference Recommender run.

## Serverless & async alarms

Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html and https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Async backlog growing | `AWS/SageMaker` / `ApproximateBacklogSizePerInstance` (dimension `EndpointName` only; adding `VariantName` returns no datapoints, https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-monitor.html) | Average | `>` target backlog (set the scaling target from observed burst depth) | 60s | 3 of 3 | Workload-specific |
| Async oldest-request age | `AWS/SageMaker` / `ApproximateAgeOfOldestRequest` | Maximum | `>` the caller's tolerated wait | 60s | 3 of 3 | Workload-specific |
| Serverless cold-start | `AWS/SageMaker` / `ModelSetupTime` | p90 | `>` first-call latency budget | 300s | 3 of 3 | Workload-specific |

Use the async backlog metric (`ApproximateBacklogSizePerInstance`) as the **target-tracking scaling signal** for LLM-SM-SERVE-004, not only as an alarm. Serverless cold-start (`ModelSetupTime`) is the LLM-SM-SERVE-001 signal.

## Batch transform (lifecycle, not a metric)

Transform jobs are one-shot; alarm on lifecycle via an EventBridge `SageMaker Transform Job State Change` rule matching `TransformJobStatus = Failed` routed to SNS, not on a steady metric (LLM-SM-BATCH-001). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/batch-transform.html and https://docs.aws.amazon.com/sagemaker/latest/dg/automating-sagemaker-with-eventbridge.html
