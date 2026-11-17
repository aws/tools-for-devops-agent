# Checks — SageMaker-side evaluation / benchmark jobs (LLM-SM-EVAL-*)

Covers Amazon SageMaker-side evaluation / benchmark jobs for a customized GenAI / LLM model — Nova eval recipes and LLM-as-judge jobs run as a SageMaker job.

Each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation`

Family code: **SM** = SageMaker for LLMs. Family prefix: `LLM-SM-`; the `LLM-SM-EVAL-*` sub-family covers SageMaker-side evaluation.

Severity scale: CRITICAL > HIGH > MEDIUM > LOW > INFO. A *tuning or right-sizing judgment* with no AWS-published number is marked `workload-specific` at severity INFO; a *binary present/absent/failed* state (a job FAILED, no checkpoint produced, access denied) keeps its catalog severity even when AWS publishes no number.

## SageMaker-side evaluation / benchmark jobs (LLM-SM-EVAL-*)

SageMaker-side model evaluation for customized LLMs (Nova eval recipes, LLM-as-judge run as a SageMaker job). One row is an explicit route-out so this skill does not duplicate the Bedrock-native evaluation owned by `llmops-quality-evaluation` (the `LLM-EVAL-*` family).

| check-id | pillar | severity | detection-rule | remediation | AWS-doc-citation |
|---|---|---|---|---|---|
| LLM-SM-EVAL-001 | Quality & Evaluation | MEDIUM | A customized/fine-tuned LLM artifact (from an LLM-SM-TRAIN job) was registered or deployed with **no** SageMaker-side evaluation run against it — quality/regression is unmeasured before serving. Threshold `workload-specific`. | Run a SageMaker model-evaluation / Nova eval recipe (or LLM-as-judge job) against a held-out set before promoting the customized model; gate promotion on the result. | https://docs.aws.amazon.com/nova/latest/userguide/customize-fine-tune-evaluate-recipe-examples.html |
| LLM-SM-EVAL-002 | Reliability | HIGH | A SageMaker evaluation/benchmark job `Failed` — read the `FailureReason` for a bad eval-dataset S3 path, a malformed eval recipe, or a judge-model access/permission error. | Fix the indicated cause (dataset path, recipe schema, or judge-model IAM/access) and resubmit the evaluation job; validate the eval dataset format first. | https://docs.aws.amazon.com/nova/latest/userguide/customize-fine-tune-evaluate-recipe-examples.html |
| LLM-SM-EVAL-003 | Operational Excellence | LOW | Evaluation output exists but is not published as a tracked metric / not retained for run-over-run comparison — no quality trend for the customized model. Threshold `workload-specific`. | Publish eval scores as custom CloudWatch metrics (namespace `LLMOps/Evaluation`) and retain the output prefix so regressions are visible over time. | https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html |
| LLM-SM-EVAL-004 | Quality & Evaluation | INFO | The evaluation request is actually **Bedrock-native** (a Bedrock `CreateEvaluationJob`, not a SageMaker job) — out of this skill's scope. | Hand off to the sibling skill `llmops-quality-evaluation` (`LLM-EVAL-*`); do not duplicate its catalog here. This row is a routing marker, not a defect in the SageMaker workload, so its citation is the Bedrock-native evaluation doc because the request belongs to that service. | https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation.html |
