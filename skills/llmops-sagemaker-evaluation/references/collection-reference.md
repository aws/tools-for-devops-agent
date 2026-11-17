# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker-side evaluation review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker-side evaluation (SM-EVAL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTrainingJobs` / `DescribeTrainingJob` for a Nova eval-recipe job (SageMaker-side evaluation runs as a recipe-driven job) | eval job status, `FailureReason`, eval-dataset S3 path, judge-model reference | LLM-SM-EVAL-001, 002 |
| `s3:ListObjectsV2` / `HeadObject` on the eval output prefix | whether eval output was produced and retained | LLM-SM-EVAL-003 |
| `cloudwatch:ListMetrics` (namespace `LLMOps/Evaluation`) | whether SageMaker-side eval scores are published as metrics | LLM-SM-EVAL-003 |
