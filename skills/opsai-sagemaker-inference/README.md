# opsai-sagemaker-inference

> **Non-production disclaimer.** This skill performs a **read-only** posture, failure, and right-sizing
> review of Amazon SageMaker real-time, serverless and asynchronous inference endpoints and batch
> transform jobs. It never mutates a resource. Its findings, severities, and SLAs are operational
> guidance derived from AWS documentation and general practice — they are not AWS-published
> commitments. Validate every recommendation against your own workload before acting. Not for use as a
> compliance attestation.

## What It Does

Runs the **LLM-SM** checks against SageMaker inference and returns findings grounded in a catalog, each
with a stable `check-id`, a severity, the concrete observed evidence, an AWS-doc citation, and a
recommended (never executed) remediation. Areas and check families:

- **Real-time endpoints (LLM-SM-001..011)** — reliability (scaling failures, idle/abandoned variants),
  operational excellence (A/B variants, registry lineage), security (CMK), cost (idle capacity, instance-hours), and performance/right-sizing judged against **both** metric
  namespaces (`AWS/SageMaker` and `/aws/sagemaker/Endpoints`).
- **Serverless & asynchronous endpoints (LLM-SM-SERVE-*)** — serverless cold start (`ModelSetupTime`)
  with no Provisioned Concurrency, `MaxConcurrency` exhausted while throttling, async endpoints with no
  SNS success/error notification or no scaling on `ApproximateBacklogSizePerInstance`, and the
  serverless/async fit decision for large, long or bursty inference.
- **Batch transform (LLM-SM-BATCH-*)** — job failure (format/`ContentType`/S3 access),
  under-parallelization, `Completed`-but-partial output masked by a success status, and output written
  without a CMK where the scored data is sensitive.

It also answers stated break-fix errors directly (failed endpoints, health checks, VPC reachability,
`ModelError`, capacity versus quota, async notifications, transform parsing and timeouts). It diagnoses
the endpoint or job itself; deciding whether a live fault sits with the provider, infrastructure or
application is left to a live-failure triage skill when one is installed.

Merged from the earlier SageMaker inference endpoints, serverless and async, and batch transform skills.

## Prerequisites

Read-only (or least-privilege) credentials for the account and region under review. Required IAM read
actions:

- `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`
- `sagemaker:DescribeEndpointConfig` (including `ServerlessConfig` / `AsyncInferenceConfig`),
  `sagemaker:DescribeModel`
- `sagemaker:ListMonitoringSchedules`, `sagemaker:DescribeMonitoringSchedule`
- `sagemaker:ListInferenceRecommendationsJobs`
- `sagemaker:ListModelPackages`, `sagemaker:DescribeModelPackage`
- `sagemaker:ListTransformJobs`, `sagemaker:DescribeTransformJob`
- `application-autoscaling:DescribeScalableTargets`, `application-autoscaling:DescribeScalingPolicies`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`,
  `cloudwatch:DescribeAlarms`
- `s3:ListBucket` (the ListObjectsV2 call) on the transform output prefix: keys and sizes only. The skill
  does not use `s3:GetObject`, which returns customer data

`AIDevOpsAgentAccessPolicy` grants all of these, so no skill policies template parameter is needed.

Prefer ReadOnly over Admin credentials (production safety).

## Uploading

Package the skill for upload, excluding repo-only files:

```bash
cd skills/opsai-sagemaker-inference && zip -r ../opsai-sagemaker-inference.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

> **Agent Type: All agents (`GENERIC`).** Self-contained; related skills are optional.

## Usage Examples

- "Our SageMaker endpoint `my-llm-ep` is throwing Invocation5XXErrors and ModelLatency is climbing —
  what's wrong?"
- "Is this GPU endpoint right-sized, or are we over-provisioned? What is it costing us?"
- "We have an endpoint that shows InService but I think it's idle — is it serving anything?"
- "Our serverless endpoint has high cold-start latency — what should we change?"
- "Our async endpoint seems to drop requests silently and the queue backs up — what's misconfigured?"
- "Our batch transform job shows Completed but the results look short — was every record scored?"
- "The transform job failed — is it a format problem or an access problem?"
- "Give me a health report for all real-time inference endpoints in us-east-1."

## Author

Madhukiran J (jmadhuki)

## Version History

See the `CHANGELOG.md` file in this directory.
