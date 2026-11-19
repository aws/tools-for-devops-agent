# Related skills

Areas `opsai-bedrock-security` does not cover, the skill that does, and what to do when that skill isn't installed.
Every skill here is optional. Follow the three steps in `SKILL.md` under *Related skills (optional)*.

| Area | Skill | Fallback when it isn't installed |
|---|---|---|
| A live failure right now: model calls erroring, throttled (429), timing out or slow; "is it AWS or us" | `opsai-incident-triage` | Read the error and throttle metrics for the incident window (`AWS/Bedrock` `InvocationClientErrors`, `InvocationServerErrors`, `InvocationThrottles`, or the endpoint's `Invocation5XXErrors`) and AWS Health events for the service and Region where the account's support plan allows `health:DescribeEvents`. Say whether the evidence points at the provider or the account; don't rule on the root cause. |
| Bedrock model access and denied calls, invocation logging, model lifecycle, inference profiles; Knowledge Bases and RAG retrieval | `opsai-bedrock-review` | Read `bedrock:GetModelInvocationLoggingConfiguration`, the model's lifecycle status from `bedrock:GetFoundationModel`, or `bedrock:GetKnowledgeBase` with its latest ingestion job (`bedrock:ListIngestionJobs`), and report what you observed. |
| Bedrock spend, pricing tiers, quotas and headroom, Provisioned Throughput | `opsai-capacity-cost` | Read the relevant quota (`servicequotas:ListServiceQuotas`, service code `bedrock`) and `AWS/Bedrock` `InvocationThrottles` for the model. Give no cost figure you did not retrieve. |
| Bedrock AgentCore runtimes and gateways; Bedrock Agents (action groups, aliases, which version is live) | `opsai-bedrock-agentcore` | Read the runtime or agent status (`bedrock-agentcore:GetAgentRuntime`, or `bedrock:GetAgent` and `bedrock:GetAgentAlias`) and report it. An AccessDenied on `bedrock-agentcore` is a permission gap, not proof that no runtime exists. |
| Output quality and regressions, evaluation jobs (Bedrock or SageMaker), truncated answers and finish reasons | `opsai-ml-eval-check` | If invocation logs exist, report the share of responses that stopped on `max_tokens` (Converse `stopReason`). Otherwise say output quality is not measured. |
| SageMaker real-time, serverless and async endpoints; batch transform; SageMaker endpoint cost | `opsai-sagemaker-inference` | Read `sagemaker:DescribeEndpoint` (status, `FailureReason`) or `sagemaker:DescribeTransformJob` and report it. |
| SageMaker training and fine-tuning jobs; Model Registry | `opsai-sagemaker-training` | Read `sagemaker:DescribeTrainingJob` (status, `FailureReason`) or the model package's approval status (`sagemaker:DescribeModelPackage`) and report it. |

## Boundaries to keep

- **Who can call versus why a call fails.** This skill audits which IAM users and long-lived keys can
  invoke Amazon Bedrock. A failing call (`AccessDeniedException` on `InvokeModel`, or an authentication
  error) from an application, a role, an IAM user or an API key belongs to the model access area: that
  review checks the caller's permissions itself, so this audit adds nothing to that diagnosis.
- **IAM roles, federated users and IAM Identity Center users** have no long-lived keys and are out of
  scope. Whether a role's `bedrock:InvokeModel*` grants are least privilege is the model access area.
- **Guardrail limits stay here**: count limits (topics per guardrail), size limits (text-unit input
  size) and rate quotas (`ApplyGuardrail` requests and text units per second), including throttling by a
  guardrail rate quota. Model quotas, token limits and Provisioned Throughput are the capacity area.
- **Cost** of Amazon Bedrock calls, per IAM user or API key included, is the capacity area.

## Covered by no skill

- **Which model a key invoked, and when.** That is usage history: AWS CloudTrail and GuardDuty AI
  Protection, not configuration.
- **An organization-wide audit, or accounts not connected to this Agent Space.** This skill audits
  only the accounts connected to this Agent Space (`credential-audit.md`, Scope, under The Review Procedure).
- **Applying a fix.** Deleting keys, attaching policies and creating SCPs are the customer's actions.
