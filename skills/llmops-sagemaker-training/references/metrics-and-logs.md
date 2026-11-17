# Metrics & Logs Reference

The job-signal set for SageMaker training / customization jobs.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds are workload-specific.

---

## SageMaker training job signals

Training jobs are **one-shot** (they run to completion and stop), so their health is read from the **describe API status plus the job's CloudWatch Logs group**, not a steady inference metric namespace.

Training jobs: health surfaces through `DescribeTrainingJob` (`TrainingJobStatus`, `SecondaryStatus`, `FailureReason` — the first 1024 characters of the container's `/opt/ml/output/failure` file) and the CloudWatch **training-job log group** `/aws/sagemaker/TrainingJobs` (stream per job/instance). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/API_DescribeTrainingJob.html

The `FailureReason` string (and the training log) maps to a TRAIN check the same way the Bedrock invocation-log table maps error codes to INV checks:

| `FailureReason` / log signal | What it indicates | Linked check |
|---|---|---|
| JSONL parse error / missing `messages`/`role`/`content` / invalid-sample tolerance exceeded | malformed or corrupt training data | LLM-SM-TRAIN-001 |
| `InsufficientInstanceCapacity` | AWS-side GPU capacity shortfall (not a quota problem) | LLM-SM-TRAIN-002 |
| `ResourceLimitExceeded` | customer instance-type service quota (possibly zero) | LLM-SM-TRAIN-003 |
| recipe / hyperparameter validation error (null or out-of-range `HyperParameters`) | config error in the recipe | LLM-SM-TRAIN-004 |
| `AccessDenied` / assume-role / `s3:GetObject`/`PutObject` denial | execution-role S3/KMS access gap | LLM-SM-TRAIN-005 |
| input channel empty / wrong `S3Uri` / unexpected `ContentType` | misconfigured data channel | LLM-SM-TRAIN-006 |

Training jobs are one-shot; alarm on lifecycle via an EventBridge `SageMaker Training Job State Change` rule matching `TrainingJobStatus = Failed` routed to SNS, not on a steady metric.
