# llmops-sagemaker-inference-endpoints

> **Non-production disclaimer.** This skill performs a **read-only** posture, health, and right-sizing
> review of Amazon SageMaker real-time inference endpoints. It never mutates a resource. Its findings,
> severities, and SLAs are operational guidance derived from AWS documentation and general practice —
> they are not AWS-published commitments. Validate every recommendation against your own workload
> before acting. Not for use as a compliance attestation.

## What It Does

Runs the **LLM-SM-001..011** endpoint checks against a SageMaker real-time inference endpoint and
returns findings grounded in a catalog, each with a stable `check-id`, a severity, the concrete
observed evidence, an AWS-doc citation, and a recommended (never executed) remediation. Coverage:
reliability (auto-scaling, idle/abandoned variants), operational excellence (data capture, Model
Monitor, A/B variants, registry lineage), security (VPC, CMK), cost (idle capacity, serverless/async
fit), and performance/right-sizing judged against **both** metric namespaces (`AWS/SageMaker` and
`/aws/sagemaker/Endpoints`).

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`
- `sagemaker:DescribeEndpointConfig`, `sagemaker:DescribeModel`
- `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- `sagemaker:ListInferenceRecommenderJobs`
- `sagemaker:ListModelPackages`, `sagemaker:DescribeModelPackage`
- `application-autoscaling:DescribeScalableTargets`, `application-autoscaling:DescribeScalingPolicies`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`,
  `cloudwatch:DescribeAlarms`

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/llmops-sagemaker-inference-endpoints && zip -r ../llmops-sagemaker-inference-endpoints.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents.** This skill is self-contained and can be attached to any agent, but it is
> authored for and belongs to the **`llmops-agent`** custom agent. It has no dependency on any other
> skill.

## Usage Examples

- "Our SageMaker endpoint `my-llm-ep` is throwing Invocation5XXErrors and ModelLatency is climbing —
  what's wrong?"
- "Is this GPU endpoint right-sized, or are we over-provisioned?"
- "We have an endpoint that shows InService but I think it's idle — is it serving anything?"
- "Give me a health report for all real-time inference endpoints in us-east-1."

## Author

Madhukiran J

## Version History

See the `CHANGELOG.md` file in this directory.
