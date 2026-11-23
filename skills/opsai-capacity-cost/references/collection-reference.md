# Collection Reference

The exact **read-only** API calls this skill uses to collect state, and the fields each contributes, by family. All calls are describe/list/get; none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Naming: the IAM action prefix for every Bedrock control-plane call here is `bedrock:` (`bedrock-agent` is the CLI and SDK client name for agents and knowledge bases, not an IAM prefix; this skill makes no such calls). AgentCore actions use the `bedrock-agentcore:` prefix and belong to `opsai-bedrock-agentcore`, not to this skill. The data-plane clients `bedrock-runtime` and `bedrock-mantle` are **not** used for collection (they invoke models).

**Permissions.** Every read below is granted by the AWS managed policy `AIDevOpsAgentAccessPolicy` except `pricing:GetProducts`. The `EnableOpsaiCapacityCost` parameter of `cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml` adds it. Without it the token model reads prices from the Bedrock pricing page with `verify_aws_claim`, or marks the model "unpriced: pricing:GetProducts denied" (cost-analysis.md §1b); every other check runs unchanged. `iam:SimulatePrincipalPolicy` and `s3:GetObject` are not used: the agent runtime refuses the first even when granted, and the second returns customer data.

---

## Model invocation (INV)

| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListInferenceProfiles` / `bedrock:GetInferenceProfile` | profile ids, type (SYSTEM_DEFINED/APPLICATION), member regions/models; `GetInferenceProfile` rejects a model ID, which marks a direct call | LLM-INV-002, LLM-COST-005, quota form (api-quirks §18 step 1) |
| `bedrock:GetFoundationModel` / `bedrock:ListFoundationModels` | `providerName`, `modelName`, `modelLifecycle.status` for the quota-name match and the PT end-of-life check | quota headroom, LLM-PT-003 |
| `bedrock:GetModelInvocationLoggingConfiguration` | `loggingConfig` (cloudWatchConfig, s3Config): the log destination whose retention LLM-COST-006 reads | LLM-COST-006, Step 2b log queries |

## Provisioned throughput (PT)

| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListProvisionedModelThroughputs` | provisioned model ARNs, `status`, `modelUnits`, `commitmentDuration` | LLM-PT-001/002/003 |
| `bedrock:GetProvisionedModelThroughput` | per-PT model units, model ARN, creation/commitment times | LLM-PT-001/003 |

## Observability (OBS)

| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `cloudwatch:ListMetrics` | presence of metrics in `AWS/Bedrock`, `AWS/BedrockMantle`, `AWS/Bedrock/Batch` and the `ModelId` forms in use | Step 2 |
| `cloudwatch:GetMetricData` / `cloudwatch:GetMetricStatistics` | metric values over the window (tokens, throttles, client errors, quota use) | all COST, PT and INV checks |
| `cloudwatch:DescribeAlarms` | which alarms exist vs the recommended set | Step 7 (cloudwatch-alarm-reference.md) |
| `logs:DescribeLogGroups` | existence, `creationTime`, `retentionInDays` and `storedBytes` of the Bedrock invocation log group | LLM-COST-006, Step 2b |
| `logs:StartQuery` / `logs:GetQueryResults` (Logs Insights) | `stopReason`, `outputTokenCount` tail, cache fields, prefix hashes (metrics-and-logs.md) | LLM-COST-001, 002 confirmation |

## Cost (COST)

| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `ce:GetCostAndUsage` with `GroupBy Type=PRODUCT_ATTRIBUTE,Key=model` (or `provider`, `inferenceType`, `feature`), **no** SERVICE filter | billed Bedrock spend per model / provider / token type (windows before product-attribute data exists → `DataUnavailableException`; fall back to `USAGE_TYPE`) | billed cost model, all COST checks |
| `ce:GetCostAndUsage` grouped by `USAGE_TYPE` | billed spend per model × token type (input, output, cache-read, cache-write) × tier (`-flex`/`-priority`) × routing (`-cross-region-global`); PT model-unit hours; reserved-TPM lines | billed cost model, LLM-COST-001..006, LLM-PT-001 |
| `ce:GetDimensionValues` (`SERVICE` with `SearchString=Bedrock`) | every service name Bedrock costs appear under | billed cost model (avoids undercount, api-quirks §16) |
| `ce:ListCostAllocationTags` (management account only; `AccessDenied` from a member account is expected) | activation state of the cost allocation tag keys used for per-team splits | per-caller attribution (cost-analysis §1a.5) |
| `pricing:GetProducts` (us-east-1 endpoint; `AmazonBedrockFoundationModels` or `AmazonBedrock`, filter `regionCode` + `model`, or `titanModel` for Titan; one call per model). **Not in the managed policy**: see Permissions above | published per-token rates by token type, with tier and routing in `usagetype` | token model (cross-check / fallback), what-ifs (cost-analysis.md §1b) |
| Bedrock pricing page (https://aws.amazon.com/bedrock/pricing/), read with `verify_aws_claim` | published per-token rates by model, region, token type, tier and routing, with the date read | token model (fallback when `pricing:GetProducts` is denied), LLM-COST-003/004 what-ifs |
| `cloudwatch:GetMetricData` on `InputTokenCount`/`OutputTokenCount`/`CacheReadInputTokenCount`/`CacheWriteInputTokenCount` | token volume per type for the token model (cross-check / fallback) | LLM-COST-001, 002 |
| `servicequotas:GetServiceQuota` (one call per quota code, from quota-codes.md or the user); `servicequotas:ListServiceQuotas` only for a user-requested sweep; `servicequotas:ListRequestedServiceQuotaChangeHistory` when the user mentions an earlier increase (service code `bedrock`; boto3 client `service-quotas`) | applied per-model tokens-per-minute / requests-per-minute / tokens-per-day quota values (on-demand, cross-region, global, `[bedrock-mantle endpoint]` input/output) | quota headroom (`EstimatedTPMQuotaUsage` ÷ quota), LLM-PT-002 |
| `cloudwatch:GetMetricData` on `EstimatedTPMQuotaUsage` (`Sum`, 60 s, trailing 15 days, per `ModelId`) | peak per-minute quota use | quota headroom (SKILL.md Step 6) |
| `cloudwatch:GetMetricData` on `InvocationThrottles`/`InvocationClientErrors` per `ModelId` **and** with no dimension | throttles and quota rejections, including requests that failed before model resolution | LLM-INV-007, LLM-PT-002 |
| `cloudwatch:GetMetricData` on `AWS/BedrockMantle` `TotalInputTokens`/`TotalOutputTokens`/`InferenceClientErrors` by `Model` | token volume and errors for bedrock-mantle endpoint traffic (no throttle metric) | token model, LLM-INV-007 (api-quirks §20) |
| `logs:DescribeLogGroups` / `s3:GetLifecycleConfiguration` (CLI `aws s3api get-bucket-lifecycle-configuration`) on the invocation-log destination | `retentionInDays`, `storedBytes`; S3 lifecycle expiration on the logging prefix | LLM-COST-006 |

## Not collected here

Guardrails (GRD), knowledge bases (KB), agents (AGT), AgentCore (AC), evaluation (EVAL), SageMaker (SM), telemetry coverage (TEL), IAM policy simulation and SCP reads belong to the sibling skills named in `related-skills.md`. This skill raises none of their checks and makes none of their calls; the fallback in that file is the only read it makes in those areas.
