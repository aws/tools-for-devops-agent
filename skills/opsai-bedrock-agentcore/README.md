# opsai-bedrock-agentcore

> **Non-production disclaimer.** This skill is an operational aid for reviewing the health of Amazon
> Bedrock Agents and Bedrock AgentCore runtimes. It performs **read-only** analysis and reports
> findings; it does not modify any resource. Findings and remediations are guidance, not guarantees —
> confirm against AWS documentation and your own change process before acting. Not an AWS-published
> commitment. Validate in a non-production context before relying on it operationally.

## What It Does

`opsai-bedrock-agentcore` reviews the **agent layer** on AWS across two services operators frequently
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

This skill works on its own: it depends on no other skill.

### When NOT to use it

Related skills are optional: when one is installed this skill uses it for that part, otherwise it runs a short fallback check and recommends installing it.

- Bedrock model configuration, invocation logging and knowledge bases → `opsai-bedrock-review`
- Guardrail policy content → `opsai-bedrock-security`
- Quota & cost → `opsai-capacity-cost`
- SageMaker → `opsai-sagemaker-inference`, `opsai-sagemaker-training`
- Is-this-AWS-or-mine incident triage → `opsai-incident-triage`
- Model-output quality / evaluation → `opsai-ml-eval-check`

## Prerequisites

Read-only IAM permissions in the account and Region under review. The AWS managed policy
`AIDevOpsAgentAccessPolicy` already grants the Bedrock Agents Classic reads (`bedrock:GetAgent`, `bedrock:GetAgentAlias`,
`bedrock:GetAgentActionGroup` and `bedrock:List*` for agents, aliases and action groups; `bedrock-agent` is only the CLI client name, not an IAM prefix), the
IAM policy reads, `organizations:ListPoliciesForTarget` / `DescribePolicy`, `ec2:DescribeVpcEndpoints`,
`lambda:GetPolicy`, `cloudtrail:LookupEvents` and the CloudWatch and Logs reads.

> **AgentCore reads are NOT in `AIDevOpsAgentAccessPolicy`.** It has no `bedrock-agentcore` action and not
> `bedrock:GetPrompt`. Set the `EnableOpsaiBedrockAgentCore` parameter of the [skill policies template](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)
> (default `true`) to add them. Without it the skill reports each denied AgentCore read as a disclosed
> permission gap, not as an absent runtime.

The skill does not use `iam:SimulatePrincipalPolicy`, which the agent runtime refuses even when granted: it
reads the runtime role's policies and the SCPs and labels the verdict "evaluated from policy documents, not
simulated". It does not use `s3:GetObject` (returns customer data). No write, modify, or delete permissions are needed or used.

## Uploading to AWS DevOps Agent

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip from
**inside** the skill directory:

```bash
cd skills/opsai-bedrock-agentcore && zip -r ../opsai-bedrock-agentcore.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/opsai-bedrock-agentcore.zip` containing `SKILL.md`, `references/`, and `assets/` at the
top level, with the repo-management files excluded.

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `opsai-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

## Usage Examples

- "Our Bedrock agent is returning empty responses." → resolves alias→version first (not the DRAFT),
  then checks guardrail attachment and tracing (LLM-AGT-001, LLM-AGT-005, LLM-AGT-007).
- "The action group keeps failing." → inspects the executor Lambda's role scope (LLM-AGT-002) and the
  action-group / Code Interpreter config (LLM-AGT-006).
- "My AgentCore runtime can't invoke the model." → evaluates the runtime role's policies for `bedrock:InvokeModel*`
  (LLM-AC-001) and, if denied, correlates against SCPs (LLM-AC-002).
- "We're getting gateway errors / a VPC endpoint seems missing." → checks required VPC endpoints
  (LLM-AC-003) and gateway target config (LLM-AC-004).
- "No traces are coming from my agent." → checks stage-level OTLP telemetry and trace propagation
  (LLM-AC-005, LLM-AC-006) and structured logs (LLM-AC-007).
- "Does my agent even have a guardrail attached?" → LLM-AGT-001 (attachment only; policy content is
  `opsai-bedrock-security`).

## Author

Wael Dimassi

## Version History

See the `CHANGELOG.md` file in this directory.
