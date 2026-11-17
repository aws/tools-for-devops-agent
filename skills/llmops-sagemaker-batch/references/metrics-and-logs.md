# Metrics & Logs Reference

The job-signal set for SageMaker batch transform / offline-scoring jobs.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds are workload-specific.

---

## SageMaker transform job signals

Transform jobs are **one-shot** (they run to completion and stop), so their health is read from the **describe API status plus the job's CloudWatch Logs group**, not a steady inference metric namespace.

Transform jobs: read `DescribeTransformJob` (`TransformJobStatus`, `FailureReason`) plus the CloudWatch **transform-job log group** `/aws/sagemaker/TransformJobs`; a `Failed` status or a `Completed` status with a short output object count maps to LLM-SM-BATCH-001 / LLM-SM-BATCH-003.

Transform jobs are one-shot; alarm on lifecycle via an EventBridge `SageMaker Transform Job State Change` rule matching `TransformJobStatus = Failed` routed to SNS, not on a steady metric.
