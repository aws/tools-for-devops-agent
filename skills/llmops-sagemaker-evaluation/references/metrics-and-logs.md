# Metrics & Logs Reference

The job-signal set for SageMaker-side evaluation / benchmark jobs.

All metric names are as published by AWS. "AWS-published" means the metric/namespace is documented by AWS; thresholds are workload-specific.

---

## SageMaker-side evaluation job signals

A SageMaker-side evaluation runs as a **recipe-driven training job** (a Nova eval recipe or an LLM-as-judge job), so it is **one-shot** and its health is read from the **describe API status plus the job's CloudWatch Logs group** (`/aws/sagemaker/TrainingJobs`), not a dedicated native metric namespace. Read `DescribeTrainingJob` (`TrainingJobStatus`, `FailureReason`) for a bad eval-dataset path, a malformed recipe, or a judge-model access error (LLM-SM-EVAL-002).

Eval scores are not native CloudWatch metrics — publish them to the `LLMOps/Evaluation` custom namespace and retain the eval output prefix so run-over-run comparison is possible (LLM-SM-EVAL-003). Reference: https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html
