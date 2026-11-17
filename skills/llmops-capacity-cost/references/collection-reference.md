# Collection Reference

The exact **read-only** API calls the agent uses to collect state, and the fields each contributes, organized by family. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Bedrock has two control-plane clients: `bedrock` (model/eval/guardrail/PT config, logging config) and `bedrock-agent` (agents, knowledge bases, data sources). The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are **not** used for collection (they invoke models).

---

## Model invocation (INV)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:GetModelInvocationLoggingConfiguration` | `loggingConfig` (cloudWatchConfig, s3Config, text/image/embedding delivery flags) | LLM-INV-001, 005, 010 |
| `bedrock:ListFoundationModels` | `modelSummaries[].modelId`, `modelLifecycle.status`, I/O modalities, streaming support | LLM-INV-003 |
| `bedrock:ListInferenceProfiles` / `GetInferenceProfile` | profile ids, type (SYSTEM_DEFINED/APPLICATION), member regions/models | LLM-INV-002, LLM-COST-005 |
| `bedrock:GetFoundationModelAvailability` (where available) | per-model access/availability in region | LLM-INV-014 |
| `iam:GetPolicy`/`GetPolicyVersion`/`SimulatePrincipalPolicy` | `bedrock:InvokeModel*` resource scope and conditions | LLM-INV-004 |

## Provisioned throughput (PT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListProvisionedModelThroughputs` | provisioned model ARNs, `status`, `modelUnits`, `commitmentDuration` | LLM-PT-001/002/003 |
| `bedrock:GetProvisionedModelThroughput` | per-PT model units, model ARN, creation/commitment times | LLM-PT-001/003 |

## Guardrails (GRD)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListGuardrails` | guardrail ids, versions, status | LLM-GRD-001, 006 |
| `bedrock:GetGuardrail` | contentPolicy, sensitiveInformationPolicy, topicPolicy, wordPolicy, contextualGroundingPolicy, kmsKeyId, blocked messaging | LLM-GRD-002..005, 008..010 |

## Knowledge bases / RAG (KB)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:ListKnowledgeBases` | KB ids, status | LLM-KB-008 |
| `bedrock-agent:GetKnowledgeBase` | `embeddingModelArn`, `storageConfiguration`, KMS config, vector store type | LLM-KB-004, 005, 006 |
| `bedrock-agent:ListDataSources` / `GetDataSource` | chunking config, parsing config, data source KMS, S3 config | LLM-KB-003, 005 |
| `bedrock-agent:ListIngestionJobs` | per-source job history (empty = never synced) | LLM-KB-001, 010 |
| `bedrock-agent:GetIngestionJob` | latest `status`, `statistics` (docs scanned/indexed/failed), `failureReasons` | LLM-KB-002 |

## Agents & action groups (AGT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:ListAgents` | agent ids, status | LLM-AGT-004 |
| `bedrock-agent:GetAgent` | `guardrailConfiguration`, `foundationModel`, `memoryConfiguration`, prompt override config | LLM-AGT-001, 003, 008, 009 |
| `bedrock-agent:ListAgentActionGroups` / `GetAgentActionGroup` | action group executor (Lambda ARN), API schema, parent action group signatures (code interpreter) | LLM-AGT-002, 006 |
| `bedrock-agent:ListAgentAliases` / `GetAgentAlias` | alias ids, routing config, version pinning | LLM-AGT-007 |
| `bedrock-agent:ListAgentKnowledgeBases` | KBs attached to the agent | LLM-KB-008 |
| `lambda:GetPolicy` / `iam:GetRolePolicy` for action-group Lambda | execution-role permission scope | LLM-AGT-002 |
| `bedrock-agent:ListPrompts` / `GetPrompt` | prompt versions in Prompt Management | LLM-AGT-003, LLM-INV-012 |

## Evaluation (EVAL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListEvaluationJobs` | job names, `status`, `jobType` (automated/human), creation times (empty = none ever) | LLM-EVAL-001, 002, 004 |
| `bedrock:GetEvaluationJob` | task type, metrics, dataset S3 locations, model targets, output location, failure reason | LLM-EVAL-003, 006, 009, 010, 011 |
| `s3:ListObjectsV2`/`HeadObject` on eval dataset+output prefixes | dataset last-modified (staleness), output versioning/retention | LLM-EVAL-003, 008 |
| `cloudwatch:ListMetrics` (namespace `LLMOps/Evaluation`) | whether eval scores are published as metrics | LLM-EVAL-005 |

## SageMaker inference (SM)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListEndpoints` / `DescribeEndpoint` | endpoint status, `ProductionVariants[].CurrentInstanceCount`, variant weights, DataCaptureConfig status | LLM-SM-002, 003, 004 |
| `sagemaker:DescribeEndpointConfig` | variant instance type/count, `KmsKeyId`, `DataCaptureConfig`, serverless config | LLM-SM-002, 007, 008 |
| `sagemaker:DescribeModel` | `VpcConfig`, container/image, model data URL | LLM-SM-006 |
| `application-autoscaling:DescribeScalableTargets` / `DescribeScalingPolicies` | registered scaling targets/policies for the variant | LLM-SM-001 |
| `sagemaker:ListMonitoringSchedules` / `DescribeMonitoringSchedule` | Model Monitor schedules attached | LLM-SM-002 |
| `sagemaker:ListInferenceRecommenderJobs` | whether right-sizing was run | LLM-SM-005 |
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage / approval status | LLM-SM-011 |

## Observability (OBS)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `cloudwatch:ListMetrics` | presence of metrics in `AWS/Bedrock`, `AWS/Bedrock/Guardrails`, `AWS/Bedrock/Agents`, `AWS/SageMaker`, `/aws/sagemaker/Endpoints` | all OBS/metric checks |
| `cloudwatch:GetMetricData` / `GetMetricStatistics` | metric values over the window (latency, errors, throttles, tokens, utilization) | invocation/agent/SM checks |
| `cloudwatch:DescribeAlarms` | which alarms exist vs the recommended set | LLM-SM-009, alarm gaps |
| `logs:DescribeLogGroups` | existence of the Bedrock invocation log group | LLM-INV-001, 005 |
| `logs:StartQuery`/`GetQueryResults` (Logs Insights) | invocation-log error patterns (see metrics-and-logs.md) | LLM-INV error patterns |

## Cost (COST)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `ce:GetCostAndUsage` with `GroupBy Type=PRODUCT_ATTRIBUTE,Key=model` (or `provider`, `inferenceType`, `feature`), **no** SERVICE filter | billed Bedrock spend per model / provider / token type (windows before product-attribute data exists → `DataUnavailableException`; fall back to `USAGE_TYPE`) | billed cost model, all COST checks |
| `ce:GetCostAndUsage` grouped by `USAGE_TYPE` | billed spend per model × token type (input, output, cache-read, cache-write) × tier (`-flex`/`-priority`) × routing (`-cross-region-global`); PT model-unit hours | billed cost model, LLM-COST-001..006, LLM-PT-001 |
| `ce:GetDimensionValues` (`SERVICE` with `SearchString=Bedrock`) | every service name Bedrock costs appear under | billed cost model (avoids undercount, api-quirks §16) |
| `pricing:GetProducts` (us-east-1 endpoint; `AmazonBedrockFoundationModels` or `AmazonBedrock`, filter `regionCode` + `model`, or `titanModel` for Titan; one call per model) | published per-token rates by token type, with tier and routing in `usagetype` | token model (cross-check / fallback), what-ifs (cost-analysis.md §1b) |
| Bedrock pricing page (https://aws.amazon.com/bedrock/pricing/), read with `verify_aws_claim` | published per-token rates by model, region, token type, tier and routing, with the date read | token model (cross-check / fallback), LLM-COST-003/004 what-ifs |
| `cloudwatch:GetMetricData` on `InputTokenCount`/`OutputTokenCount`/`CacheReadInputTokenCount`/`CacheWriteInputTokenCount` | token volume per type for the token model (cross-check / fallback) | LLM-COST-001, 002 |
| `servicequotas:ListServiceQuotas` (IAM action; boto3 client `service-quotas`, service code `bedrock`) | applied per-model tokens-per-minute / requests-per-minute quota values (on-demand, cross-region, global, `[bedrock-mantle endpoint]` input/output) | quota headroom (`EstimatedTPMQuotaUsage` ÷ quota), LLM-PT-002 |
| `bedrock:GetInferenceProfile` / `bedrock:GetFoundationModel` | the foundation model behind a `ModelId` (an error = direct call); `providerName` and `modelName` for the quota-name match | quota headroom (SKILL.md Step 6), LLM-INV-002 |
| `cloudwatch:GetMetricData` on `InvocationThrottles`/`InvocationClientErrors` per `ModelId` **and** with no dimension | throttles and quota rejections, including requests that failed before model resolution | LLM-INV-007, LLM-PT-002 |
| `cloudwatch:GetMetricData` on `AWS/BedrockMantle` `TotalInputTokens`/`TotalOutputTokens`/`InferenceClientErrors` by `Model` | token volume and errors for bedrock-mantle endpoint traffic (no throttle metric) | token model, LLM-INV-007 (api-quirks §20) |
| `logs:DescribeLogGroups` / `s3:GetBucketLifecycleConfiguration` on the invocation-log destination | `retentionInDays`, `storedBytes`; S3 lifecycle expiration on the logging prefix | LLM-COST-006 |

## AgentCore (AC)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:GetAgentRuntime` / `ListAgentRuntimes` | runtime status, version, endpoint, role ARN | LLM-AC-001, 009 |
| `iam:SimulatePrincipalPolicy` (on runtime role) | permission eval for bedrock:InvokeModel, s3:GetObject, logs:PutLogEvents | LLM-AC-001, LLM-INV-013 |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP policies affecting the account | LLM-AC-002, LLM-INV-015 |
| `ec2:DescribeVpcEndpoints` | VPC endpoint presence for bedrock-runtime, bedrock-agent-runtime, s3, logs, monitoring | LLM-AC-003 |
| `bedrock-agent:GetAgentGateway` / `ListAgentGateways` | gateway config, targets, auth | LLM-AC-004, 008 |
| AgentCore Observability (OTLP config inspection) | telemetry enablement, span coverage | LLM-AC-005, 006, LLM-TEL-001 |

## Telemetry coverage (TEL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `logs:DescribeMetricFilters` | metric filters on Bedrock invocation log group (finish-reason, error patterns) | LLM-TEL-002 |
| `cloudwatch:ListDashboards` | presence of a GenAI-specific dashboard | LLM-TEL-005 |
| `logs:DescribeLogGroups` | log retention, log format (structured JSON vs text) | LLM-TEL-004, 008 |
| `health:DescribeEvents` | active service events in region (for transient classifier) | transient-vs-config-classifier |

## Access control (cross-cutting additions)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `iam:SimulatePrincipalPolicy` | policy simulation for specific Bedrock actions | LLM-INV-013, LLM-AC-001 |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP deny detection | LLM-INV-015, LLM-AC-002 |
| `bedrock:GetFoundationModelAvailability` / model access page | model access + marketplace subscription status | LLM-INV-014 |
| `health:DescribeEvents` | active Bedrock service events in region | transient-vs-config-classifier |

## Security (SEC) — cross-cutting

Security findings are produced by the KMS/VPC/IAM fields above rather than a separate family of calls:
- Encryption: `KmsKeyId` from guardrail, KB storage, data source, SageMaker endpoint config; S3 bucket encryption on logging/eval/data-source buckets.
- Network: `VpcConfig` on SageMaker models; vector store network policy.
- IAM: policy scope for `bedrock:InvokeModel*` and action-group Lambda roles.
Feeds LLM-INV-004/010, LLM-GRD-010, LLM-KB-005/006, LLM-SM-006/007, LLM-AGT-002.
