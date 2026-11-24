# Router

Match what the operator says to the first read and the files to load. Paths are relative to the skill root.

Which evaluation call to make is in [collection-reference.md](references/collection-reference.md); which log group, field, query and metric carry the quality signals is in [metrics-and-logs.md](references/metrics-and-logs.md). Load both with any row.

| Operator says | First read | Load |
|---|---|---|
| Do we have evals, is quality measured at all | `ListEvaluationJobs` (confirm regional support first) | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-001), [api-quirks.md](references/api-quirks.md) |
| Is there a quality gate before deploy, regression gate on promotion | Candidate eval score vs established baseline | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-007) |
| Do evals run automatically or by hand | Eval-job cadence and names as a proxy; CI/CD cannot be confirmed via API | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-002) |
| Our eval job failed, did it ever re-run | `GetEvaluationJob` status and failure reason | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-011) |
| I used Bedrock CreateEvaluationJob, what's wrong with my eval | `GetEvaluationJob` `status`, `failureMessages` → Bedrock path, Step 3 (LLM-SM-EVAL-004 only if it was presented as SageMaker) | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-011), [api-quirks.md](references/api-quirks.md) §15 |
| Our RAG evaluation job failed / what do its scores mean | `GetEvaluationJob` `applicationType`=`RagEvaluation`, `failureMessages`, knowledge base in `inferenceConfig` | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-009, 011) |
| Output is being cut off, responses are truncated | `GetModelInvocationLoggingConfiguration`, then the `stopReason` distribution over the resolved log group, current vs baseline window | [metrics-and-logs.md](references/metrics-and-logs.md) (§1-§3), [finish-reason-analysis.md](references/finish-reason-analysis.md) (LLM-EVAL-012) |
| We can't see truncation, is anything watching finish reasons | `logs:DescribeMetricFilters` for `{ $.output.outputBodyJson.stopReason = "max_tokens" }` on the invocation log group | [metrics-and-logs.md](references/metrics-and-logs.md) (§5), [finish-reason-analysis.md](references/finish-reason-analysis.md) (LLM-EVAL-013) |
| Answers got longer, did quality drop | `OutputTokenCount` against flat `Invocations` — a precursor, not a truncation measurement | [metrics-and-logs.md](references/metrics-and-logs.md) (§4), [finish-reason-analysis.md](references/finish-reason-analysis.md) (LLM-EVAL-014) |
| How do I A/B compare two models | Candidate vs incumbent on the identical dataset and metrics | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-006) |
| We need human evaluation for tone/helpfulness | Presence of a human-based evaluation job | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-004) |
| Is the RAG path's retrieval quality measured | A retrieve / retrieve-and-generate evaluation job | [checks-evaluation.md](references/checks-evaluation.md) (LLM-EVAL-009) |
| We fine-tuned a model and deployed it, did anyone evaluate it | `ListModelPackages` / `DescribeModelPackage`, then recent SageMaker evaluation jobs for the artifact | [checks-evaluation.md](references/checks-evaluation.md) (LLM-SM-EVAL-001) |
| My evaluation or benchmark job failed (SageMaker) | `DescribeTrainingJob` `FailureReason` for the eval job | [checks-evaluation.md](references/checks-evaluation.md) (LLM-SM-EVAL-002), [metrics-and-logs.md](references/metrics-and-logs.md) §7, [known-causes.md](references/known-causes.md) |
| The eval dataset path is wrong, the judge model is denied | `FailureReason`, the eval dataset S3 URI, then the role's access to the judge model | [checks-evaluation.md](references/checks-evaluation.md) (LLM-SM-EVAL-002) |
| I can't compare this eval to last week's, scores aren't saved | `cloudwatch:ListMetrics` in `OpsAI/Evaluation`, then the eval output prefix | [checks-evaluation.md](references/checks-evaluation.md) (LLM-SM-EVAL-003), [api-quirks.md](references/api-quirks.md) §10 |
| Which service is running my evaluation | `DescribeTrainingJob` for a recipe-driven job vs `bedrock:GetEvaluationJob` | [api-quirks.md](references/api-quirks.md) §15 (LLM-SM-EVAL-004) |
