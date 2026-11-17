# llmops-sagemaker-batch

> **Non-production disclaimer.** This skill performs a **read-only** posture and failure review of
> Amazon SageMaker batch transform jobs. It never mutates a resource. Its findings, severities, and
> SLAs are operational guidance derived from AWS documentation and general practice — they are not
> AWS-published commitments. Validate every recommendation against your own workload before acting.
> Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-BATCH-*** checks against a SageMaker batch transform job used for offline LLM
scoring and returns findings grounded in a catalog, each with a stable `check-id`, a severity, the
concrete observed evidence, an AWS-doc citation, and a recommended (never executed) remediation.
Coverage: transform job failure (format/`ContentType`/S3 access), under-parallelization
(`MaxConcurrentTransforms`=1), `Completed`-but-partial output masked by a success status, and output
written without a CMK where the scored data is sensitive.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListTransformJobs`, `sagemaker:DescribeTransformJob`
- `s3:ListBucket`, `s3:GetObject` (HeadObject) on the transform output prefix

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-batch && zip -r ../llmops-sagemaker-batch.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "Our batch transform job shows Completed but the results look short — was every record scored?"
- "The transform job failed — is it a format problem or an access problem?"
- "Is this batch job under-parallelized on a large dataset?"

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
