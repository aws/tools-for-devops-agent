# Out-of-Scope Routing

What this skill does not cover, and the `llmops-agent` skill that does. `SKILL.md`, When NOT to Use,
lists the same cases in short, and holds the rule for a request that mixes them with an audit of
long-lived credentials.

## 1. Owned by another llmops-agent skill

- **Throttling, quotas, latency or the cost of Amazon Bedrock calls.** This skill reads IAM
  configuration only. Quota, throttling and token spend → `llmops-capacity-cost`; a live failure or
  slowdown, and whether it is an AWS problem or the customer's → `llmops-incident-triage`.
- **Amazon Bedrock Guardrails** (content filters, sensitive information, denied topics). Not this
  skill → `llmops-guardrails`.
- **A failing Amazon Bedrock call** from an application, a role, an IAM user or an API key
  (`AccessDeniedException` on `InvokeModel`, or an authentication error). This skill does not
  diagnose why a call fails; it audits who can call with long-lived IAM user credentials.
  `llmops-bedrock-configuration` checks the caller's permissions itself, so this skill adds nothing
  to that diagnosis. Why `InvokeModel` returns `AccessDeniedException`, model access, invocation
  logging and inference profiles → `llmops-bedrock-configuration`.
- **IAM roles, federated users and IAM Identity Center users.** They have no long-lived keys and are
  out of scope. Whether an IAM role's `bedrock:InvokeModel*` grants are least privilege (federated
  and IAM Identity Center users act through roles) → `llmops-bedrock-configuration`.
- **Knowledge bases and RAG** (ingestion, retrieval, vector store) → `llmops-rag-knowledge`.
- **Amazon Bedrock Agents and Amazon Bedrock AgentCore** (action groups, aliases, runtimes,
  gateways) → `llmops-agent-runtime`.
- **Model output quality and evaluation** (answers got worse, evaluation jobs) →
  `llmops-quality-evaluation`.
- **Amazon SageMaker for LLMs** → the `llmops-sagemaker-*` skills: `llmops-sagemaker-inference-endpoints` (real-time endpoints), `llmops-sagemaker-training`, `llmops-sagemaker-serverless-async`, `llmops-sagemaker-batch`, `llmops-sagemaker-evaluation`, `llmops-sagemaker-model-registry`.

## 2. Covered by no skill

- **Which model a key invoked, and when.** That is usage history: AWS CloudTrail and GuardDuty AI
  Protection, not configuration.
- **An organization-wide audit, or accounts not connected to this Agent Space.** This skill audits
  only the accounts connected to this Agent Space (`SKILL.md`, Scope, under The Review Procedure).
- **Applying a fix.** Deleting keys, attaching policies and creating SCPs are the customer's actions.
