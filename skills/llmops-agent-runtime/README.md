# llmops-agent-runtime

> **Non-production disclaimer.** This skill is an operational aid for reviewing the health of Amazon
> Bedrock Agents and Bedrock AgentCore runtimes. It performs **read-only** analysis and reports
> findings; it does not modify any resource. Findings and remediations are guidance, not guarantees —
> confirm against AWS documentation and your own change process before acting. Not an AWS-published
> commitment. Validate in a non-production context before relying on it operationally.

## What It Does

`llmops-agent-runtime` reviews the **agent layer** on AWS across two services operators frequently
conflate:

- **Amazon Bedrock Agents** (family **LLM-AGT**) — managed agents with action groups and aliases. Checks
  cover a missing guardrail attachment (CRITICAL), over-broad action-group Lambda permissions, prompt
  management and versioning, test-alias use in production, tracing, Code Interpreter controls, model
  resilience via inference profile, idle/abandoned agents, and memory/session TTL.
- **Amazon Bedrock AgentCore** (family **LLM-AC**) — runtimes, gateways, memories, and workload
  identities. Checks cover a runtime execution role missing required permissions (CRITICAL), an
  explicit SCP deny, absent VPC endpoints, misconfigured gateway targets, stage-level OTLP telemetry,
  trace-context propagation, structured logs, credential rotation, runtime version currency, and
  session recording.

It resolves which service is actually in play first (the diagnosis diverges), then runs the matching
ordered procedure. Every finding carries an AWS-documented `check-id` (LLM-AGT-### / LLM-AC-###), a
severity, and a citation. The skill never invents a threshold and never mutates a resource.

This is a skill for the `llmops-agent` custom agent and is fully self-contained — it depends on no other
skill.

### When NOT to use it

- Bedrock model configuration & invocation logging → `llmops-bedrock-configuration`
- Guardrail policy content → `llmops-guardrails`
- Quota & cost → `llmops-capacity-cost`
- Knowledge bases / RAG → `llmops-rag-knowledge`
- SageMaker for LLMs → the `llmops-sagemaker-*` skills: `llmops-sagemaker-inference-endpoints` (real-time endpoints), `llmops-sagemaker-training`, `llmops-sagemaker-serverless-async`, `llmops-sagemaker-batch`, `llmops-sagemaker-evaluation`, `llmops-sagemaker-model-registry`.
- Is-this-AWS-or-mine incident triage → `llmops-incident-triage`
- Model-output quality / evaluation → `llmops-quality-evaluation`

## Prerequisites

Read-only IAM permissions in the account/region under review:

- **Bedrock Agents (read):** `bedrock-agent:Get*`, `bedrock-agent:List*` (agents, aliases, action
  groups, prompts, memory config), and `bedrock:Get*` / `bedrock:List*` for model/inference-profile
  context.
- **Action-group Lambda scope:** `lambda:GetPolicy`, `iam:GetRole`, `iam:GetRolePolicy`,
  `iam:ListAttachedRolePolicies`.
- **IAM / Organizations (for AgentCore permission checks):** `iam:SimulatePrincipalPolicy`,
  `organizations:ListPoliciesForTarget`, `organizations:DescribePolicy`.
- **Networking:** `ec2:DescribeVpcEndpoints` (VPC-deployed runtimes).
- **AgentCore (read, for LLM-AC-004 and LLM-AC-011..014):** `bedrock-agentcore:Get*` / `List*` for
  runtimes, endpoints, gateways and targets, memories and browser/code-interpreter sessions, and
  `bedrock-agentcore:GetResourcePolicy` (cross-account checks). `iam:GetRole` (permissions boundary)
  and `cloudtrail:LookupEvents` (`AssumeRole` session policy) for the denied-caller checks. Without them
  the skill reports the denial as a disclosed permission gap.
- **CloudWatch / Logs:** `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`,
  `logs:DescribeLogGroups`, `logs:DescribeMetricFilters` (activity, tracing, structured-log checks).

> **CRITICAL — AgentCore reads are NOT in `AIDevOpsAgentAccessPolicy`.** The standard
> `AIDevOpsAgentAccessPolicy` attached to the default Agent Space role does **not** include the
> `bedrock-agentcore` namespace. AgentCore read actions (runtime, gateway, observability config) must be
> granted **separately**. If they are not, the skill reports the denial as a disclosed permission gap —
> not as an absent runtime.

No write, modify, or delete permissions are needed or used.

## Uploading to AWS DevOps Agent

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip from
**inside** the skill directory:

```bash
cd skills/llmops-agent-runtime && zip -r ../llmops-agent-runtime.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/llmops-agent-runtime.zip` containing `SKILL.md`, `references/`, and `assets/` at the
top level, with the repo-management files excluded.

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `llmops-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

## Usage Examples

- "Our Bedrock agent is returning empty responses." → resolves alias→version first (not the DRAFT),
  then checks guardrail attachment and tracing (LLM-AGT-001, LLM-AGT-005, LLM-AGT-007).
- "The action group keeps failing." → inspects the executor Lambda's role scope (LLM-AGT-002) and the
  action-group / Code Interpreter config (LLM-AGT-006).
- "My AgentCore runtime can't invoke the model." → simulates the runtime role for `bedrock:InvokeModel*`
  (LLM-AC-001) and, if denied, correlates against SCPs (LLM-AC-002).
- "We're getting gateway errors / a VPC endpoint seems missing." → checks required VPC endpoints
  (LLM-AC-003) and gateway target config (LLM-AC-004).
- "No traces are coming from my agent." → checks stage-level OTLP telemetry and trace propagation
  (LLM-AC-005, LLM-AC-006) and structured logs (LLM-AC-007).
- "Does my agent even have a guardrail attached?" → LLM-AGT-001 (attachment only; policy content routes
  to `llmops-guardrails`).

## Author

Wael Dimassi

## Version History

See the `CHANGELOG.md` file in this directory.
