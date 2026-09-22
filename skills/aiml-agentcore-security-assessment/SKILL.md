---
name: aiml-agentcore-security-assessment
description: "Run a read-only Amazon Bedrock AgentCore security posture assessment across an AWS account, regions, and associated accounts. Use when asked to assess, audit, or review the security of Amazon Bedrock AgentCore workloads: agent-runtime VPC configuration, IAM least privilege, KMS encryption of ECR repositories, agent memory, the policy engine, and gateways, VPC endpoints, the AgentCore service-linked role, resource-based policies, browser-tool recording storage, and gateway security (configuration, inbound authorization, tool-policy enforcement, error-detail exposure, and WAF protection). Produces structured findings (Check_ID, severity, status, verifiability, remediation) and a consolidated report. Strictly read-only (describe/list/get only); never mutates or remediates. Proactive posture audit only — AgentCore observability is owned by agentcore-observability-setup, and a specific access denial by aiml-access-diagnostics."
metadata:
  author: apparaka
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Prevention"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock AgentCore"
  aws-devops-agent-skills.technical-domains: "Machine Learning, Security"
---

# Amazon Bedrock AgentCore Security Assessment

Assess the security posture of Amazon Bedrock AgentCore workloads on AWS and
produce a consolidated, severity-rated findings report. **You (the agent) run
read-only checks directly** using your AWS API access, then assemble the report.
No infrastructure is deployed.

This is the AgentCore domain of a per-domain family of AI/ML security posture
skills. It covers **16 AgentCore checks** — `AC-01`, `AC-02`, `AC-03`, and
`AC-05`..`AC-17`. Amazon Bedrock and Amazon SageMaker are separate skills, not
phases of this one.

Guidance is aligned with the AWS Well-Architected Agentic AI Lens and the Amazon
Bedrock AgentCore security documentation.

## Scope: what this skill owns vs. defers

**Owns** — *proactive, point-in-time security misconfiguration posture* of
AgentCore control-plane resources: runtime network configuration, IAM
least-privilege, encryption at rest (ECR, memory, policy engine, gateway), VPC
endpoints, service-linked role, resource-based policies, and gateway security.

**Defers `AC-04` (observability) to
[`agentcore-observability-setup`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/agentcore-observability-setup/SKILL.md)**
— that merged skill owns validating and bootstrapping AgentCore observability
(CloudWatch Transaction Search, log/trace delivery, X-Ray). This skill does **not**
re-implement it; `AC-04` is intentionally excluded from the check set.

**Defers to `aiml-access-diagnostics`** (reactive) — diagnosing *why a specific
AgentCore call was denied* by tracing the authorization chain. This skill reports
static IAM *posture* only, never a specific denial.

**Out of scope entirely** — Amazon Bedrock and Amazon SageMaker (separate skills),
Responsible AI GRC, and OWASP Top 10 for LLM.

## SAFETY: read-only assessment

This assessment is strictly **read-only**. When executing it:

- **ONLY** call `Describe*`, `List*`, `Get*`, `BatchGet*`, and equivalent read
  operations. NEVER call any API that creates, updates, deletes, attaches,
  enables, disables, or otherwise mutates a resource, configuration, policy, or
  IAM entity.
- Do **not** modify resources to "fix" a finding. Remediation is reported as
  guidance only; the customer applies changes separately.
- Never call a non-`Get`/`List`/`Describe` verb — including analysis verbs such
  as `iam:GenerateServiceLastAccessedDetails`. The DevOps Agent platform enforces
  a read-only guardrail that blocks such verbs, and this skill treats any control
  that would require them as **Prescribe-only** (see below), never as Passed.
- Use the `bedrock-agentcore` IAM action prefix (the `-control` suffix is only the
  SDK client name, not an IAM service prefix).
- Treat every account as production unless told otherwise.

If asked to remediate, first present the findings, then confirm explicitly with
the user before proposing any change — and even then, propose, do not apply,
unless separately authorized.

## Verify vs. prescribe (determinism contract)

Not every best practice is provable from the control plane. Every check in
`references/agentcore-checks.md` carries a **Verifiability** classification, and
you MUST honor it so the report never marks an unread control as `Passed`:

- **Verifiable** — a read-only `Describe`/`List`/`Get` returns the exact
  configuration. Emit `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — readable, but the verdict is an inference (e.g. IAM
  least-privilege or resource-policy scoping judged from contents). Apply the
  check's stated rule exactly and **cite the concrete evidence** (resource id,
  ARN, field value) in `Finding_Details`. If the evidence is ambiguous or the
  needed read is denied, emit `N/A` with the reason — **never guess `Passed`**.
- **Prescribe-only** — cannot be proven read-only under the DevOps Agent (the
  required verb is blocked, or no control-plane field exposes the state). Emit
  `N/A` and put the recommended configuration in `Resolution`. **Never emit
  `Passed`/`Failed`.** In this skill that is **AC-03** (stale AgentCore access),
  which needs `iam:GenerateServiceLastAccessedDetails`.

When read access is denied for any check, the status is `N/A` (reason:
`AccessDenied`), never `Passed`.

## Workflow

Follow these steps in order.

### Step 1 — Confirm intent and scope

1. Confirm the user wants a **read-only** Amazon Bedrock AgentCore security
   assessment. State the read-only guarantee above.
2. This skill runs the AgentCore family only. If the user asks for Bedrock,
   SageMaker, or AgentCore *observability*, point them to the respective skill
   (`agentcore-observability-setup` for observability).
3. Determine which **accounts** are in scope (default primary; or named IDs / "all
   accounts").
4. Record the account ID(s) (`sts:GetCallerIdentity` per account) for the header.

### Step 2 — Resolve target regions

See `references/finding-schema-and-report.md` → "Region resolution": default is
the current region; an explicit list uses those; "all regions" uses the union of
regions where `bedrock-agentcore` is available. AgentCore is not available in
every Region — emit its regional checks as `N/A` where unavailable.

### Step 3 — Run the AgentCore checks per region

Open `references/agentcore-checks.md` and execute every check. Each entry gives
the read-only API call(s), the pass/fail/N-A logic, severity, **verifiability**,
resolution text, and an `https` documentation reference. Global checks (`AC-02`,
`AC-03`, `AC-09`) draw on account-wide IAM data and are emitted once per account.

Produce one finding per check per applicable region, conforming exactly to the
schema in `references/finding-schema-and-report.md`, including the `Verifiability`
field.

### Step 4 — Assemble and present the report

Consolidate all findings and produce the report described in
`references/finding-schema-and-report.md`: an executive summary (counts by
severity, by region/scope, by verifiability), a priority list of High-severity
`Failed` findings, the full findings table, and a machine-readable JSON block. Do
not omit `Passed` or `N/A` findings from the machine-readable output.

## Multi-region execution

Global checks (`AC-02`, `AC-03`, `AC-09`) are IAM/account-derived and are emitted
**once**, tagged `Region: "Global"`, on the primary region (once per account in
multi-account runs). All other checks are regional; when AgentCore is unavailable
or has no matching resources in a region, emit the check as `N/A` for that region.

## Multi-account execution

Cross-account access comes from the **Agent Space associations**, not from this
skill. The DevOps Agent service assumes the read-only monitoring role in each
associated account directly — **do not attempt `sts:AssumeRole` yourself**. See
`references/finding-schema-and-report.md` → "Account resolution". For each
in-scope account, scope every read-only call to that account, set the `Account`
field on every finding, and emit each global check once per account.

## Notes and limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls (IAM,
  encryption, network isolation), not AWS-managed infrastructure.
- **Coverage:** Amazon Bedrock AgentCore only; observability is owned by
  `agentcore-observability-setup`. Other AI/ML services are separate skills.
