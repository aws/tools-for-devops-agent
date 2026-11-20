# Collection Reference

The exact **read-only** API calls the agent uses to collect state, and the fields each contributes, organized by family. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Bedrock has two control-plane clients: `bedrock` (model/eval/guardrail/PT config, logging config) and `bedrock-agent` (agents, knowledge bases, data sources). The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are **not** used for collection (they invoke models).

Only the Evaluation (EVAL) and SageMaker-side evaluation (SM-EVAL) sections feed this skill's check-ids. The other sections are kept as knowledge for a question that reaches into another area; their "Feeds checks" cell names the owning area, and a finding drawn from them carries no check-id here.

---

## Model invocation (INV)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:GetModelInvocationLoggingConfiguration` | `loggingConfig` (cloudWatchConfig, s3Config, text/image/embedding delivery flags) | Bedrock invocation-logging area |
| `bedrock:ListFoundationModels` | `modelSummaries[].modelId`, `modelLifecycle.status`, I/O modalities, streaming support | Bedrock model-lifecycle area |
| `bedrock:ListInferenceProfiles` / `GetInferenceProfile` | profile ids, type (SYSTEM_DEFINED/APPLICATION), member regions/models | inference-profile and spend areas |
| `bedrock:GetFoundationModelAvailability` (where available) | per-model access/availability in region | Bedrock model-access area |
| `iam:GetPolicy`/`GetPolicyVersion`/`SimulatePrincipalPolicy` | `bedrock:InvokeModel*` resource scope and conditions | Bedrock model-access area |

## Provisioned throughput (PT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListProvisionedModelThroughputs` | provisioned model ARNs, `status`, `modelUnits`, `commitmentDuration` | Provisioned Throughput area |
| `bedrock:GetProvisionedModelThroughput` | per-PT model units, model ARN, creation/commitment times | Provisioned Throughput area |

## Guardrails (GRD)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListGuardrails` | guardrail ids, versions, status | Bedrock Guardrails area |
| `bedrock:GetGuardrail` | contentPolicy, sensitiveInformationPolicy, topicPolicy, wordPolicy, contextualGroundingPolicy, kmsKeyId, blocked messaging | Bedrock Guardrails area |

## Knowledge bases / RAG (KB)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:ListKnowledgeBases` | KB ids, status | Knowledge Bases / RAG area |
| `bedrock-agent:GetKnowledgeBase` | `embeddingModelArn`, `storageConfiguration`, KMS config, vector store type | Knowledge Bases / RAG area |
| `bedrock-agent:ListDataSources` / `GetDataSource` | chunking config, parsing config, data source KMS, S3 config | Knowledge Bases / RAG area |
| `bedrock-agent:ListIngestionJobs` | per-source job history (empty = never synced) | Knowledge Bases / RAG area |
| `bedrock-agent:GetIngestionJob` | latest `status`, `statistics` (docs scanned/indexed/failed), `failureReasons` | Knowledge Bases / RAG area |

## Agents & action groups (AGT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:ListAgents` | agent ids, status | Bedrock Agents area |
| `bedrock-agent:GetAgent` | `guardrailConfiguration`, `foundationModel`, `memoryConfiguration`, prompt override config | Bedrock Agents area |
| `bedrock-agent:ListAgentActionGroups` / `GetAgentActionGroup` | action group executor (Lambda ARN), API schema, parent action group signatures (code interpreter) | Bedrock Agents area |
| `bedrock-agent:ListAgentAliases` / `GetAgentAlias` | alias ids, routing config, version pinning | Bedrock Agents area |
| `bedrock-agent:ListAgentKnowledgeBases` | KBs attached to the agent | Knowledge Bases / RAG area |
| `lambda:GetPolicy` / `iam:GetRolePolicy` for action-group Lambda | execution-role permission scope | Bedrock Agents area |
| `bedrock-agent:ListPrompts` / `GetPrompt` | prompt versions in Prompt Management | Bedrock Agents and Bedrock invocation areas |

## Evaluation (EVAL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListEvaluationJobs` | job names, `status`, `jobType` (automated/human), creation times (empty = none ever) | LLM-EVAL-001, 002, 004 |
| `bedrock:GetEvaluationJob` | task type, metrics, dataset S3 locations, model targets, output location, failure reason | LLM-EVAL-003, 006, 009, 010, 011 |
| `s3:ListObjectsV2`/`HeadObject` on eval dataset+output prefixes | dataset last-modified (staleness), output versioning/retention | LLM-EVAL-003, 008 |
| `cloudwatch:ListMetrics` (namespace `OpsAI/Evaluation`) | whether eval scores are published as metrics | LLM-EVAL-005 |
| `bedrock:ListEvaluationJobs` / `GetEvaluationJob` for a RAG evaluation ([GetEvaluationJob](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetEvaluationJob.html), [EvaluationSummary](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_EvaluationSummary.html)) | `applicationType` (`ModelEvaluation` \| `RagEvaluation`), `inferenceConfig` / `inferenceConfigSummary` (knowledge base evaluated; `ragIdentifiers` is deprecated), `failureMessages` | LLM-EVAL-009, 011 |

## SageMaker-side evaluation (SM-EVAL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListTrainingJobs` / `DescribeTrainingJob` for a Nova eval-recipe job (SageMaker-side evaluation runs as a recipe-driven job) | eval job status, `FailureReason`, eval-dataset S3 path, judge-model reference | LLM-SM-EVAL-001, 002 |
| `s3:ListObjectsV2` / `HeadObject` on the eval output prefix | whether eval output was produced and retained | LLM-SM-EVAL-003 |
| `cloudwatch:ListMetrics` (namespace `OpsAI/Evaluation`) | whether SageMaker-side eval scores are published as metrics | LLM-SM-EVAL-003 |

## SageMaker inference (SM)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `sagemaker:ListEndpoints` / `DescribeEndpoint` | endpoint status, `ProductionVariants[].CurrentInstanceCount`, variant weights, DataCaptureConfig status | SageMaker endpoint area |
| `sagemaker:DescribeEndpointConfig` | variant instance type/count, `KmsKeyId`, `DataCaptureConfig`, serverless config | SageMaker endpoint area |
| `sagemaker:DescribeModel` | `VpcConfig`, container/image, model data URL | SageMaker endpoint area |
| `application-autoscaling:DescribeScalableTargets` / `DescribeScalingPolicies` | registered scaling targets/policies for the variant | SageMaker endpoint area |
| `sagemaker:ListMonitoringSchedules` / `DescribeMonitoringSchedule` | Model Monitor schedules attached | SageMaker endpoint area |
| `sagemaker:ListInferenceRecommenderJobs` | whether right-sizing was run | SageMaker endpoint area |
| `sagemaker:ListModelPackages` / `DescribeModelPackage` | registry lineage / approval status | SageMaker Model Registry area |

## Observability (OBS)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `cloudwatch:ListMetrics` | presence of metrics in `AWS/Bedrock`, `AWS/Bedrock/Guardrails`, `AWS/Bedrock/Agents`, `AWS/SageMaker`, `/aws/sagemaker/Endpoints` | metric-presence checks in each owning area |
| `cloudwatch:GetMetricData` / `GetMetricStatistics` | metric values over the window (latency, errors, throttles, tokens, utilization) | invocation, agent and SageMaker endpoint areas; LLM-EVAL-014 for `OutputTokenCount` / `Invocations` |
| `cloudwatch:DescribeAlarms` | which alarms exist vs the recommended set | SageMaker endpoint area, alarm gaps |
| `logs:DescribeLogGroups` | existence of the Bedrock invocation log group | Bedrock invocation-logging area |
| `logs:StartQuery`/`GetQueryResults` (Logs Insights) | invocation-log error patterns (see metrics-and-logs.md) | Bedrock invocation-logging area; LLM-EVAL-012 for the `stopReason` distribution |

## Cost (COST)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `ce:GetCostAndUsage` | spend by service (`Amazon Bedrock`, `Amazon SageMaker`), grouped by `USAGE_TYPE` | Bedrock spend area; SageMaker endpoint area for endpoint cost |
| `ce:GetCostAndUsage` with token usage types | input/output token usage-type spend per model | Bedrock spend area |
| `cloudwatch:GetMetricData` on `InputTokenCount`/`OutputTokenCount` | token volume for spend modeling | Bedrock spend area |

## AgentCore (AC)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agent:GetAgentRuntime` / `ListAgentRuntimes` | runtime status, version, endpoint, role ARN | Bedrock AgentCore area |
| `iam:SimulatePrincipalPolicy` (on runtime role) | permission eval for bedrock:InvokeModel, s3:GetObject, logs:PutLogEvents | Bedrock AgentCore and Bedrock model-access areas |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP policies affecting the account | Bedrock AgentCore and Bedrock model-access areas |
| `ec2:DescribeVpcEndpoints` | VPC endpoint presence for bedrock-runtime, bedrock-agent-runtime, s3, logs, monitoring | Bedrock AgentCore area |
| `bedrock-agent:GetAgentGateway` / `ListAgentGateways` | gateway config, targets, auth | Bedrock AgentCore area |
| AgentCore Observability (OTLP config inspection) | telemetry enablement, span coverage | Bedrock AgentCore area |

## Telemetry coverage (TEL)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `logs:DescribeMetricFilters` | metric filters on Bedrock invocation log group (finish-reason, error patterns) | LLM-EVAL-013 for the `stopReason` filter; telemetry-coverage view in the live-failure triage area |
| `cloudwatch:ListDashboards` | presence of a GenAI-specific dashboard | live-failure triage area (telemetry coverage) |
| `logs:DescribeLogGroups` | log retention, log format (structured JSON vs text) | live-failure triage area (telemetry coverage) |
| `health:DescribeEvents` | active service events in region (for transient classifier) | live-failure triage area (transient-vs-config) |

## Access control (cross-cutting additions)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `iam:SimulatePrincipalPolicy` | policy simulation for specific Bedrock actions | Bedrock model-access and Bedrock AgentCore areas |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP deny detection | Bedrock model-access and Bedrock AgentCore areas |
| `bedrock:GetFoundationModelAvailability` / model access page | model access + marketplace subscription status | Bedrock model-access area |
| `health:DescribeEvents` | active Bedrock service events in region | live-failure triage area (transient-vs-config) |

## Security (SEC) — cross-cutting

Security findings are produced by the KMS/VPC/IAM fields above rather than a separate family of calls:
- Encryption: `KmsKeyId` from guardrail, KB storage, data source, SageMaker endpoint config; S3 bucket encryption on logging/eval/data-source buckets.
- Network: `VpcConfig` on SageMaker models; vector store network policy.
- IAM: policy scope for `bedrock:InvokeModel*` and action-group Lambda roles.
Feeds the Bedrock access, Guardrails, Knowledge Bases and SageMaker endpoint areas.
