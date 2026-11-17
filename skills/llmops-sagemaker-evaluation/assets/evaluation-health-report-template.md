# SageMaker-side Evaluation Job — Health Report
> Read-only review of SageMaker-side evaluation and benchmark jobs (Nova eval recipes, LLM-as-judge
> run as a SageMaker job) for a customized GenAI / LLM model.
> Every finding carries an `LLM-SM-EVAL-*` check-id, a catalog severity, and the observed evidence.
> No job was mutated. Account IDs and secret / eval-dataset values are redacted.
## Scope
- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Customized artifacts and eval jobs reviewed:** `<count and names>`
- **Window:** `<lookback window, e.g. last 30 days of eval runs>`
- **Routed out (Bedrock-native, LLM-SM-EVAL-004):** `<requests handed to llmops-quality-evaluation / none>`
- **Not covered (disclosed):** `<jobs / regions / S3 prefixes / checks skipped, with reason — permissions, budget, region-unsupported>`
## Service Check
| Request / job | Runs on (SageMaker recipe-driven training job / Bedrock `CreateEvaluationJob`) | Evidence (`DescribeTrainingJob` / `bedrock:GetEvaluationJob`) | In scope? |
|---|---|---|---|
| `<name>` | `<SageMaker / Bedrock>` | `<call that resolved it>` | `<yes / no — LLM-SM-EVAL-004 handoff>` |
> A SageMaker-side eval runs as a recipe-driven training job (api-quirks §2). A Bedrock-native
> evaluation is never diagnosed here; it is handed to `llmops-quality-evaluation`.
## Evaluation Coverage
| Customized artifact / model package | Promoted or deployed? | SageMaker eval run against it? | Eval output retained / published (`LLMOps/Evaluation`)? | check-id |
|---|---|---|---|---|
| `<name>` | `<yes / no>` | `<job name / none found>` | `<yes / no — no datapoints is not a zero score>` | `<LLM-SM-EVAL-001 / 003 as applicable>` |
> Registration or approval is not evidence of an eval run. No `LLMOps/Evaluation` datapoints means the
> scores were never published, not a measured zero (api-quirks §1).
## Per-Job State
For each **failed** eval job, name the cause and cite `LLM-SM-EVAL-002`:
| Eval job | `TrainingJobStatus` | `FailureReason` (summarized — no dataset content) | Cause (dataset S3 path / malformed recipe / judge-model access) | check-id |
|---|---|---|---|---|
| `<name>` | `<InProgress / Completed / Failed / Stopped>` | `<one-line summary>` | `<cause>` | `LLM-SM-EVAL-002` |
> A failed eval job says nothing about model quality. Fix the cause and re-run before judging the model.
## Findings
| check-id | severity | artifact / job | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-EVAL-00X` | `<catalog severity>` | `<name>` | `<concrete observed value>` | `<exact CLI command>` |
Only findings backed by an observed value appear here (evidence or silence). Each severity is the
catalog severity; a threshold AWS does not publish is marked `workload-specific`.
## Prioritized Recommendations
1. `<HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`
