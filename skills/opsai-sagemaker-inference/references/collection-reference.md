# Collection Reference

The exact **read-only** API calls the agent uses to collect state for a SageMaker real-time, serverless/async or batch transform review, and the fields each contributes. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

---

## SageMaker real-time inference (SM)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListEndpoints` / `DescribeEndpoint` | endpoint status, `ProductionVariants[].CurrentInstanceCount`, variant weights, DataCaptureConfig status | LLM-SM-002, 003, 004 |
| `sagemaker:DescribeEndpointConfig` | variant instance type/count, `KmsKeyId`, `DataCaptureConfig`, serverless config | LLM-SM-002, 007, 008 |
| `sagemaker:DescribeModel` | `VpcConfig`, container/image, model data URL | LLM-SM-006 |
| `application-autoscaling:DescribeScalableTargets` / `DescribeScalingPolicies` | registered scaling targets/policies for the variant or async backlog | LLM-SM-001, LLM-SM-SERVE-004 |
| `sagemaker:ListMonitoringSchedules` / `DescribeMonitoringSchedule` | Model Monitor schedules attached | LLM-SM-002 |
| `sagemaker:ListInferenceRecommendationsJobs` | whether right-sizing was run | LLM-SM-005 |
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage for the deployed endpoint's model artifact | LLM-SM-011 |

## Serverless & asynchronous inference (SERVE)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:DescribeEndpointConfig` `ServerlessConfig` | `MemorySizeInMB`, `MaxConcurrency`, `ProvisionedConcurrency` | LLM-SM-SERVE-001, 002 |
| `sagemaker:DescribeEndpointConfig` `AsyncInferenceConfig` | `OutputConfig.NotificationConfig` (`SuccessTopic`/`ErrorTopic`), `ClientConfig.MaxConcurrentInvocationsPerInstance` | LLM-SM-SERVE-003 |
| `cloudwatch:GetMetricData` on `ModelSetupTime` | serverless cold-start latency | LLM-SM-SERVE-001 |
| `cloudwatch:GetMetricData` on `ApproximateBacklogSizePerInstance` / `ApproximateAgeOfOldestRequest` (dimension `EndpointName` only; a query that adds `VariantName` returns nothing) | async queue depth and oldest-request age | LLM-SM-SERVE-004 |

Scaling targets/policies for the async backlog are read with the `application-autoscaling` row in the SM table above.

## Batch transform (BATCH)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTransformJobs` / `DescribeTransformJob` | `TransformJobStatus`, `FailureReason`, `TransformInput` (`ContentType`/`SplitType`), `TransformOutput.KmsKeyId`, `MaxConcurrentTransforms`, `MaxPayloadInMB`, `BatchStrategy` | LLM-SM-BATCH-001..004 |
| `s3:ListBucket` (ListObjectsV2) on the transform input and output prefixes | `.out` object count vs input **file** count; one `<input>.out` is written per input file whose records all succeeded (partial-scoring detection) | LLM-SM-BATCH-003 |

## Observability (OBS)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `cloudwatch:ListMetrics` | presence of metrics in `AWS/SageMaker`, `/aws/sagemaker/Endpoints` | all OBS/metric checks |
| `cloudwatch:GetMetricData` / `GetMetricStatistics` | metric values over the window (latency, errors, invocations, utilization) | SM right-sizing/idle checks |
| `cloudwatch:DescribeAlarms` | which alarms exist vs the recommended set | LLM-SM-009, alarm gaps |
