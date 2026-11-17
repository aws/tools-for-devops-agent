# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker serverless / asynchronous inference review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker serverless & async inference (SERVE)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:DescribeEndpointConfig` `ServerlessConfig` | `MemorySizeInMB`, `MaxConcurrency`, `ProvisionedConcurrency` | LLM-SM-SERVE-001, 002 |
| `sagemaker:DescribeEndpointConfig` `AsyncInferenceConfig` | `OutputConfig.NotificationConfig` (`SuccessTopic`/`ErrorTopic`), `ClientConfig.MaxConcurrentInvocationsPerInstance` | LLM-SM-SERVE-003 |
| `cloudwatch:GetMetricData` on `ModelSetupTime` | serverless cold-start latency | LLM-SM-SERVE-001 |
| `cloudwatch:GetMetricData` on `ApproximateBacklogSizePerInstance` / `ApproximateAgeOfOldestRequest` | async queue depth and oldest-request age | LLM-SM-SERVE-004 |
| `application-autoscaling:DescribeScalableTargets` / `DescribeScalingPolicies` | registered scaling targets/policies for the async backlog | LLM-SM-SERVE-004 |
