# llmops-guardrails

> **Non-production disclaimer.** This skill is an operational aid for reviewing the responsible-AI
> posture of Amazon Bedrock Guardrails. It performs **read-only** analysis and produces findings; it
> does not modify any resource. Every API it calls is read-only. Findings and remediations are guidance, not guarantees — not
> an AWS-published commitment. Validate in a non-production context before relying on it operationally.

## What It Does

`llmops-guardrails` reviews whether Amazon Bedrock Guardrails actually protect a production model path:
whether a guardrail exists on a customer-facing path at all (by request, or enforced for the whole
account or organization), whether its content, sensitive-information, denied-topic, word, and
contextual-grounding policies are configured and actually block rather than merely detect, whether the
invocation pins a published version instead of DRAFT, whether the guardrail was ever validated, whether
blocked messaging is customized, and whether it is encrypted with a customer-managed key.

It provides:

- **A 10-step review procedure** (plus an enforcement pre-step, Step 1a) that enumerates guardrails,
  reads account- and organization-level enforcements, resolves which guardrail and version each
  production path references (agent alias version, flow node, request-level `guardrailConfig`, metrics
  and invocation logs), and evaluates the enforced version against the LLM-GRD checks.
- **The LLM-GRD check family** (`references/checks-guardrails.md`, LLM-GRD-001..011 and 021) — each
  check with a detection rule, a remediation, a severity, and an AWS-doc citation.
- **The DRAFT-vs-enforced trap handling.** A strong DRAFT says nothing about a path that pins a numeric
  version; the skill evaluates the version the invocation pins (LLM-GRD-006).
- **Detect-mode handling.** A filter at `HIGH` strength with action `NONE` blocks nothing; the skill
  reports the action, not the strength (LLM-GRD-011).
- **Answers for questions with no account to read** (`references/service-limits.md`,
  `references/documented-behavior.md`): guardrail limits and quotas, what a guardrail evaluates when a
  call uses tools, why a prompt is blocked only sometimes, streaming latency, and how to read a
  contextual grounding score.

Every finding carries an `LLM-GRD-###` check-id, a severity, and a citation. The skill never invents a
threshold, never reproduces blocked content, and never echoes a raw account ID.

This skill belongs to the `llmops-agent` custom agent, which is fully self-contained with no external
skill dependencies.

### When NOT to use it

- Bedrock config and invocation logging → `llmops-bedrock-configuration`.
- Bedrock model quota, model throttling and cost → `llmops-capacity-cost`. Guardrail limits (count, size and rate quotas) stay in this skill.
- Knowledge bases / RAG → `llmops-rag-knowledge`.
- Agents and AgentCore → `llmops-agent-runtime`.
- SageMaker for LLMs → the `llmops-sagemaker-*` skills: `llmops-sagemaker-inference-endpoints` (real-time endpoints), `llmops-sagemaker-training`, `llmops-sagemaker-serverless-async`, `llmops-sagemaker-batch`, `llmops-sagemaker-evaluation`, `llmops-sagemaker-model-registry`.
- Service-vs-config triage of a live failure → `llmops-incident-triage`.
- Model-output quality / evaluation → `llmops-quality-evaluation`.

## Prerequisites

Read-only IAM permissions in the account/region under review. The IAM action prefix for the Agents
for Amazon Bedrock control plane (agents, aliases, flows) is `bedrock:` — the `bedrock-agent` client
name is not an IAM prefix and matches nothing.

**Already in `AIDevOpsAgentAccessPolicy`** (the AWS managed policy on the default Agent Space role):

- **Bedrock (read):** `bedrock:GetGuardrail`; `bedrock:List*`, which covers `bedrock:ListGuardrails`,
  `bedrock:ListEnforcedGuardrailsConfiguration`, `bedrock:ListAgents`, `bedrock:ListAgentAliases`,
  `bedrock:ListFlows`; `bedrock:GetAgent`, `bedrock:GetAgentAlias`;
  `bedrock:GetModelInvocationLoggingConfiguration` (locates the invocation log group).
- **Organizations:** `organizations:DescribeEffectivePolicy` (policy type `BEDROCK_POLICY`; callable from
  any account in the organization — "not in an Organization" or a denial is reported as a disclosed gap).
- **CloudWatch:** `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics` (`AWS/Bedrock/Guardrails`
  `Invocations` by `GuardrailArn` + `GuardrailVersion`, `InvocationsIntervened`; `AWS/Bedrock` `Invocations`).
- **CloudWatch Logs:** `logs:DescribeLogGroups`, `logs:StartQuery`, `logs:GetQueryResults`,
  `logs:FilterLogEvents` (invocation-log `appliedGuardrailDetails` when model invocation logging is on).
- **KMS:** `kms:DescribeKey` (confirms a customer-managed key behind `kmsKeyArn`, LLM-GRD-010).

**Add as an inline policy on the Agent Space role** (both are in `ReadOnlyAccess`, so the read-only
session guardrail allows them, but neither is in `AIDevOpsAgentAccessPolicy`):

- `bedrock:GetFlow` — prompt-node and knowledge-base-node `guardrailConfiguration` in Amazon Bedrock Flows.
- `bedrock:GetAgentVersion` — the `guardrailConfiguration` recorded on the agent version an alias serves.

Without them the skill reports the flow / agent-version resolution as a disclosed permission gap, not as
an absent guardrail. `automation/cloudformation/llmops-agent-iam.yaml` and `automation/terraform/main.tf`
grant the same list.

> **Note.** The DevOps Agent `use_aws` tool refuses IAM calls that name an AWS managed policy ARN
> (for example `iam:GetPolicyVersion` on `arn:aws:iam::aws:policy/...`) and all `iam:Simulate*` calls.
> The checks above do not need them; any future IAM-enforcement check must disclose that limit.

No write, modify, or delete permissions are needed or used. `bedrock:ApplyGuardrail` and
`bedrock:InvokeGuardrailChecks` are never called: both invoke the guardrail and are billable (see
Guardrails rule 1 in `SKILL.md`).

## Uploading to AWS DevOps Agent

Package the skill as a zip with `SKILL.md` at the **archive root** (not nested under a folder). Zip
from **inside** the skill directory:

```bash
cd skills/llmops-guardrails && zip -r ../llmops-guardrails.zip . -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

This produces `skills/llmops-guardrails.zip` containing `SKILL.md`, `references/`, and `assets/` at the
top level, with the repo-management files excluded.

> **CRITICAL:** When uploading, select **All agents** as the Agent Type. The custom `llmops-agent` can
> only load the skill if it is published to all agents — selecting a single built-in agent type will
> prevent the custom agent from seeing it.

## Usage Examples

- "Is anything actually protecting our customer-facing model, or are we invoking it raw?" → Steps 1–2,
  LLM-GRD-001 (after the enforcement read in Step 1a; LLM-GRD-021 when nothing is enforced).
- "Our guardrail looks strong in the console but it isn't blocking anything in production." → the
  DRAFT-not-pinned trap, LLM-GRD-006, or detect mode (action `NONE`), LLM-GRD-011.
- "Could PII be leaking into our prompts or completions?" → LLM-GRD-003 sensitive-information policy.
- "Did we ever actually test this guardrail?" → LLM-GRD-007: the skill reports whether validation
  evidence exists and gives the exact command for the customer to run the test themselves (the skill
  never invokes a guardrail).
- "We have a RAG assistant — is anything stopping it hallucinating off-source?" → LLM-GRD-008
  contextual grounding.
- "InvocationsIntervened spiked overnight — should we loosen the guardrail?" → investigate attack vs
  false-positive first; a spike is often the guardrail working.
- "Our assistant uses tools and the guardrail shows zero interventions, but PII from a tool result still
  reaches the model." → on the Converse API a guardrail does not evaluate tool results; the application
  has to screen them (`references/documented-behavior.md` §1).
- "Grounding blocks our answers — should we lower the threshold?" → read each blocked sample's score
  against its threshold first (`references/documented-behavior.md` §4, LLM-GRD-008).
- "Why is the same prompt blocked only sometimes?" → rule out version, side, detect mode and streaming
  mode, then say what AWS documents (ML-based safeguards are probabilistic) without naming a cause the
  evidence does not show (`references/documented-behavior.md` §2).

## Version History

See the `CHANGELOG.md` file in this directory.
