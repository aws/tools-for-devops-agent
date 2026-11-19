# Collection Reference

The exact **read-only** API calls the agent uses to collect state, and the fields each contributes, organized by family. All calls are describe/list/get — none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Bedrock has two control-plane clients: `bedrock` (model/eval/guardrail/PT config, logging config, enforcements) and `bedrock-agent` (agents, flows, knowledge bases, data sources). Rows are named by **IAM action**, and the IAM action prefix for both clients is `bedrock:` (for example `bedrock:GetAgent`, `bedrock:GetFlow`); the AgentCore control plane uses `bedrock-agentcore:`. The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are **not** used for collection (they invoke models and guardrails).

---

## Model invocation (INV)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:GetModelInvocationLoggingConfiguration` | `loggingConfig` (cloudWatchConfig, s3Config, text/image/embedding delivery flags) | LLM-INV-001, 005, 010 |
| `bedrock:ListFoundationModels` | `modelSummaries[].modelId`, `modelLifecycle.status`, I/O modalities, streaming support | LLM-INV-003 |
| `bedrock:ListInferenceProfiles` / `GetInferenceProfile` | profile ids, type (SYSTEM_DEFINED/APPLICATION), member regions/models | LLM-INV-002, LLM-COST-005 |
| `bedrock:GetFoundationModelAvailability` (where available) | per-model access/availability in region | LLM-INV-004 |
| `iam:GetPolicy`/`GetPolicyVersion`/`SimulatePrincipalPolicy` | `bedrock:InvokeModel*` resource scope and conditions | LLM-INV-004 |

## Provisioned throughput (PT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListProvisionedModelThroughputs` | provisioned model ARNs, `status`, `modelUnits`, `commitmentDuration` | LLM-PT-001/002/003 |
| `bedrock:GetProvisionedModelThroughput` | per-PT model units, model ARN, creation/commitment times | LLM-PT-001/003 |

## Guardrails (GRD)

### Guardrail configuration and enforcement reads

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListGuardrails` | guardrail ids, ARNs, `status`; without `guardrailIdentifier` it returns one DRAFT row per guardrail, so pass the guardrail ARN as `guardrailIdentifier` to list its published versions. Never conclude "no published version" from the unfiltered list. | LLM-GRD-001, 006 |
| `bedrock:GetGuardrail` (always pass the `guardrailVersion` the path enforces; without it the DRAFT is returned) | `version`, `status`; `contentPolicy.filters[]` (`type`, `inputStrength`, `outputStrength`, `inputAction`, `outputAction`, `inputEnabled`, `outputEnabled`); `sensitiveInformationPolicy.piiEntities[]` / `regexes[]` (`action`, `inputAction`, `outputAction`, `inputEnabled`, `outputEnabled`; an entry can carry only `action`, see `api-quirks.md` §17); `topicPolicy.topics[]` and `wordPolicy.managedWordLists[]` / `words[]` (same action/enabled fields); `contextualGroundingPolicy.filters[]` (`type`, `threshold`, `action`, `enabled`) and `contextualGroundingPolicy.tier.tierName` (optional; with no tier set AWS uses Classic); `blockedInputMessaging`, `blockedOutputsMessaging`; `kmsKeyArn` | LLM-GRD-002..005, 008..011 |
| `bedrock:ListEnforcedGuardrailsConfiguration` (per Region, paginate on `nextToken`) | `guardrailsConfig[]`: `guardrailArn`, `guardrailId`, `guardrailVersion`, `modelEnforcement.includedModels` / `excludedModels`, `selectiveContentGuarding.system` / `messages`, `inputTags`, `updatedAt`. Empty array = no account-level enforcement in that Region. | LLM-GRD-001, 021 |
| `organizations:DescribeEffectivePolicy` with `PolicyType` `BEDROCK_POLICY` (callable from any account in the organization; omit `TargetId` to describe the calling account, pass an account id only from the management account) | `EffectivePolicy.PolicyContent` (the enforced guardrail identifier/version and model scope), `LastUpdatedTimestamp`. `EffectivePolicyNotFoundException` = no organization-level enforcement; `AWSOrganizationsNotInUseException` (not in an Organization) or AccessDenied = **disclosed gap, not "no enforcement"**. | LLM-GRD-001, 021 |
| `kms:DescribeKey` on `kmsKeyArn` | `KeyMetadata.KeyManager` (`AWS` \| `CUSTOMER`) | LLM-GRD-010 |

### Which guardrail and version does each production path enforce (Steps 1, 1a, 7)

Resolve every production path with the rows below and record `path → guardrailArn:guardrailVersion → origin`. The `GetGuardrail` reads in Steps 3–10 are made against **those** versions.

| Path | Read | Field that answers it | Notes |
|---|---|---|---|
| (a) Every invocation in the account / organization | `bedrock:ListEnforcedGuardrailsConfiguration`; `organizations:DescribeEffectivePolicy` `BEDROCK_POLICY` | `guardrailsConfig[].guardrailArn` + `guardrailVersion`; effective policy content | Origin `ACCOUNT_ENFORCED` / `ORGANIZATION_ENFORCED`. Guards every `InvokeModel`/`Converse` call without a request-level guardrail, subject to `modelEnforcement` include/exclude lists. If present, LLM-GRD-001 is not raised; evaluate this version. |
| (b) Amazon Bedrock Agent | `bedrock:GetAgent` → `agent.guardrailConfiguration.{guardrailIdentifier, guardrailVersion}` (the working copy); `bedrock:ListAgentAliases` / `GetAgentAlias` → `routingConfiguration[].agentVersion` for the alias production invokes | guardrail identifier + version recorded on the **agent version the alias serves** (`bedrock:GetAgentVersion` → `agentVersion.guardrailConfiguration`; inline grant, see README) | If `GetAgentVersion` is denied, report the working copy's guardrail as "could not confirm for the served version" and let (d)/(e) decide. Agent attachment itself is also LLM-AGT-001 territory; GRD evaluates the attached version's strength. |
| (c) Amazon Bedrock Flow | `bedrock:ListFlows` / `GetFlow` → `definition.nodes[].configuration.prompt.guardrailConfiguration` and `.knowledgeBase.guardrailConfiguration` | `guardrailIdentifier`, `guardrailVersion` per prompt node and knowledge-base node | `bedrock:GetFlow` is in `ReadOnlyAccess` but not in `AIDevOpsAgentAccessPolicy` → needs an inline grant (README); if denied, disclose the gap. |
| (d) Which versions actually receive traffic (any path, independent of trace) | `cloudwatch:GetMetricData`, namespace `AWS/Bedrock/Guardrails`, metric `Invocations`, dimensions `GuardrailArn` + `GuardrailVersion` (value: version number or `DRAFT`), Sum over 14–30 days; compare with namespace `AWS/Bedrock`, metric `Invocations` summed over the `ModelId` values of the generation models in the same Region and window | versions with non-zero `Invocations` = enforced in practice. The metric counts guardrail evaluations, and inline `Converse` calls with `guardrailConfig` emit it: an allowed call adds 2 (input and output evaluated), a call blocked at the input adds 1, and either call adds 1 to model `Invocations`. Guardrail series carry no `ModelId`, so compare totals, not models: with M = model `Invocations` and E = guardrail `Invocations` summed over all versions, at least M − E calls were unguarded when M > E (a lower bound, assuming each guarded call adds at least one evaluation); when E ≥ M the comparison shows nothing. Measured on non-streaming `Converse` with one model in one Region; other paths (`ConverseStream`, `InvokeModel`, agents, flows, `RetrieveAndGenerate`) not measured | `GuardrailVersion` `DRAFT` with traffic is LLM-GRD-006 evidence. No datapoints = no traffic measured, not a measured zero. AWS's metrics page describes `Invocations` as requests to the `ApplyGuardrail` API operation, but inline evaluations are counted too. Do not use dimension `Operation` to isolate standalone `ApplyGuardrail` calls: those series are account-wide, carry no `GuardrailArn`, and include the inline evaluations; the `GuardrailContentSource` `Input`/`Output` split exists only on them. |
| (e) App `InvokeModel`/`Converse` and `RetrieveAndGenerate` paths, when model invocation logging is enabled | `bedrock:GetModelInvocationLoggingConfiguration` → `loggingConfig.cloudWatchConfig.logGroupName`; then `logs:StartQuery` / `GetQueryResults` (query below) | `output.outputBodyJson.trace.guardrail.inputAssessment.*.appliedGuardrailDetails.{guardrailArn, guardrailVersion, guardrailOrigin}`, `output.outputBodyJson.stopReason` = `guardrail_intervened`; request side `input.inputBodyJson.guardrailConfig.{guardrailIdentifier, guardrailVersion}` (`Converse`/`ConverseStream` only; `InvokeModel` passes the guardrail as request headers that the log body does not carry) | Trace fields are expected when the caller enabled `trace` (AWS: "If you enabled tracing, the trace is available"); AWS does not say what a response holds otherwise, and for an enforced guardrail it says only that the response "will include enforced guardrail information". "No guardrail evidence in logs" is **"could not confirm"**, not "measured absent". Logged `Converse` request bodies may not carry `guardrailConfig` (observed absent in all traced guarded events of a test account), so an empty `requestGuardrail` never upgrades "could not confirm" to "measured absent". State per-model or per-path absence only as the aggregate bound in row (d). The guardrail on a `RetrieveAndGenerate` path is a request-time field (`generationConfiguration.guardrailConfiguration`) that only logs/metrics reveal — `GetKnowledgeBase` does not expose a guardrail. |

Logs Insights query for (e), run against the invocation log group (results carry ARNs: mask the account segment before quoting). `inputAssessment` is a map keyed by guardrail id, so the trace fields are read with `parse` rather than a dotted path:

```
fields @timestamp, operation, modelId,
  input.inputBodyJson.guardrailConfig.guardrailIdentifier as requestGuardrail,
  input.inputBodyJson.guardrailConfig.guardrailVersion as requestVersion,
  output.outputBodyJson.stopReason as stopReason
| parse @message /"appliedGuardrailDetails"\s*:\s*\{[^}]*"guardrailArn"\s*:\s*"(?<appliedArn>[^"]+)"/
| parse @message /"appliedGuardrailDetails"\s*:\s*\{[^}]*"guardrailVersion"\s*:\s*"(?<appliedVersion>[^"]*)"/
| parse @message /"guardrailOrigin"\s*:\s*\[\s*"(?<guardrailOrigin>[A-Z_]+)"/
| stats count(*) as calls,
        count(appliedArn) as withTrace,
        count(requestGuardrail) as withRequestGuardrail,
        sum(stopReason = "guardrail_intervened") as intervened
  by operation, modelId, appliedArn, appliedVersion, guardrailOrigin, requestGuardrail, requestVersion
| sort calls desc
```

A group with `withTrace` = 0 and `withRequestGuardrail` = 0 is "could not confirm" (trace disabled, or the guardrail passed as `InvokeModel` headers), not an unguarded path; an account- or organization-enforced guardrail appears only in the trace (`guardrailOrigin`), never in the request body. `appliedVersion` `DRAFT` with traffic is LLM-GRD-006 evidence. `withRequestGuardrail` = 0 (and empty `requestGuardrail` / `requestVersion` columns) is the normal result for `Converse` and carries no information. `appliedArn` (counted as `withTrace`) shows the guardrail was applied to the call, not which policy evaluated or acted on it. The `parse` lines above read one field each and cannot tell the input entry from an output element, so read an entry's key names, `detected` booleans and `usage` integers with one `parse` per field, never the `match` values or `modelOutput` (`api-quirks.md` §18).

## Knowledge bases / RAG (KB)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListKnowledgeBases` | KB ids, status | LLM-KB-008 |
| `bedrock:GetKnowledgeBase` | `embeddingModelArn`, `storageConfiguration`, KMS config, vector store type (no guardrail field: the `RetrieveAndGenerate` guardrail is request-time, see GRD row (e)) | LLM-KB-004, 005, 006 |
| `bedrock:ListDataSources` / `GetDataSource` | chunking config, parsing config, data source KMS, S3 config | LLM-KB-003, 005 |
| `bedrock:ListIngestionJobs` | per-source job history (empty = never synced) | LLM-KB-001, 010 |
| `bedrock:GetIngestionJob` | latest `status`, `statistics` (docs scanned/indexed/failed), `failureReasons` | LLM-KB-002 |

## Agents & action groups (AGT)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListAgents` | agent ids, status | LLM-AGT-004 |
| `bedrock:GetAgent` | `guardrailConfiguration`, `foundationModel`, `memoryConfiguration`, prompt override config | LLM-AGT-001, 003, 008, 009 |
| `bedrock:ListAgentActionGroups` / `GetAgentActionGroup` | action group executor (Lambda ARN), API schema, parent action group signatures (code interpreter) | LLM-AGT-002, 006 |
| `bedrock:ListAgentAliases` / `GetAgentAlias` | alias ids, routing config, version pinning | LLM-AGT-007 |
| `bedrock:ListAgentKnowledgeBases` | KBs attached to the agent | LLM-KB-008 |
| `lambda:GetPolicy` / `iam:GetRolePolicy` for action-group Lambda | execution-role permission scope | LLM-AGT-002 |
| `bedrock:ListPrompts` / `GetPrompt` | prompt versions in Prompt Management | LLM-AGT-003, LLM-INV-012 |

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
| `ce:GetCostAndUsage` | spend by service (`Amazon Bedrock`, `Amazon SageMaker`), grouped by `USAGE_TYPE` | all COST checks |
| `ce:GetCostAndUsage` with token usage types | input/output token usage-type spend per model | LLM-COST-001..004 |
| `cloudwatch:GetMetricData` on `InputTokenCount`/`OutputTokenCount` | token volume for spend modeling | LLM-COST-001, 002 |

## AgentCore (AC)

| API (service) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock-agentcore:GetAgentRuntime` / `ListAgentRuntimes` | runtime status, version, endpoint, role ARN | LLM-AC-001, 009 |
| `iam:SimulatePrincipalPolicy` (on runtime role) | permission eval for bedrock:InvokeModel, s3:GetObject, logs:PutLogEvents | LLM-AC-001, LLM-INV-013 |
| `organizations:ListPoliciesForTarget` / `DescribePolicy` | SCP policies affecting the account | LLM-AC-002, LLM-INV-015 |
| `ec2:DescribeVpcEndpoints` | VPC endpoint presence for bedrock-runtime, bedrock-agent-runtime, s3, logs, monitoring | LLM-AC-003 |
| `bedrock-agentcore:GetGateway` / `ListGateways` | gateway config, targets, auth | LLM-AC-004, 008 |
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
- Encryption: `kmsKeyArn` from the guardrail (`GetGuardrail`); `KmsKeyId` from KB storage, data source, SageMaker endpoint config; S3 bucket encryption on logging/eval/data-source buckets.
- Network: `VpcConfig` on SageMaker models; vector store network policy.
- IAM: policy scope for `bedrock:InvokeModel*` and action-group Lambda roles.
Feeds LLM-INV-004/010, LLM-GRD-010, LLM-KB-005/006, LLM-SM-006/007, LLM-AGT-002.
