# Related skills

Areas `opsai-incident-triage` does not cover, the skill that does, and what to do when that skill isn't installed.
Every skill here is optional. Follow the three steps in `SKILL.md` under *Related skills (optional)*.

| Area | Skill | Fallback when it isn't installed |
|---|---|---|
| Bedrock model access and denied calls, invocation logging, model lifecycle, inference profiles; Knowledge Bases and RAG retrieval | `opsai-bedrock-review` | Read `bedrock:GetModelInvocationLoggingConfiguration`, the model's lifecycle status from `bedrock:GetFoundationModel`, or `bedrock:GetKnowledgeBase` with its latest ingestion job (`bedrock:ListIngestionJobs`), and report what you observed. |
| Who can call Bedrock (IAM users, long-lived access keys, Bedrock API keys); Bedrock Guardrails coverage and strength | `opsai-bedrock-security` | Read `bedrock:GetGuardrail` for the guardrail version in use and list which policy types it configures. For callers, list the IAM users (`iam:ListUsers`) without ruling on what their policies allow, and say access keys were not checked (`iam:ListAccessKeys` is not called here: it is not in `AIDevOpsAgentAccessPolicy`). |
| Bedrock spend, pricing tiers, quotas and headroom, Provisioned Throughput | `opsai-capacity-cost` | Read the one quota that binds with `servicequotas:GetServiceQuota` (service code `bedrock`) if you know its code, or ask the user for it; never page the full `ListServiceQuotas` list. Match the quota to how the caller invokes: latency-optimized (`performanceConfig.latency = optimized`) and each cross-region profile have their own per-minute quota. Read `AWS/Bedrock` `InvocationThrottles` and `Invocations` for both the base model ID and its latency-optimized series. Give no cost figure you did not retrieve. |
| Bedrock AgentCore runtimes and gateways; Bedrock Agents (action groups, aliases, which version is live) | `opsai-bedrock-agentcore` | Read the runtime or agent status (`bedrock-agentcore:GetAgentRuntime`, or `bedrock:GetAgent` and `bedrock:GetAgentAlias`) and report it. The `bedrock-agentcore` reads need the `EnableOpsaiIncidentTriage` template parameter; an AccessDenied on `bedrock-agentcore` is a permission gap, not proof that no runtime exists. |
| Output quality and regressions, evaluation jobs (Bedrock, including RAG evaluation jobs, or SageMaker), truncated answers and finish reasons | `opsai-ml-eval-check` | If invocation logs exist, report the share of responses that stopped on `max_tokens` (Converse `stopReason`). Otherwise say output quality is not measured. |
| SageMaker real-time, serverless and async endpoints; batch transform; SageMaker endpoint cost | `opsai-sagemaker-inference` | Read `sagemaker:DescribeEndpoint` (status, `FailureReason`) or `sagemaker:DescribeTransformJob` and report it. |
| SageMaker training and fine-tuning jobs, including GPU time wasted by a run; Model Registry | `opsai-sagemaker-training` | Read `sagemaker:DescribeTrainingJob` (status, `FailureReason`) or the model package's approval status (`sagemaker:DescribeModelPackage`) and report it. |

## Remediation owner tracks

The `Remediation owner` cell in a triage report names one of these tracks. Recommend the skill once, at the end of the report, when it isn't installed.

| Track | Owns | Skill |
|---|---|---|
| `bedrock-configuration` | access, entitlement, model lifecycle, wrong model ID, inference profiles | `opsai-bedrock-review` |
| `retrieval` | knowledge base ingestion and retrieval | `opsai-bedrock-review` |
| `caller-identities` | which IAM users and long-lived keys may call the model | `opsai-bedrock-security` |
| `guardrails` | guardrail filter and policy behaviour | `opsai-bedrock-security` |
| `capacity-and-quota` | quota posture, Provisioned Throughput, spend | `opsai-capacity-cost` |
| `agent-runtime` | AgentCore or Bedrock Agents runtime, gateways, aliases | `opsai-bedrock-agentcore` |
| `output-quality` | output quality, truncation, finish reasons, eval gating | `opsai-ml-eval-check` |
| `sagemaker-serving` | SageMaker endpoint sizing, scaling and serving | `opsai-sagemaker-inference` |
| `caller` | the caller's own request shape | none, the fix is in the caller's code |
| `host-investigation` | compute, networking or a non-LLM component, including a self-hosted model's instances and containers | none, investigate with general tools |
