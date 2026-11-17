# Metrics & Logs Reference
The signal set for SageMaker Model Registry checks.
All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds are workload-specific.
---
## Model Registry signals
The Model Registry is a **metadata store**, not a runtime. Model package groups and model packages publish **no dedicated CloudWatch metric namespace** and have no log group of their own. Their health is read from the control-plane describe/list APIs, not from metrics:

- `ListModelPackages` / `DescribeModelPackage`: `ModelApprovalStatus`, `ModelPackageStatus`, and the training-job / dataset association (LLM-SM-REG-001..003).
- Registry state changes (a package created, or its approval status updated) are emitted as **EventBridge** events (`SageMaker Model Package State Change`), which is how approval-gate automation is audited.
- CloudTrail records `CreateModelPackage` and `UpdateModelPackage` calls; use it to see who changed an approval status.

Because there is no metric to read, CloudWatch "no datapoints" is not evidence of a healthy or unhealthy registry (see `api-quirks.md` §1). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html
