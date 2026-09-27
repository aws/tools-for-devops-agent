# Amazon Bedrock AgentCore Security Assessment — AWS DevOps Agent Skill

An AWS DevOps Agent skill that runs a **read-only** Amazon Bedrock AgentCore
security posture assessment across an AWS account, regions, and associated
accounts. It covers **16 checks** (`AC-01`, `AC-02`, `AC-03`, `AC-05`..`AC-17`)
spanning runtime VPC configuration, IAM least-privilege, KMS encryption of ECR /
memory / policy engine / gateways, VPC endpoints, service-linked role,
resource-based policies, browser-tool recording storage, and gateway security
(configuration, inbound authorization, tool-policy enforcement, error-detail
exposure, WAF), and produces a consolidated, severity-rated findings report.

The DevOps Agent runs the read-only checks directly using its AWS API access,
then assembles the report. No infrastructure is deployed in the account.

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Validate in a non-production environment first.

## Scope: what it owns vs. defers

This is the **AgentCore domain** of a per-domain family of AI/ML security posture
skills.

- **Owns** — proactive, point-in-time **security misconfiguration posture** of
  AgentCore control-plane resources (runtime network, IAM, encryption, VPC
  endpoints, resource policies, gateway security).
- **Defers `AC-04` (observability) to
  [`agentcore-observability-setup`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/agentcore-observability-setup/SKILL.md)**
  — that merged skill owns validating/bootstrapping AgentCore observability. This
  skill does not re-implement it; `AC-04` is intentionally excluded.
- **Defers to
  [`aiml-access-diagnostics`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-access-diagnostics/SKILL.md)**
  — reactive diagnosis of *why a specific AgentCore call was denied*. This skill
  reports static IAM posture only.
- **Out of scope** — Amazon Bedrock and Amazon SageMaker (separate skills),
  Responsible AI GRC, and OWASP Top 10 for LLM.

## Verify vs. prescribe

Every check is classified so the report never marks an unread control as
`Passed`:

- **Verifiable (13 checks)** — a read-only call returns the exact config.
- **Heuristic (2 checks — `AC-02` IAM, `AC-10` resource policy)** — readable but
  inferred; the verdict cites evidence, and ambiguous/denied reads become `N/A`,
  not `Passed`.
- **Prescribe-only (1 check — `AC-03` stale access)** — requires
  `iam:GenerateServiceLastAccessedDetails`, a `Generate*` verb blocked by the
  read-only guardrail; always reported `N/A` with out-of-band remediation, never
  `Passed`/`Failed`.

See
[`references/agentcore-checks.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-agentcore-security-assessment/references/agentcore-checks.md)
for the per-check classification and
[`references/finding-schema-and-report.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-agentcore-security-assessment/references/finding-schema-and-report.md)
for the output contract.

## Read-only guarantee

Every check is read-only (`Describe*`/`List*`/`Get*`). The skill never creates,
modifies, deletes, enables, or disables any resource, and never calls non-read
verbs (including analysis verbs like `iam:GenerateServiceLastAccessedDetails`).
Remediation is reported as guidance only. The skill uses the `bedrock-agentcore`
IAM action prefix (the `-control` suffix is only the SDK client name).

## Prerequisites

- An AWS DevOps Agent **Agent Space** with this skill imported.
- The agent's execution role needs read-only access to the assessed services. The
  baseline **`AIDevOpsAgentAccessPolicy`** covers IAM/EC2/KMS reads; the
  AgentCore-specific reads (`bedrock-agentcore:Get*`/`List*`) and
  `ecr:DescribeRepositories` are delivered as a **gated read-only inline policy**
  (`EnableAIMLAgentCoreSecurityAssessment`, default `true`) in the repository's
  `cloudformation/devops-agent-skill-policies.yaml`. Checks whose reads are not
  granted return `N/A (AccessDenied)`.
- **(Multi-account, optional)** Associate each additional account with the Agent
  Space as a secondary source with a monitoring role carrying
  `AIDevOpsAgentAccessPolicy` plus the gated add-on.

## Usage

Invoke the agent conversationally, e.g.:

- "Run the Amazon Bedrock AgentCore security assessment in `us-east-1`
  (read-only)."
- "Audit our AgentCore runtimes and gateways for VPC configuration, encryption,
  and inbound authorization."
- "Assess AgentCore security across all associated accounts and give me a
  per-account breakdown."

For AgentCore *observability* (traces/telemetry), use the
`agentcore-observability-setup` skill instead.

## Importing the skill

Zip the `aiml-agentcore-security-assessment/` directory (must contain `SKILL.md`
with frontmatter) and upload via the Operator Web App, or import from the GitHub
directory. ZIP only, ≤ 6 MB, ≤ 100 files, no `scripts/` directory.

## Limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls, not
  AWS-managed infrastructure.
- **Coverage:** Amazon Bedrock AgentCore only; observability is owned by
  `agentcore-observability-setup`.

## Provenance

AgentCore check definitions, severities, API calls, and reference URLs derive from
the open-source
[AWS AI/ML Security Assessment](https://github.com/aws-samples/sample-aiml-security-assessment)
framework, licensed MIT-0 upstream.
