# Amazon Bedrock Security Assessment — AWS DevOps Agent Skill

An AWS DevOps Agent skill that runs a **read-only** Amazon Bedrock security posture
assessment across an AWS account and regions (and, optionally, across associated
accounts). It covers **33 Bedrock checks (`BR-01`..`BR-33`)** spanning guardrail
coverage, KMS encryption, VPC private connectivity, agent/action-group IAM,
logging, alarms, throttling, and Inspector scanning, and produces a consolidated,
severity-rated findings report.

The DevOps Agent runs the read-only checks directly using its AWS API access, then
assembles the report. No infrastructure is deployed in the account.

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Validate in a non-production environment first.

## Scope: what it owns vs. defers

This is the **Bedrock domain** of a per-domain family of AI/ML security posture
skills. It deliberately draws boundaries against the other AI/ML skills in this
repository:

- **Owns** — proactive, point-in-time **security misconfiguration posture** of
  Bedrock control-plane resources (guardrails, encryption, network, agent IAM,
  logging presence, abuse controls).
- **Defers to
  [`bedrock-adoption-readiness`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/bedrock-adoption-readiness/SKILL.md)**
  — Bedrock production-adoption readiness (ZDR/data-retention, quota/capacity
  headroom, observability maturity, bedrock-mantle surface).
- **Defers to
  [`aiml-access-diagnostics`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-access-diagnostics/SKILL.md)**
  — reactive diagnosis of *why a specific Bedrock call was denied* (authorization
  chain tracing). This skill reports static IAM posture only, never a specific
  denial.
- **Out of scope** — Amazon SageMaker, Amazon Bedrock AgentCore (AgentCore
  observability is owned by
  [`agentcore-observability-setup`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/agentcore-observability-setup/SKILL.md)),
  Responsible AI GRC, and OWASP Top 10 for LLM — each a separate skill.

## Verify vs. prescribe

Every check is classified so the report never marks an unread control as
`Passed`:

- **Verifiable (22 checks)** — a read-only call returns the exact config;
  deterministic verdict.
- **Heuristic (10 checks)** — readable but inferred (e.g. IAM least-privilege);
  the verdict cites concrete evidence, and ambiguous/denied reads become `N/A`,
  not `Passed`.
- **Prescribe-only (1 check — `BR-14` stale access)** — requires
  `iam:GenerateServiceLastAccessedDetails`, a `Generate*` verb the DevOps Agent
  read-only guardrail blocks; always reported `N/A` with out-of-band remediation,
  never `Passed`/`Failed`.

See
[`references/bedrock-checks.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-bedrock-security-assessment/references/bedrock-checks.md)
for the per-check classification and
[`references/finding-schema-and-report.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-bedrock-security-assessment/references/finding-schema-and-report.md)
for the output contract.

## Read-only guarantee

Every check is read-only (`Describe*`/`List*`/`Get*`/`BatchGet*`). The skill never
creates, modifies, deletes, attaches, enables, or disables any resource, and never
calls non-read verbs (including analysis verbs like
`iam:GenerateServiceLastAccessedDetails`). Remediation is reported as guidance
only.

## Prerequisites

- An AWS DevOps Agent **Agent Space** with this skill imported.
- The agent's execution role needs read-only access to the assessed services. The
  baseline **`AIDevOpsAgentAccessPolicy`** covers most reads; the Bedrock-specific
  reads beyond that baseline (e.g. `bedrock:Get*`/`List*`, `bedrock-agent:*` reads,
  `cloudtrail:Get*`, `servicequotas:Get*`, `inspector2:BatchGetAccountStatus`) are
  delivered as a **gated read-only inline policy**
  (`EnableAIMLBedrockSecurityAssessment`, default `true`) in the repository's
  `cloudformation/devops-agent-skill-policies.yaml`. Checks whose reads are not
  granted return `N/A (AccessDenied)`.
- **(Multi-account, optional)** Associate each additional account with the Agent
  Space as a secondary source with a monitoring role carrying
  `AIDevOpsAgentAccessPolicy` plus the gated add-on. The DevOps Agent service
  assumes that read-only role directly; the skill does not assume roles itself.

## Usage

Invoke the agent conversationally, e.g.:

- "Run the Amazon Bedrock security assessment in `us-east-1` (read-only)."
- "Audit our Bedrock guardrails and model-invocation logging across `us-east-1`
  and `us-west-2`."
- "Assess Bedrock security across all associated accounts and give me a
  per-account breakdown."

## Importing the skill

Zip the `aiml-bedrock-security-assessment/` directory (must contain `SKILL.md`
with frontmatter) and upload via the Operator Web App (Knowledge → Skills → Add
skill), or import from the GitHub directory. ZIP only, ≤ 6 MB, ≤ 100 files, no
`scripts/` directory.

## Limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls, not
  AWS-managed infrastructure.
- **Coverage:** Amazon Bedrock only.

## Provenance

Bedrock check definitions, severities, API calls, and reference URLs derive from
the open-source
[AWS AI/ML Security Assessment](https://github.com/aws-samples/sample-aiml-security-assessment)
framework (`docs/SECURITY_CHECKS*.md`), licensed MIT-0 upstream.
