# CloudWatch Alarm Reference

Recommended alarms for SageMaker serverless & asynchronous inference with exact settings.

Columns: alarm | namespace / metric | statistic | threshold approach | period | datapoints-to-alarm / evaluation-periods | source.

`source` marks each threshold as:
- **AWS-published** — a numeric threshold AWS documents.
- **Derived** — a defensible default from AWS guidance/general operational practice; tune per workload.
- **Workload-specific** — AWS publishes no number; the operator must set a baseline from observed traffic.

> AWS does not publish fixed numeric alarm thresholds for most SageMaker metrics. The vast majority below are **Derived** or **Workload-specific**. Treat the numbers as starting points, not compliance values.

---

## SageMaker serverless & async alarms

Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html and https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html

| alarm | namespace / metric | statistic | threshold approach | period | datapoints/eval | source |
|---|---|---|---|---|---|---|
| Async backlog growing | `AWS/SageMaker` / `ApproximateBacklogSizePerInstance` | Average | `>` target backlog (set the scaling target from observed burst depth) | 60s | 3 of 3 | Workload-specific |
| Async oldest-request age | `AWS/SageMaker` / `ApproximateAgeOfOldestRequest` | Maximum | `>` the caller's tolerated wait | 60s | 3 of 3 | Workload-specific |
| Serverless cold-start | `AWS/SageMaker` / `ModelSetupTime` | p90 | `>` first-call latency budget | 300s | 3 of 3 | Workload-specific |

Use the async backlog metric (`ApproximateBacklogSizePerInstance`) as the **target-tracking scaling signal** for LLM-SM-SERVE-004, not only as an alarm. Serverless cold-start (`ModelSetupTime`) is the LLM-SM-SERVE-001 signal.
