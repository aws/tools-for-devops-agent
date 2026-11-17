# llmops-sagemaker-model-registry

> **Non-production disclaimer.** This skill performs a **read-only** posture review of SageMaker Model
> Registry governance for customized LLM artifacts. It never mutates a resource. Its findings,
> severities, and SLAs are operational guidance derived from AWS documentation and general practice —
> they are not AWS-published commitments. Validate every recommendation against your own workload
> before acting. Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-REG-*** checks against the SageMaker Model Registry governance of a customized or
fine-tuned LLM artifact and returns findings grounded in a catalog, each with a stable `check-id`, a
severity, the concrete observed evidence, an AWS-doc citation, and a recommended (never executed)
remediation. Coverage: a customized artifact never registered (no governed version/lineage), a
deployed/staged package that is `PendingManualApproval` or `Rejected`, a registered package with no
lineage to its training job/dataset, and a model package group with a broad/absent resource policy or
an un-CMK'd artifact.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListModelPackages`, `sagemaker:DescribeModelPackage`

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-model-registry && zip -r ../llmops-sagemaker-model-registry.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "Did the fine-tuned model version we're serving actually go through approval in the Model Registry?"
- "Is our customized artifact registered, or is it deployed with no governed version?"
- "Does this registered package have lineage back to its training job and dataset?"

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
