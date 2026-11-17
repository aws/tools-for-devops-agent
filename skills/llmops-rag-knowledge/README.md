# llmops-rag-knowledge

> **Non-production disclaimer.** This skill is an operational aid for reviewing the health of Amazon
> Bedrock Knowledge Bases and the RAG retrieval path. It performs **read-only** analysis and renders
> findings; it does not modify any resource and never starts an ingestion job. Findings and
> remediations are guidance, not guarantees — confirm against the AWS console and documentation before
> acting. Not an AWS-published commitment. Validate in a non-production context before relying on it
> operationally.

## What It Does

`llmops-rag-knowledge` reviews the health of Amazon Bedrock Knowledge Bases and the retrieval-augmented
generation (RAG) path for the `llmops-agent` custom agent. It answers the question operators ask —
**"why is my knowledge base returning nothing / stale / wrong answers?"** — with evidence, and it
distinguishes a Knowledge Base that merely *exists* from one that is actually *populated and serving
fresh content*.

It provides:

- **The RAG health review.** A ten-step read-only procedure: enumerate KBs → data sources → **ingestion
  job history** (the decisive signal) → ingestion statistics → confirm the KB is populated → chunking →
  embedding currency → encryption → hybrid vs semantic retrieval → attachment → sync automation.
- **The LLM-KB check family (001–012).** Stale data, failed or never-run ingestion, chunking strategy,
  embedding-model currency, data source and vector store encryption, hybrid search, unattached knowledge
  bases, retrieval-quality measurement, data-source access & authorization, and embedding/retrieval
  quota & throttling — each with a severity and an AWS-doc citation.
- **The highest-value trap, called out explicitly.** A KB that is `ACTIVE` with **no completed
  ingestion job is EMPTY** and silently returns nothing; an empty `ListIngestionJobs` means **never
  synced** (LLM-KB-001, HIGH), not healthy.

Every finding carries an `LLM-KB` check-id, a severity, and a citation. The skill never invents a
threshold, never mutates a resource, and **never reproduces the content of retrieved document chunks**
(counts, sources, and scores only — KB content is frequently sensitive customer data).

It is **fully self-contained** with **no external skill dependencies**.

### When NOT to use it

- Bedrock model config / invocation logging → **llmops-bedrock-configuration**.
- Guardrails incl. contextual grounding config → **llmops-guardrails**.
- Quota and cost → **llmops-capacity-cost**.
- Bedrock Agents / AgentCore runtime → **llmops-agent-runtime**.
- SageMaker for LLMs → the **llmops-sagemaker-\*** skills: **llmops-sagemaker-inference-endpoints** (real-time endpoints), **llmops-sagemaker-training**, **llmops-sagemaker-serverless-async**, **llmops-sagemaker-batch**, **llmops-sagemaker-evaluation**, **llmops-sagemaker-model-registry**.
- A live incident ("is this AWS or mine right now?") → **llmops-incident-triage**.
- Model-output quality and RAG **evaluation jobs** → **llmops-quality-evaluation**.

## Prerequisites

Read-only IAM permissions in the account/region under review. Bedrock Agents APIs authorize under
the `bedrock:` IAM prefix (there is no `bedrock-agent:` IAM prefix):

- **Bedrock (read):** `bedrock:ListKnowledgeBases`, `bedrock:GetKnowledgeBase`,
  `bedrock:ListDataSources`, `bedrock:GetDataSource`, `bedrock:ListIngestionJobs`,
  `bedrock:GetIngestionJob`, `bedrock:ListAgents`, `bedrock:ListAgentVersions`,
  `bedrock:ListAgentKnowledgeBases`, `bedrock:GetFoundationModel`, `bedrock:ListEvaluationJobs`.
- **Bedrock (optional, billed):** `bedrock:Retrieve` for the bounded retrieval probe (counts, URIs and
  scores only).
- **S3 (read):** `s3:ListBucket` (object `LastModified` and sizes under the inclusion prefix) and
  `s3:GetEncryptionConfiguration` (bucket default encryption).
- **OpenSearch Serverless (read, AOSS stores):** `aoss:BatchGetCollection`,
  `aoss:ListSecurityPolicies`, `aoss:GetSecurityPolicy`.
- **Sync automation and callers (read, optional):** `cloudtrail:LookupEvents`,
  `cloudtrail:GetEventSelectors`, `scheduler:ListSchedules`, `events:ListRules`,
  `events:ListTargetsByRule`, `logs:DescribeDeliverySources`.
- **CloudWatch (read, optional):** `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData` for `AWS/AOSS`
  vector-store signals and embedding/retrieval throttle/usage signals (`InvocationThrottles`,
  `EstimatedTPMQuotaUsage`).
- **Access & authorization (read):** `iam:SimulatePrincipalPolicy`, `iam:GetRole`,
  `s3:GetBucketPolicy`, `organizations:ListPoliciesForTarget`, `organizations:DescribePolicy`
  (data-source access & authorization check).
- **Service Quotas (read):** `servicequotas:GetServiceQuota` (embedding/retrieval quota & throttling
  check).

The DevOps Agent's standard `AIDevOpsAgentAccessPolicy` does not list `bedrock:GetIngestionJob` or
`bedrock:Retrieve`; the skill falls back to job-summary statistics and skips the probe.

No write, modify, or delete permissions are needed or used. `StartIngestionJob` is **recommended, never
called**.

## Uploading to AWS DevOps Agent

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip
from **inside** the skill directory:

```bash
cd skills/llmops-rag-knowledge && zip -r ../llmops-rag-knowledge.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/llmops-rag-knowledge.zip` containing `SKILL.md`, `references/`, and `assets/` at
the top level, with the repo-management files excluded.

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `llmops-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

## Usage Examples

- "Our knowledge base is returning nothing even though it shows ACTIVE." → checks ingestion-job
  history, finds an empty `ListIngestionJobs` → LLM-KB-001, never synced / EMPTY, recommends
  `StartIngestionJob`.
- "RAG answers are out of date." → reads latest `GetIngestionJob` status + statistics; a `FAILED` job
  or `numberOfDocumentsFailed` > 0 → LLM-KB-002.
- "Retrieval quality is poor on part numbers and SKUs." → semantic-only retrieval where exact-match
  terms matter → LLM-KB-007 (consider `HYBRID`).
- "Is our embedding model current?" → `GetKnowledgeBase` `embeddingModelArn` vs current models →
  LLM-KB-004, with the re-embed/re-eval caveat.
- "We have a knowledge base nobody seems to use." → `ListAgents` → `ListAgentVersions` →
  `ListAgentKnowledgeBases` finds no attachment → LLM-KB-008 (LOW), with application use reported as
  unverified unless CloudTrail data events for the KB are recorded.
- "Ingestion fails with access denied but the data is fine." → simulates the KB role, checks
  trust/bucket/SCP → LLM-KB-011, returns the exact missing statement.
- "Retrieve is getting throttled under load." → reads Bedrock quotas + CloudWatch throttles →
  LLM-KB-012, recommends the specific quota increase.

## Author

Ankur Sinha

## Version History

See the `CHANGELOG.md` file in this directory.
