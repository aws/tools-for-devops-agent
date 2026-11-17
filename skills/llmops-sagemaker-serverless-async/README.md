# llmops-sagemaker-serverless-async

> **Non-production disclaimer.** This skill performs a **read-only** posture review of Amazon SageMaker
> serverless and asynchronous inference endpoints. It never mutates a resource. Its findings,
> severities, and SLAs are operational guidance derived from AWS documentation and general practice —
> they are not AWS-published commitments. Validate every recommendation against your own workload
> before acting. Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-SERVE-*** checks against a SageMaker serverless or asynchronous inference endpoint
and returns findings grounded in a catalog, each with a stable `check-id`, a severity, the concrete
observed evidence, an AWS-doc citation, and a recommended (never executed) remediation. Coverage:
serverless cold-start (`ModelSetupTime`) with no Provisioned Concurrency, serverless `MaxConcurrency`
exhausted while throttling, an async endpoint with no SNS success/error notification (silent
failures), an async endpoint with no scaling on `ApproximateBacklogSizePerInstance`, and large/long
inference on an always-on endpoint that belongs on async/serverless.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:DescribeEndpointConfig` (ServerlessConfig / AsyncInferenceConfig)
- `application-autoscaling:DescribeScalableTargets`, `application-autoscaling:DescribeScalingPolicies`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`,
  `cloudwatch:DescribeAlarms`

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-serverless-async && zip -r ../llmops-sagemaker-serverless-async.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "Our serverless endpoint has high cold-start latency — what should we change?"
- "Our async endpoint seems to drop requests silently and the queue backs up — what's misconfigured?"
- "Should this large/long-running inference be on async instead of an always-on endpoint?"

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
