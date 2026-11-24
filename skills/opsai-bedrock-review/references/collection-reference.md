# Collection Reference
The exact **read-only** API calls this skill uses to collect state, and the fields each contributes, by family. All calls are describe/list/get; none mutate state. Use ReadOnly or least-privilege credentials (production safety).

Naming: the API column names **IAM actions**. Knowledge base, data source and agent calls authorize under the `bedrock:` prefix (the CLI and SDK client is `aws bedrock-agent`, which is not an IAM prefix). The data-plane clients `bedrock-runtime` and `bedrock-agent-runtime` are not used for collection, with one exception: the optional, bounded `Retrieve` probe of the RAG review (`rag-review-playbook.md` Step 8), which returns counts, URIs and scores and never chunk text in the answer. `RetrieveAndGenerate` is never called.

**Permissions.** The AWS managed policy `AIDevOpsAgentAccessPolicy` grants every read below except `bedrock:GetIngestionJob`, `bedrock:GetFoundationModelAvailability` and `s3:GetBucketPolicyStatus`. The `EnableOpsaiBedrockReview` parameter of [devops-agent-skill-policies.yaml](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) adds them. Without them the skill reads ingestion statistics from the `ListIngestionJobs` summaries, judges model access from the error text and CloudTrail, and reports the bucket's public status from `s3:GetBucketPolicy` and `s3:GetBucketPublicAccessBlock`. The template leaves out `iam:SimulatePrincipalPolicy` (the agent runtime refuses it even when granted; fallback below), `bedrock:Retrieve` (returns chunk text) and `s3:GetObject` (returns customer data).

---
## Model invocation (INV)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:GetModelInvocationLoggingConfiguration` | `loggingConfig` (`cloudWatchConfig` incl. `largeDataDeliveryS3Config`, `s3Config`, text/image/embedding/video/audio delivery flags) | LLM-INV-001, 005, 010 |
| `bedrock:GetFoundationModel` | `modelLifecycle.status`, `inferenceTypesSupported`; `ResourceNotFoundException` "reached the end of its life" = EOL | LLM-INV-003, 002 |
| `bedrock:ListFoundationModels` | `modelSummaries[].modelId`, `modelLifecycle.status`, I/O modalities, streaming support | LLM-INV-003, 006 |
| `bedrock:ListInferenceProfiles` / `bedrock:GetInferenceProfile` | profile ids, type (SYSTEM_DEFINED/APPLICATION), member regions/models | LLM-INV-002 |
| `bedrock:GetFoundationModelAvailability` (not in the managed policy) | `agreementAvailability.status`, `authorizationStatus`, `entitlementAvailability`, `regionAvailability` | LLM-INV-014 |
| `bedrock:ListModelInvocationJobs` | batch inference jobs in use | LLM-INV-009 |
| `bedrock:ListPrompts` | whether Prompt Management holds the prompts | LLM-INV-012 |
| `iam:GetPolicy` / `iam:GetPolicyVersion`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies` / `iam:GetRolePolicy` | `bedrock:InvokeModel*` resource scope and conditions | LLM-INV-004, 013 |
| `s3:GetEncryptionConfiguration`, `s3:GetBucketPolicyStatus` (not in the managed policy), `s3:GetBucketPublicAccessBlock`, `s3:GetBucketPolicy` on the S3 logging destination | encryption and public exposure of the log bucket | LLM-INV-010 |

## Knowledge bases / RAG (KB)
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `bedrock:ListKnowledgeBases` | KB ids, status | LLM-KB-008 |
| `bedrock:GetKnowledgeBase` | `embeddingModelArn`, `storageConfiguration` (vector store type and its ARN); the response has no KMS field, so encryption is read from the data source and the vector store | LLM-KB-004, 006 |
| `bedrock:ListDataSources` / `bedrock:GetDataSource` | chunking and parsing configuration, `serverSideEncryptionConfiguration`, S3 configuration | LLM-KB-003, 005 |
| `bedrock:ListIngestionJobs` | per-source job history (empty = never synced), per-job `statistics` | LLM-KB-001, 002, 010 |
| `bedrock:GetIngestionJob` (not in the managed policy) | latest `status`, `statistics` (documents scanned/indexed/failed), `failureReasons` | LLM-KB-002, 011 |
| `bedrock:ListAgents` → `bedrock:ListAgentVersions` → `bedrock:ListAgentKnowledgeBases` | which agent versions attach the KB | LLM-KB-008 |
| `bedrock:ListEvaluationJobs` | RAG evaluation jobs for the KB | LLM-KB-009 |
| `aoss:BatchGetCollection`, `aoss:ListSecurityPolicies` / `aoss:GetSecurityPolicy` | vector store encryption and network policy (OpenSearch Serverless) | LLM-KB-006 |
| `iam:GetRole` (trust policy), `iam:GetRolePolicy` / `iam:GetPolicyVersion` on the KB role, `s3:GetBucketPolicy` | KB role permissions and trust, cross-account bucket-policy deny | LLM-KB-011 |
| `servicequotas:GetServiceQuota` (service code `bedrock`) | embedding-model requests-per-minute quota and KB / `Retrieve` request-rate quotas | LLM-KB-012 |
| `cloudwatch:GetMetricData` | `InvocationThrottles` for the embedding model and other retrieval-path throttle counts over the window | LLM-KB-012 |

## Observability
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `cloudwatch:ListMetrics` / `cloudwatch:GetMetricData` | `AWS/Bedrock` invocation, error, throttle and log-delivery metrics | LLM-INV-005, 007 |
| `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:DescribeMetricFilters` | the invocation log group exists, receives streams, and has filters | LLM-INV-001, 005 |
| `logs:StartQuery` / `logs:GetQueryResults` (Logs Insights) | invocation-log usage patterns (see `metrics-and-logs.md`) | LLM-INV-002, 006, 011 |
| `health:DescribeEvents` | active Bedrock service events in the Region, for the service-vs-customer transient verdict before any customer fix | LLM-KB-002, 011, 012 |

## Access control
| API (IAM action) | Fields contributed | Feeds checks |
|---|---|---|
| `organizations:DescribeOrganization` | `AWSOrganizationsNotInUseException` = not in an Organization (LLM-INV-015 not applicable) | LLM-INV-015 |
| `organizations:ListPoliciesForTarget` / `organizations:DescribePolicy` (management account or delegated administrator only) | SCP deny detection | LLM-INV-015, LLM-KB-011 |
| `cloudtrail:LookupEvents` (`EventSource=bedrock.amazonaws.com`) | failed `InvokeModel`/`Converse` calls (management events, 90 days); the DevOps Agent runtime may block it | LLM-INV-013, 014, 015 |

**Fallback when `iam:SimulatePrincipalPolicy` is denied** (it is refused in the DevOps Agent runtime): read the caller's or KB role's identity policies (`iam:ListAttachedRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicyVersion`) and the SCPs above, check each action against them, and label the verdict "read from policy documents, not simulated" (`diagnosis-playbook.md`).
