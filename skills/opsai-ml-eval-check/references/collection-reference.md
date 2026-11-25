# Collection Reference
The exact **read-only** API calls this skill uses to collect state, and the fields each contributes, by family. All calls are describe/list/get; none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Naming: the API column names **IAM actions**. Bedrock evaluation calls use the `bedrock:` prefix. The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are **not** used for collection (they invoke models).

**Permissions.** The AWS managed policy `AIDevOpsAgentAccessPolicy` grants every read below except `bedrock:GetEvaluationJob`. The `EnableOpsaiMlEvalCheck` parameter of [devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) adds it. Without it the skill works from the `ListEvaluationJobs` summaries (status, job type, application type, creation time) and reports the dataset, metric and failure-reason checks (LLM-EVAL-003, 006, 009, 010, 011) as not evaluated. `s3:GetObject` is not used: it returns customer data, so dataset and output checks read keys, counts, sizes and dates with `s3:ListBucket` (ListObjectsV2) only, and a check that needs file content is reported as not evaluated.

Other areas (model invocation, knowledge bases, agents, SageMaker endpoints, spend) belong to the sibling skills named in `related-skills.md`; this file lists only this skill's reads.

---
## Evaluation (EVAL)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListEvaluationJobs` | job names, `status`, `jobType` (Automated/Human), `applicationType`, creation times (empty = none ever) | LLM-EVAL-001, 002, 004, 011 |
| `bedrock:GetEvaluationJob` (not in the managed policy) | task type, metrics, dataset S3 locations, model targets, output location, `failureMessages` | LLM-EVAL-003, 006, 009, 010, 011 |
| `bedrock:ListEvaluationJobs` / `bedrock:GetEvaluationJob` for a RAG evaluation ([GetEvaluationJob](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetEvaluationJob.html), [EvaluationSummary](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_EvaluationSummary.html)) | `applicationType` (`ModelEvaluation` \| `RagEvaluation`), `inferenceConfig` / `inferenceConfigSummary` (knowledge base evaluated; `ragIdentifiers` is deprecated), `failureMessages` | LLM-EVAL-009, 011 |
| `s3:ListBucket` (ListObjectsV2) on the eval dataset and output prefixes | dataset last-modified (staleness), one prefix per run (versioning/retention) | LLM-EVAL-003, 008 |
| `cloudwatch:ListMetrics` (namespace `OpsAI/Evaluation`) | whether eval scores are published as metrics | LLM-EVAL-005 |

## SageMaker-side evaluation (SM-EVAL)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTrainingJobs` / `sagemaker:DescribeTrainingJob` for a Nova eval-recipe job (SageMaker-side evaluation runs as a recipe-driven job) | eval job status, `FailureReason`, eval-dataset S3 path, judge-model reference | LLM-SM-EVAL-001, 002 |
| `s3:ListBucket` (ListObjectsV2) on the eval output prefix | whether eval output was produced and retained | LLM-SM-EVAL-003 |
| `cloudwatch:ListMetrics` (namespace `OpsAI/Evaluation`) | whether SageMaker-side eval scores are published as metrics | LLM-SM-EVAL-003 |

## Quality signals from invocation logs and metrics
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:GetModelInvocationLoggingConfiguration` | whether invocation logging is on, and its log group | prerequisite of LLM-EVAL-012, 013 |
| `logs:StartQuery` / `logs:GetQueryResults` (Logs Insights) on the invocation log group | `output.outputBodyJson.stopReason` distribution (`finish-reason-analysis.md`) | LLM-EVAL-012 |
| `logs:DescribeMetricFilters` on the invocation log group | whether a metric filter on `output.outputBodyJson.stopReason` exists | LLM-EVAL-013 |
| `cloudwatch:GetMetricData` (`AWS/Bedrock` `OutputTokenCount`, `Invocations` per `ModelId`) | output length trend against traffic | LLM-EVAL-014 |
