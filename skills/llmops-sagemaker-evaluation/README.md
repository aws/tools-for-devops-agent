# llmops-sagemaker-evaluation

> **Non-production disclaimer.** This skill performs a **read-only** posture and failure review of
> SageMaker-side evaluation / benchmark jobs. It never mutates a resource. Its findings, severities,
> and SLAs are operational guidance derived from AWS documentation and general practice — they are not
> AWS-published commitments. Validate every recommendation against your own workload before acting.
> Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-EVAL-*** checks against a SageMaker-side evaluation / benchmark job (a Nova eval
recipe or LLM-as-judge run as a SageMaker job) and returns findings grounded in a catalog, each with a
stable `check-id`, a severity, the concrete observed evidence, an AWS-doc citation, and a recommended
(never executed) remediation. Coverage: a customized artifact promoted with no eval run, a SageMaker
evaluation job that failed, and eval output not published/retained for run-over-run comparison. A
**Bedrock-native** `CreateEvaluationJob` is routed to `llmops-quality-evaluation` via LLM-SM-EVAL-004.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob` (eval jobs run as recipe-driven
  training jobs)
- `s3:ListBucket`, `s3:GetObject` (HeadObject) on the eval output prefix
- `cloudwatch:ListMetrics` (namespace `LLMOps/Evaluation`)

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-evaluation && zip -r ../llmops-sagemaker-evaluation.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "Our Nova evaluation recipe ran as a SageMaker job and failed — what went wrong?"
- "Did we even evaluate the fine-tuned model before we promoted it?"
- "Is our eval output retained for run-over-run comparison?"

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
