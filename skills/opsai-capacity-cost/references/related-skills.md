# Related skills

Areas `opsai-capacity-cost` does not cover, the skill that does, and what to do when that skill isn't installed.
Every skill here is optional. Follow the three steps in `SKILL.md` under *Related skills (optional)*.

| Area | Skill | Fallback when it isn't installed |
|---|---|---|
| A live failure right now: model calls erroring, throttled (429), timing out or slow; "is it AWS or us" | `opsai-incident-triage` | Read the error and throttle metrics for the incident window (`AWS/Bedrock` `InvocationClientErrors`, `InvocationServerErrors`, `InvocationThrottles`, or the endpoint's `Invocation5XXErrors`) and AWS Health events for the service and Region where the account's support plan allows `health:DescribeEvents`. Say whether the evidence points at the provider or the account; don't rule on the root cause. |
| Bedrock model access and denied calls, invocation logging, model lifecycle, inference profiles; Knowledge Bases and RAG retrieval | `opsai-bedrock-review` | Read `bedrock:GetModelInvocationLoggingConfiguration`, the model's lifecycle status from `bedrock:GetFoundationModel`, or `bedrock:GetKnowledgeBase` with its latest ingestion job (`bedrock:ListIngestionJobs`), and report what you observed. |
| Who can call Bedrock (IAM users, long-lived access keys, Bedrock API keys); Bedrock Guardrails coverage and strength | `opsai-bedrock-security` | Read `bedrock:GetGuardrail` for the guardrail version in use and list which policy types it configures. For callers, list IAM users that hold access keys (`iam:ListUsers`, `iam:ListAccessKeys`) without ruling on what their policies allow. |
| Bedrock AgentCore runtimes and gateways; Bedrock Agents (action groups, aliases, which version is live) | `opsai-bedrock-agentcore` | Read the runtime or agent status (`bedrock-agentcore:GetAgentRuntime`, or `bedrock:GetAgent` and `bedrock:GetAgentAlias`) and report it. An AccessDenied on `bedrock-agentcore` is a permission gap, not proof that no runtime exists. |
| Output quality and regressions, evaluation jobs (Bedrock or SageMaker), truncated answers and finish reasons | `opsai-ml-eval-check` | If invocation logs exist, report the share of responses that stopped on `max_tokens` (Converse `stopReason`). Otherwise say output quality is not measured. |
| SageMaker real-time, serverless and async endpoints; batch transform; SageMaker endpoint cost | `opsai-sagemaker-inference` | Read `sagemaker:DescribeEndpoint` (status, `FailureReason`) or `sagemaker:DescribeTransformJob` and report it. |
| SageMaker training and fine-tuning jobs; Model Registry | `opsai-sagemaker-training` | Read `sagemaker:DescribeTrainingJob` (status, `FailureReason`) or the model package's approval status (`sagemaker:DescribeModelPackage`) and report it. |
