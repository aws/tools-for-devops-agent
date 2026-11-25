# Metrics & Logs Reference

The signal set for SageMaker training / customization jobs and for SageMaker Model Registry checks.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds are workload-specific.

---

## 1. Training job signals

Training jobs are **one-shot** (they run to completion and stop), so their health is read from the **describe API status plus the job's CloudWatch Logs group**, not a steady inference metric namespace.

Training jobs: health surfaces through `DescribeTrainingJob` (`TrainingJobStatus`, `SecondaryStatus`, `FailureReason` — the first 1024 characters of the container's `/opt/ml/output/failure` file) and the CloudWatch **training-job log group** `/aws/sagemaker/TrainingJobs` (stream per job/instance). Reference: https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_DescribeTrainingJob.html

The `FailureReason` string (and the training log) maps to a TRAIN check:

| `FailureReason` / log signal | What it indicates | Linked check |
|---|---|---|
| JSONL parse error / missing `messages`/`role`/`content` / invalid-sample tolerance exceeded | malformed or corrupt training data | LLM-SM-TRAIN-001 |
| `InsufficientCapacityError` | AWS-side GPU capacity shortfall after the pending wait (not a quota problem; SageMaker's name, not EC2's `InsufficientInstanceCapacity`) | LLM-SM-TRAIN-002 |
| `ResourceLimitExceeded` | customer instance-type service quota (possibly zero) | LLM-SM-TRAIN-003 |
| recipe / hyperparameter validation error (null or out-of-range `HyperParameters`) | config error in the recipe | LLM-SM-TRAIN-004 |
| `AccessDenied` / assume-role / `s3:GetObject`/`PutObject` denial | execution-role S3/KMS access gap | LLM-SM-TRAIN-005 |
| input channel empty / wrong `S3Uri` / unexpected `ContentType` | misconfigured data channel | LLM-SM-TRAIN-006 |

Training jobs are one-shot; alarm on lifecycle via an EventBridge `SageMaker Training Job State Change` rule matching `TrainingJobStatus = Failed` routed to SNS, not on a steady metric.

## 2. Model Registry signals
The Model Registry is a **metadata store**, not a runtime. Model package groups and model packages publish **no dedicated CloudWatch metric namespace** and have no log group of their own. Their health is read from the control-plane describe/list APIs, not from metrics:

- `ListModelPackages` / `DescribeModelPackage`: `ModelApprovalStatus`, `ModelPackageStatus`, and the training-job / dataset association (LLM-SM-REG-001..003).
- Registry state changes (a package created, or its approval status updated) are emitted as **EventBridge** events (`SageMaker Model Package State Change`), which is how approval-gate automation is audited.
- CloudTrail records `CreateModelPackage` and `UpdateModelPackage` calls; use it to see who changed an approval status.

Because there is no metric to read, CloudWatch "no datapoints" is not evidence of a healthy or unhealthy registry (see `api-quirks.md` §6). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html
