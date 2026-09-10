# Amazon Bedrock Security Checks (BR-01..BR-33)

This reference lists the 33 Amazon Bedrock security checks. Each check is
read-only (list/describe/get only) and reports `Passed`, `Failed`, or `N/A`.

Every check carries a **Verifiability** classification that the report engine must
honor (see `SKILL.md` → "Verify vs. prescribe"):

- **Verifiable** — a read-only call returns the exact configuration; the verdict
  is deterministic.
- **Heuristic** — readable, but the verdict is an inference; apply the stated rule
  exactly, cite the evidence in `Finding_Details`, and emit `N/A` (not `Passed`)
  when evidence is ambiguous or the read is denied.
- **Prescribe-only** — not provable read-only under the DevOps Agent; emit `N/A`
  with remediation in `Resolution`. **Never `Passed`/`Failed`.**

Global checks (`BR-01`, `BR-03`, `BR-14`, `BR-15`) derive from IAM/Organizations
data and are emitted once per execution (per account in multi-account runs);
regional checks run in each scanned region that has relevant Bedrock resources.

**Classification summary:** Verifiable — BR-02, 04, 05, 06, 09, 11, 12, 13, 15,
16, 17, 20, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33 (22). Heuristic — BR-01, 03,
07, 08, 10, 18, 19, 21, 22, 25 (10). Prescribe-only — BR-14 (1).

---

### BR-01: AWS IAM Least Privilege
- **Severity:** High
- **Scope:** Global
- **Verifiability:** Heuristic
- **Read-only APIs:** `iam:ListAttachedRolePolicies`, `iam:ListAttachedUserPolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListRolePolicies`, `iam:ListUserPolicies`, `iam:GetRolePolicy`, `iam:GetUserPolicy`
- **Evaluate:** `Failed` when an IAM role or user attaches the broad `AmazonBedrockFullAccess` managed policy. `Passed` only when Bedrock-permissioned principals are found and none attach `AmazonBedrockFullAccess` (cite each principal + policy inspected). `N/A` when no Bedrock-related principals exist, or the IAM reads are denied. Do not infer least-privilege beyond the explicit `AmazonBedrockFullAccess`/wildcard rule; ambiguous scoping is `N/A`, not `Passed`.
- **Resolution:** Replace `AmazonBedrockFullAccess` with a least-privilege policy scoped to the specific Bedrock actions and resources required.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam-awsmanpol.html

### BR-02: Amazon VPC Endpoint Configuration
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `ec2:DescribeVpcEndpoints`
- **Evaluate:** `Failed` when no Bedrock interface VPC endpoints exist for private connectivity; `Passed` when Bedrock VPC endpoints are present; `N/A` when Bedrock is not in use in the region.
- **Resolution:** Create Amazon VPC interface endpoints for Bedrock so traffic stays on the AWS private network.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html

### BR-03: Marketplace Subscription Access
- **Severity:** Medium
- **Scope:** Global
- **Verifiability:** Heuristic
- **Read-only APIs:** `iam:ListAttachedRolePolicies`, `iam:GetPolicy`, `iam:GetPolicyVersion`, `iam:ListRolePolicies`, `iam:GetRolePolicy`
- **Evaluate:** `Failed` when an IAM policy grants wildcard `aws-marketplace:Subscribe` (or equivalent unscoped marketplace subscription) usable for Bedrock model access; `Passed` when subscription access is scoped to specific products (cite the policy). `N/A` when no principals grant marketplace access or reads are denied.
- **Resolution:** Restrict marketplace subscription actions to specific approved model products instead of wildcard access.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam-awsmanpol.html#security-iam-awsmanpol-bedrock-marketplace

### BR-04: Model Invocation Logging
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:GetModelInvocationLoggingConfiguration`
- **Evaluate:** `Failed` when model invocation logging is disabled; `Passed` when logging is enabled to CloudWatch or S3; `N/A` when Bedrock is not in use in the region. (Security-logging *presence* only; observability maturity is `bedrock-adoption-readiness`.)
- **Resolution:** Enable model invocation logging to capture request and response data for audit and monitoring.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html

### BR-05: Guardrail Configuration
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`
- **Evaluate:** `Failed` when no guardrails are configured in a region that uses Bedrock; `Passed` when guardrails exist; `N/A` when Bedrock is not in use in the region.
- **Resolution:** Create and apply Bedrock guardrails to enforce content and safety policies on model interactions.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html

### BR-06: AWS CloudTrail Logging
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `cloudtrail:ListTrails`, `cloudtrail:GetTrail`, `cloudtrail:GetTrailStatus`, `cloudtrail:GetEventSelectors`
- **Evaluate:** `Failed` when no active CloudTrail trail captures Bedrock API calls; `Passed` when a logging trail covers the Bedrock control plane; `N/A` when Bedrock is not in use in the region.
- **Resolution:** Configure an active CloudTrail trail (logging enabled) that records Bedrock management events.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html

### BR-07: Prompt Management
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agent:ListPrompts`, `bedrock-agent:GetPrompt` (Prompt Management is under `bedrock-agent`, not `bedrock`)
- **Evaluate:** `Failed` only when managed prompts exist but none carry a version (all are `DRAFT`, no numbered version) — a deterministic proxy for "version control". `Passed` when at least one versioned prompt variant exists (cite the prompt ID/version). `N/A` when no prompts are defined. Do not judge subjective "template quality".
- **Resolution:** Adopt Bedrock Prompt Management with versioned templates and variants for consistent, governed prompts.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-management.html

### BR-08: Agent AWS IAM Configuration
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agent:ListAgents`, `bedrock-agent:GetAgent`, `iam:ListRolePolicies`, `iam:GetRolePolicy`, `iam:ListAttachedRolePolicies`
- **Evaluate:** `Failed` when an agent execution role attaches `AdministratorAccess`/`*FullAccess` or an inline statement with `Action:"*"` or `Resource:"*"` on write actions (cite role + statement). `Passed` when every agent role is inspected and none match. `N/A` when no agents exist or role reads are denied.
- **Resolution:** Scope each agent execution role to the minimal actions and resources the agent requires.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_service-with-iam.html

### BR-09: Knowledge Base Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agent:ListKnowledgeBases`, `bedrock-agent:GetKnowledgeBase`
- **Evaluate:** `Failed` when a knowledge base lacks encryption configuration; `Passed` when encryption is configured; `N/A` when no knowledge bases exist in the region.
- **Resolution:** Enable encryption for Bedrock knowledge bases and their underlying data stores.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-kb.html

### BR-10: Guardrail AWS IAM Enforcement
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock:ListGuardrails`, `iam:ListRolePolicies`, `iam:GetRolePolicy`, `iam:ListAttachedRolePolicies`
- **Evaluate:** `Failed` when invoke-capable Bedrock policies exist but none carry a `bedrock:GuardrailIdentifier` condition key; `Passed` when an IAM condition requires a guardrail on invocation (cite the policy/condition). `N/A` when no guardrails or invoke policies exist, or reads are denied.
- **Resolution:** Add IAM condition keys that require an approved guardrail identifier on model invocation actions.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-permissions-id.html

### BR-11: Custom Model Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListCustomModels`, `bedrock:GetCustomModel`, `bedrock:GetModelCustomizationJob`
- **Evaluate:** `Failed` when a custom model has no `modelKmsKeyArn`; `Passed` when a KMS key is configured; `N/A` when no custom models exist in the region.
- **Resolution:** Configure customer-managed AWS KMS keys for custom (fine-tuned) model encryption.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-custom-job.html

### BR-12: Invocation Log Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:GetModelInvocationLoggingConfiguration`, `s3:GetBucketEncryption`
- **Evaluate:** `Failed` when the S3 destination for invocation logs is not encrypted with AWS KMS; `Passed` when logs are KMS-encrypted; `N/A` when invocation logging is not enabled.
- **Resolution:** Enable AWS KMS encryption on the S3 bucket that stores Bedrock invocation logs.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html

### BR-13: Flows Guardrails
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agent:ListFlows`, `bedrock-agent:GetFlow`
- **Evaluate:** `Failed` when a Bedrock Flow has no guardrail attached to its prompt nodes; `Passed` when flows enforce guardrails; `N/A` when no flows exist in the region.
- **Resolution:** Attach guardrails to the prompt nodes of each Bedrock Flow.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/flows-guardrails.html

### BR-14: Stale Bedrock Access
- **Severity:** Medium
- **Scope:** Global
- **Verifiability:** Prescribe-only
- **Read-only APIs:** *(none reachable)* — determination requires `iam:GenerateServiceLastAccessedDetails` then `iam:GetServiceLastAccessedDetails`. `GenerateServiceLastAccessedDetails` is a `Generate*` verb blocked by the DevOps Agent read-only guardrail, so the state cannot be read here.
- **Evaluate:** **Always `N/A`** under the DevOps Agent, with `Finding_Details` stating the platform read-only guardrail blocks the required analysis call. **Never emit `Passed` or `Failed`.** Do not call `GenerateServiceLastAccessedDetails`.
- **Resolution:** Out of band (e.g. IAM console → Access Advisor, or a Lambda with `iam:GenerateServiceLastAccessedDetails`), review last-accessed data for Bedrock-permissioned principals and remove permissions unused for 90+ days.
- **Reference:** https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_last-accessed.html

### BR-15: Cross-Account Guardrails Enforcement
- **Severity:** High
- **Scope:** Global
- **Verifiability:** Verifiable
- **Read-only APIs:** `organizations:DescribeOrganization`, `sts:GetCallerIdentity`, `organizations:ListRoots`, `organizations:ListPolicies`
- **Evaluate:** `Failed` when organization-level Bedrock policies (`BEDROCK_POLICY` type) are not enabled/attached at the org root; `Passed` when Bedrock policies enforce centralized guardrails; `N/A` when not run from the Organizations management account (cite that reason).
- **Resolution:** Enable the Bedrock policy type in AWS Organizations and attach Bedrock policies at the organization root for centralized enforcement.
- **Reference:** https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_bedrock.html

### BR-16: Guardrail Tier Validation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- **Evaluate:** `Failed` when a guardrail uses the `CLASSIC` content-filter tier; `Passed` when guardrails use the `STANDARD` tier (`contentPolicy.tier.tierName`); `N/A` when no guardrails exist in the region.
- **Resolution:** Upgrade guardrails to the STANDARD content-filter tier for broader protection.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-components.html

### BR-17: Custom Model Customer-Managed KMS Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListCustomModels`, `bedrock:GetCustomModel`
- **Evaluate:** `Failed` when a custom model is encrypted with an AWS-owned key instead of a customer-managed KMS key; `Passed` when a valid customer-managed key ARN is configured; `N/A` when no custom models exist in the region.
- **Resolution:** Recreate custom models with a customer-managed AWS KMS key for encryption.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-custom-job.html

### BR-18: Model Evaluation Implementation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock:ListEvaluationJobs`
- **Evaluate:** `Failed` when Bedrock is in use but `ListEvaluationJobs` returns no `Completed` jobs at all; `Passed` when at least one completed evaluation job exists (cite job ARN + completion time). `N/A` when Bedrock is not in use or the list is denied. Report the recency window used in `Finding_Details`; do not silently apply a hidden date filter.
- **Resolution:** Run Bedrock model evaluation jobs measuring toxicity, accuracy, and robustness before production use.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html

### BR-19: Prompt Flow Validation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agent:ListFlows`, `bedrock-agent:GetFlow`
- **Evaluate:** `Failed` when a flow's `status` is not a validated/prepared state (e.g. stuck in `Failed`/`NotPrepared`); `Passed` when flows report a prepared/valid status (cite flow ID + status). `N/A` when no flows exist.
- **Resolution:** Validate flow definitions (e.g. `ValidateFlowDefinition`) before deploying prompt flows.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_ValidateFlowDefinition.html

### BR-20: Knowledge Base Encryption Enhancement
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agent:ListKnowledgeBases`, `bedrock-agent:GetKnowledgeBase`
- **Evaluate:** `Failed` when a `MANAGED` knowledge base is encrypted with an AWS-owned key; `Passed` when it uses a customer-managed KMS key; `N/A` for custom vector stores or indeterminate encryption blocks requiring manual review.
- **Resolution:** Configure customer-managed AWS KMS keys for managed knowledge base encryption.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-kb.html

### BR-21: Agent Action Group IAM Least Privilege
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agent:ListAgents`, `bedrock-agent:GetAgentActionGroup`, `lambda:GetFunction`, `iam:ListAttachedRolePolicies`, `iam:GetRolePolicy`
- **Evaluate:** `Failed` when an action-group Lambda execution role attaches `AdministratorAccess`/`*FullAccess` or an inline `Resource:"*"` on write actions (cite role + statement). `Passed` when all inspected roles are scoped. `N/A` when no agents/action groups exist or reads are denied.
- **Resolution:** Scope each action group Lambda execution role to the minimal permissions required.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/agents-permissions.html

### BR-22: Model Invocation Throttling Limits
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `servicequotas:GetServiceQuota`, `servicequotas:GetAWSDefaultServiceQuota`
- **Evaluate:** `Failed` (Informational-to-Low) when every Bedrock invocation quota equals its AWS default (no custom limit set); `Passed` when at least one custom limit differs from default (cite quota code + values). `N/A` when Service Quotas data is unavailable. Note: quota/capacity *headroom* analysis is owned by `bedrock-adoption-readiness`; this check only flags the absence of any custom throttling as an abuse-control signal.
- **Resolution:** Configure custom Service Quotas for Bedrock model invocation to control abuse and cost.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html

### BR-23: Guardrail Content Filter Coverage
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- **Evaluate:** `Failed` when a guardrail is missing any of the four content filters (hate, insults, sexual, violence) or lacks configured thresholds; `Passed` when all four are enabled with thresholds; `N/A` when no guardrails exist.
- **Resolution:** Enable all four content filter types with appropriate strength thresholds on each guardrail.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html

### BR-24: Automated Reasoning Policy Implementation
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- **Evaluate:** `Failed` when no guardrail has an Automated Reasoning policy attached; `Passed` when Automated Reasoning policies are configured and enabled; `N/A` when no guardrails exist.
- **Resolution:** Attach and enable an Automated Reasoning policy on guardrails to formally verify model responses.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/deploy-automated-reasoning-policy.html

### BR-25: RAG Evaluation Jobs
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Heuristic
- **Read-only APIs:** `bedrock-agent:ListKnowledgeBases`, `bedrock:ListEvaluationJobs`
- **Evaluate:** `Failed` when knowledge bases exist but no RAG/knowledge-base evaluation job is found; `Passed` when at least one KB evaluation job exists (cite job). `N/A` when no knowledge bases exist or the list is denied.
- **Resolution:** Configure RAG evaluation jobs for each knowledge base to measure relevance and prevent hallucinations.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html

### BR-26: Guardrail Sensitive Information Filter
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- **Evaluate:** `Failed` when a guardrail's `sensitiveInformationPolicy` has no PII entity types (`piiEntities`) or custom regex patterns (`regexes`); `Passed` when sensitive-information protection is configured; `N/A` when no guardrails exist.
- **Resolution:** Add PII entity types and/or custom regex patterns to each guardrail's sensitive information policy.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html

### BR-27: Guardrail Contextual Grounding Check
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- **Evaluate:** `Failed` when a guardrail's `contextualGroundingPolicy.filters` has no enabled grounding or relevance filters; `Passed` when grounding checks are enabled; `N/A` when no guardrails exist.
- **Resolution:** Enable grounding and relevance filters in each guardrail's contextual grounding policy.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html

### BR-28: Agent Guardrail Association
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agent:ListAgents`, `bedrock-agent:GetAgent`
- **Evaluate:** `Failed` when a Bedrock Agent has no `guardrailConfiguration` attached; `Passed` when every agent has an associated guardrail; `N/A` when no agents exist in the region.
- **Resolution:** Associate an approved guardrail with each Bedrock Agent.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use.html

### BR-29: Agent Idle Session TTL
- **Severity:** Low
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock-agent:ListAgents`, `bedrock-agent:GetAgent`
- **Evaluate:** `Failed` when an agent's `idleSessionTTLInSeconds` exceeds 3600; `Passed` when the TTL is within the ceiling; `N/A` when no agents exist in the region.
- **Resolution:** Lower each agent's idle session TTL to at most 3600 seconds to limit session-context reuse.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/agents-create.html

### BR-30: Imported Model Customer-Managed KMS Encryption
- **Severity:** High
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListImportedModels`, `bedrock:GetImportedModel`
- **Evaluate:** `Failed` when an imported model's `modelKmsKeyArn` is an AWS-owned key rather than a customer-managed key; `Passed` when a customer-managed key is used; `N/A` when no imported models exist in the region.
- **Resolution:** Re-import models using a customer-managed AWS KMS key for encryption.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-import-model.html

### BR-31: Batch Inference Output Encryption
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `bedrock:ListModelInvocationJobs`
- **Evaluate:** `Failed` when a model invocation (batch inference) job has no `outputDataConfig.s3OutputDataConfig.s3EncryptionKeyId`; `Passed` when S3 output uses a customer-managed KMS key; `N/A` when no batch inference jobs exist in the region.
- **Resolution:** Specify a customer-managed KMS key for the S3 output of each batch inference job.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference.html

### BR-32: CloudWatch Alarms on Bedrock Metrics
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `cloudwatch:DescribeAlarms`
- **Evaluate:** `Failed` when no CloudWatch alarms target the `AWS/Bedrock` namespace (directly or via metric math); `Passed` when Bedrock-metric alarms exist; `N/A` when the region has no Bedrock resources. (Security/abuse alarm *presence*; observability maturity is `bedrock-adoption-readiness`.)
- **Resolution:** Create CloudWatch alarms on `AWS/Bedrock` runtime metrics to detect abuse, throttling, and content-filter spikes.
- **Reference:** https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

### BR-33: Amazon Inspector Lambda Code Scanning
- **Severity:** Medium
- **Scope:** Regional
- **Verifiability:** Verifiable
- **Read-only APIs:** `lambda:ListFunctions`, `inspector2:BatchGetAccountStatus`
- **Evaluate:** `Failed` when in-scope Bedrock-related Lambda functions exist but `resourceState.lambda.status` or `resourceState.lambdaCode.status` is not `ENABLED`; `Passed` when both Inspector Lambda scanning modes are enabled; `N/A` when no in-scope functions exist, access is denied, or the region is unavailable.
- **Resolution:** Enable Amazon Inspector Lambda standard scanning and Lambda code scanning to cover in-scope functions.
- **Reference:** https://docs.aws.amazon.com/inspector/latest/user/scanning-lambda.html
