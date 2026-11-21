# opsai-ml-eval-check
> **Non-production disclaimer.** This skill performs a **read-only** review of model output quality and
> of evaluation jobs on Amazon Bedrock and Amazon SageMaker. It never mutates a resource. Its findings,
> severities, and SLAs are operational guidance derived from AWS documentation and general practice — they
> are not AWS-published commitments. Validate every recommendation against your own workload before acting.
> Not for use as a compliance attestation.
## What It Does
Answers three questions — is model quality measured at all, is it measured automatically, and can a
regression reach production — and diagnoses evaluation jobs. Findings are grounded in one catalog, each
with a stable `check-id`, a severity, the concrete observed evidence, an AWS-doc citation, and a
recommended (never executed) remediation:
- **Bedrock evaluation (`LLM-EVAL-*`)** — Bedrock model evaluation (`CreateEvaluationJob`, automated or
  human) and Bedrock RAG evaluation jobs on a knowledge base: whether any evaluation has run, stale
  datasets, human and safety dimensions, scores published as metrics, A/B comparison, regression gates,
  versioned results, and failed jobs never re-run.
- **Finish-reason drift (`LLM-EVAL-012..014`)** — the `stopReason` distribution from Bedrock invocation
  logs (`end_turn` → `max_tokens`), a missing metric filter, and the `OutputTokenCount` precursor.
- **SageMaker-side evaluation (`LLM-SM-EVAL-*`)** — Nova evaluation recipes and LLM-as-judge jobs that run
  as SageMaker training jobs: a customized model promoted with no eval run, a failed eval job, eval output
  not retained for comparison, and the switch to the Bedrock path when the job is Bedrock-native.
Inside a live incident it still returns its own findings; where the fault sits is decided by live-failure
triage when that skill is installed, and otherwise the answer says the locus was not determined.

Merged from the earlier quality evaluation and SageMaker evaluation skills.
## Prerequisites
Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:
- `bedrock:ListEvaluationJobs`, `bedrock:GetEvaluationJob`
- `bedrock:GetModelInvocationLoggingConfiguration`
- `logs:DescribeMetricFilters`, `logs:StartQuery`, `logs:GetQueryResults`, `logs:FilterLogEvents`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`
- `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob` (SageMaker-side evals run as recipe-driven
  training jobs)
- `s3:ListBucket` / `s3:ListObjectsV2` and `s3:GetObject` (HeadObject) on the eval dataset and output
  prefixes

If your Agent Space uses the default role, the AWS managed policy
[`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html)
already grants the CloudWatch and CloudWatch Logs reads and, in most Agent Spaces, the Bedrock and
SageMaker read actions. Prefer ReadOnly over Admin credentials (production safety).
## Uploading
Package the skill for upload, excluding repo-only files:
```bash
cd skills/opsai-ml-eval-check && zip -r ../opsai-ml-eval-check.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```
> **Agent Type: All agents (`GENERIC`).** Self-contained; related skills are optional.
## Usage Examples
- "Model quality dropped — is this a regression, and can you prove it?"
- "Our outputs are getting truncated — is this a max_tokens regression?"
- "Do we evaluate our models before shipping, and is there a quality gate on promotion?"
- "My Bedrock evaluation job failed overnight — what went wrong?"
- "Our RAG evaluation job for the knowledge base failed. What do its scores mean when it does run?"
- "Our Nova evaluation recipe ran as a SageMaker job and failed — what went wrong?"
- "Did we even evaluate the fine-tuned model before we promoted it?"
- "Set up an A/B comparison between two models."
## Author
Madhukiran J (jmadhuki) and Ankit Srivastava (ankitsri-aws). Ankit Srivastava (ankitsri-aws) wrote the
Bedrock evaluation and model-quality content (the quality-gate questions, finish-reason analysis, output
contract and delegation payload); Madhukiran J (jmadhuki) wrote the SageMaker-side evaluation content.
## Version History
See the `CHANGELOG.md` file in this directory.
