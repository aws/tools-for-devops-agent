# opsai-bedrock-review

> **Non-production.** This skill performs a **read-only** review of Amazon Bedrock configuration,
> model access and Knowledge Bases, and produces derived operational guidance. It is not an AWS
> service, carries no SLA, and its severity windows are operational guidance, not AWS-published
> commitments. Validate every remediation against current AWS documentation before acting in a
> production account.

## Purpose

`opsai-bedrock-review` answers two questions operators ask about Amazon Bedrock, with evidence:

- **Is Bedrock set up correctly, and can I invoke the models I need?** It reviews invocation logging,
  model access and lifecycle, inference profiles, IAM scope, and why a call is denied.
- **Why is my knowledge base returning nothing, stale or wrong answers?** It reviews ingestion and sync,
  chunking, embedding models, vector store encryption and exposure, search type, access and quotas on
  the retrieval path.

It merges the earlier Bedrock configuration and RAG knowledge base skills into one
install.

## Key Capabilities

- Runs the **LLM-INV** check family (LLM-INV-001 to 015) for model access and configuration, and the
  **LLM-KB** family (LLM-KB-001 to 012) for knowledge bases. Each finding carries a check-id, a
  severity and an AWS-doc citation.
- Reads an empty `GetModelInvocationLoggingConfiguration` as logging **disabled**, and checks log
  delivery and encryption.
- Tells an IAM implicit deny from an SCP explicit deny, model access not granted, a marketplace
  subscription never accepted and an end-of-life model, before prescribing any fix.
- Treats an `ACTIVE` knowledge base with no ingestion history as **never synced**, and reads the latest
  ingestion job's statistics and `failureReasons`.
- Diagnoses access denied on ingestion or `Retrieve` (KB role, trust policy, bucket policy, SCP) and
  throttling on embedding or `Retrieve` against the Bedrock quotas.
- Never reproduces retrieved chunk text and never writes a raw account ID.
- Works on its own. When a question reaches into guardrails, cost, agents, SageMaker, live incidents
  or output quality, it uses the matching OpsAI skill if installed, or runs a fallback check and
  recommends that skill.

## Prerequisites

Read-only IAM permissions in the account and Region under review. Bedrock Agents and Knowledge Bases
APIs authorize under the `bedrock:` IAM prefix (there is no `bedrock-agent:` IAM prefix).

**Model access and configuration:**

- `bedrock:GetModelInvocationLoggingConfiguration`
- `bedrock:ListFoundationModels`, `bedrock:GetFoundationModel`
- `bedrock:ListInferenceProfiles`, `bedrock:GetInferenceProfile`
- `bedrock:GetFoundationModelAvailability` (AWS CLI 2.27.42 or later)
- `bedrock:ListModelInvocationJobs`, `bedrock:ListPrompts`
- `iam:ListRoles`, `iam:GetRole`, `iam:ListAttachedRolePolicies`, `iam:ListRolePolicies`,
  `iam:GetRolePolicy`, `iam:GetPolicy`, `iam:GetPolicyVersion`
- `organizations:DescribeOrganization`; `organizations:ListPoliciesForTarget` and
  `organizations:DescribePolicy` work only from the management account or a delegated administrator
- `cloudtrail:LookupEvents` (InvokeModel and Converse are management events)
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData` (`AWS/Bedrock` invocation and log-delivery
  metrics)
- `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:DescribeMetricFilters`,
  `logs:StartQuery`, `logs:GetQueryResults`
- For an S3 logging destination: `s3:GetEncryptionConfiguration`, `s3:GetBucketPolicyStatus`,
  `s3:GetBucketPublicAccessBlock`, `s3:ListBucket`

**Knowledge bases and RAG:**

- **Bedrock (read):** `bedrock:ListKnowledgeBases`, `bedrock:GetKnowledgeBase`,
  `bedrock:ListDataSources`, `bedrock:GetDataSource`, `bedrock:ListIngestionJobs`,
  `bedrock:GetIngestionJob`, `bedrock:ListAgents`, `bedrock:ListAgentVersions`,
  `bedrock:ListAgentKnowledgeBases`, `bedrock:ListEvaluationJobs`.
- **S3 (read):** `s3:ListBucket`, `s3:GetEncryptionConfiguration`, `s3:GetBucketPolicy`.
- **OpenSearch Serverless (read, AOSS stores):** `aoss:BatchGetCollection`,
  `aoss:ListSecurityPolicies`, `aoss:GetSecurityPolicy`.
- **Sync automation and callers (read, optional):** `cloudtrail:GetEventSelectors`,
  `scheduler:ListSchedules`, `events:ListRules`, `events:ListTargetsByRule`,
  `logs:DescribeDeliverySources`.
- **Service Quotas (read):** `servicequotas:GetServiceQuota`.

The AWS managed policy `AIDevOpsAgentAccessPolicy` grants all of these except `bedrock:GetIngestionJob`,
`bedrock:GetFoundationModelAvailability` and `s3:GetBucketPolicyStatus`. Set the `EnableOpsaiBedrockReview`
parameter of the [skill policies template](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml) to add them, plus the
`bedrock-agentcore` runtime and gateway reads used for the AgentCore hand-off. The skill never calls
`iam:SimulatePrincipalPolicy` (the agent runtime refuses it even when granted; it reads the policy
documents and labels the verdict "evaluated from policy documents, not simulated"), `bedrock:Retrieve`
(returns chunk text; retrieval questions use ingestion-job statistics) or `s3:GetObject` (returns
customer data). The skill records each denied call, uses the documented fallback (job-summary
statistics, error text and CloudTrail for model access, bucket policy and Block Public Access for
exposure), and discloses what stays unconfirmed. No write, modify or delete permission is needed or used:
`StartIngestionJob` is **recommended, never called**.

## Limitations

- Read-only: it recommends fixes and gives the exact command, and never applies them.
- SCP contents are readable only from the management account or a delegated administrator.
  Elsewhere an SCP deny is reported from the error message, not the policy text.
- Whether an application (rather than an agent) uses a knowledge base is unverified unless CloudTrail
  records KB data events.
- Bedrock evaluation is not available in every Region, so LLM-KB-009 can be not-applicable.
- It does not review guardrail strength, spend, agents, SageMaker or output quality (see *Related
  skills* below).

## Agent Types

Installed as **GENERIC** (all agents), so it loads for chat and for incident investigations.

## Uploading to AWS DevOps Agent

```bash
cd skills/opsai-bedrock-review && zip -r ../opsai-bedrock-review.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/opsai-bedrock-review.zip` with `SKILL.md`, `references/` and `assets/` at the top
level. In the AWS DevOps Agent console, open your Agent Space, choose **Skills**, upload the zip, and
make it available to **All agents**.

## How to Use This Skill

Model access and configuration:

- "Is my Bedrock set up correctly? Check my configuration."
- "`InvokeModel` is returning `AccessDeniedException`. Is it IAM, an SCP, or model access?"
- "Is model invocation logging enabled, and is it encrypted?"
- "Are we calling a bare model ID instead of a cross-region inference profile?"
- "Is the model we use deprecated or end-of-life?"
- "Is `bedrock:InvokeModel` scoped to specific model ARNs or wildcarded?"

Knowledge bases and RAG:

- "Our knowledge base is returning nothing even though it shows ACTIVE."
- "RAG answers are out of date." / "The last sync may have failed."
- "Retrieval quality is poor on part numbers and SKUs."
- "Is our embedding model current?"
- "We have a knowledge base nobody seems to use."
- "Ingestion fails with access denied but the data is fine."
- "`Retrieve` is getting throttled under load."

## Related skills

All optional. This skill uses them when they are installed:
[`opsai-bedrock-security`](../../skills/opsai-bedrock-security/) (who can call Bedrock, guardrails),
the OpsAI skill for Bedrock spend and quotas,
[`opsai-bedrock-agentcore`](../../skills/opsai-bedrock-agentcore/) (agents),
the OpsAI skill for live-failure triage, and the `opsai-ml-eval-check`,
`opsai-sagemaker-inference` and `opsai-sagemaker-training` skills.

## Author

Ankur Sinha

## Version History

See the `CHANGELOG.md` file in this directory.
