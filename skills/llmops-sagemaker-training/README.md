# llmops-sagemaker-training

> **Non-production disclaimer.** This skill performs a **read-only** failure and posture review of
> Amazon SageMaker training / customization jobs. It never mutates a resource. Its findings,
> severities, and SLAs are operational guidance derived from AWS documentation and general practice —
> they are not AWS-published commitments. Validate every recommendation against your own workload
> before acting. Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-TRAIN-*** checks against a SageMaker training / customization job (Nova
fine-tuning/SFT/LoRA or JumpStart) and returns findings grounded in a catalog, each with a stable
`check-id`, a severity, the concrete observed evidence, an AWS-doc citation, and a recommended (never
executed) remediation. Coverage: corrupt/malformed training data, `InsufficientInstanceCapacity` vs an
instance quota of zero, recipe/hyperparameter validation, IAM/S3 access, an empty/misconfigured data
channel, a job stuck **Pending on capacity** (not Failed), a completed job with no checkpoint, and the
GPU cost billed for a failed or empty run.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListTrainingJobs`, `sagemaker:DescribeTrainingJob`
- the Nova customization describe actions (these run as recipe-driven training jobs, read via
  `sagemaker:DescribeTrainingJob`)
- `service-quotas:GetServiceQuota`, `service-quotas:ListServiceQuotas`
- `s3:ListBucket`, `s3:GetObject` (HeadObject) on the training / recipe / output prefixes
- `iam:GetRole`, `iam:SimulatePrincipalPolicy` on the execution role

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-training && zip -r ../llmops-sagemaker-training.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "My Nova Micro SFT+LoRA fine-tuning job on SageMaker failed — what went wrong and how do I fix it?"
- "My GPU training job will not start. Is this a capacity problem or a quota problem?"
- "My training job has been Pending for hours — did it fail?"
- "Give me a health report for all training jobs in us-east-1."

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
