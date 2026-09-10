---
name: aiml-bedrock-security-assessment
description: "Run a read-only Amazon Bedrock security posture assessment across an AWS account, regions, and associated accounts. Use when asked to assess, audit, or review the security of Amazon Bedrock generative-AI workloads: guardrail coverage (content filters, sensitive-information/PII, contextual grounding, automated reasoning, tiers), model-invocation logging and encryption, KMS encryption of knowledge bases and custom/imported models and batch output, VPC interface endpoints, agent and action-group IAM least privilege, agent guardrail association and idle-session TTL, CloudTrail coverage, CloudWatch alarms, service-quota throttling, and Inspector Lambda scanning. Produces structured findings (Check_ID, severity, status, verifiability, remediation) and a consolidated report. Strictly read-only (describe/list/get only); never mutates or remediates. Proactive posture audit only — for a specific access denial use aiml-access-diagnostics; for Bedrock adoption readiness use bedrock-adoption-readiness."
metadata:
  author: apparaka
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Prevention"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock"
  aws-devops-agent-skills.technical-domains: "Machine Learning, Security"
---

# Amazon Bedrock Security Assessment

Assess the security posture of Amazon Bedrock workloads on AWS and produce a
consolidated, severity-rated findings report. **You (the agent) run read-only
checks directly** using your AWS API access, then assemble the report. No
infrastructure is deployed.

This is the first domain in a per-domain family of AI/ML security posture skills.
It covers **33 Amazon Bedrock checks (`BR-01`..`BR-33`)**. SageMaker, AgentCore,
and cross-cutting Agentic-AI posture are separate skills, not phases of this one.

Guidance is aligned with the AWS Well-Architected Generative AI Lens and the
Amazon Bedrock security documentation.

## Scope: what this skill owns vs. defers

This skill is **one of several** Bedrock/AI-ML skills in this repository. To avoid
divergent or duplicated results, it draws hard boundaries:

**Owns** — *proactive, point-in-time security misconfiguration posture* of Bedrock
control-plane resources: guardrail coverage and tiers, KMS encryption of models /
knowledge bases / logs / batch output, VPC private connectivity, agent and
action-group IAM least privilege, agent guardrail association, security logging
*presence* (invocation logging + CloudTrail), and abuse/monitoring controls
(alarms, throttling, Inspector).

**Defers to `bedrock-adoption-readiness`** — Bedrock *production-adoption
readiness*: data-retention/ZDR posture, quota and capacity *headroom* planning,
operational observability *maturity* (dashboards/metrics depth), and
bedrock-mantle (OpenAI-compatible) surface. Where a check here touches that
surface (BR-22 throttling quota; BR-04/BR-06/BR-32 logging/alarms), this skill
evaluates only the **security control's presence**, not readiness/headroom depth,
and says so in the finding.

**Defers to `aiml-access-diagnostics`** (reactive) — diagnosing *why a specific
Bedrock call was denied* by tracing the authorization chain (`iam:PassRole`, trust
policy, permissions, resource policy, SCPs). This skill never diagnoses a specific
denial; it reports static IAM *posture* (e.g. an over-broad managed policy
attached). See "Coordinating with aiml-access-diagnostics" below.

**Out of scope entirely** — Amazon SageMaker, Amazon Bedrock AgentCore (including
AgentCore observability, owned by `agentcore-observability-setup`), Responsible AI
GRC, and OWASP Top 10 for LLM. Do not attempt those checks from this skill.

## SAFETY: read-only assessment

This assessment is strictly **read-only**. When executing it:

- **ONLY** call `Describe*`, `List*`, `Get*`, `BatchGet*`, and equivalent read
  operations. NEVER call any API that creates, updates, deletes, attaches,
  enables, disables, or otherwise mutates a resource, configuration, policy,
  guardrail, or IAM entity.
- Do **not** modify resources to "fix" a finding. Remediation is reported as
  guidance only; the customer applies changes separately.
- Never call a non-`Get`/`List`/`Describe` verb — including analysis verbs such as
  `iam:GenerateServiceLastAccessedDetails`. The DevOps Agent platform enforces a
  read-only guardrail that blocks such verbs, and this skill treats any control
  that would require them as **Prescribe-only** (see below), never as Passed.
- Treat every account as production unless told otherwise.

If asked to remediate, first present the findings, then confirm explicitly with
the user before proposing any change — and even then, propose, do not apply,
unless separately authorized.

## Verify vs. prescribe (determinism contract)

Not every best practice is provable from the control plane. Every check in
`references/bedrock-checks.md` carries a **Verifiability** classification, and you
MUST honor it so the report never marks an unread control as `Passed`:

- **Verifiable** — a read-only `Get`/`List`/`Describe` returns the exact
  configuration. Emit `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — readable, but the verdict is an inference (e.g. IAM
  least-privilege judged from policy contents). Apply the check's stated rule
  exactly and **cite the concrete evidence** (policy name, ARN, field value) in
  `Finding_Details`. If the evidence is ambiguous or the needed read is denied,
  emit `N/A` with the reason — **never guess `Passed`**.
- **Prescribe-only** — cannot be proven read-only under the DevOps Agent (the
  required verb is blocked, or no control-plane field exposes the state). Emit
  `N/A` and put the recommended configuration in `Resolution`. **Never emit
  `Passed` or `Failed` for a Prescribe-only check.** In v1 this is **BR-14**
  (stale Bedrock access), which needs `iam:GenerateServiceLastAccessedDetails`.

When read access is denied for any check, the status is `N/A` (reason:
`AccessDenied`), never `Passed`.

## Workflow

Follow these steps in order.

### Step 1 — Confirm intent and scope

1. Confirm the user wants a **read-only** Amazon Bedrock security assessment. State
   the read-only guarantee above.
2. This skill runs the Bedrock family (`BR-01`..`BR-33`) only. If the user asks
   for SageMaker, AgentCore, Agentic-AI, Responsible AI GRC, or OWASP, tell them
   those are separate skills and stay in Bedrock scope.
3. Determine which **accounts** are in scope (see "Multi-account execution"):
   default is the primary account; if the user names account IDs or says "all
   accounts"/"the organization", scope to those associated accounts.
4. Record the account ID(s) (`sts:GetCallerIdentity` per account) for the header.

### Step 2 — Resolve target regions

See `references/finding-schema-and-report.md` → "Region resolution". In short:
- Default: the current/session region only.
- Explicit list (e.g. `us-east-1, us-west-2`): use those.
- "all regions": the union of regions where `bedrock` is available.

### Step 3 — Run the Bedrock checks per region

Open `references/bedrock-checks.md` and execute every check. Each entry gives the
read-only API call(s), the pass/fail/N-A logic, severity, **verifiability**,
resolution text, and a documentation reference URL (an HTTPS link).

**Follow each entry's evaluation logic and API list exactly.** In particular,
Bedrock **prompts, agents, knowledge bases, flows, and agent action groups** are
under the **`bedrock-agent`** service (e.g. `bedrock-agent:ListPrompts`,
`bedrock-agent:ListAgents`), **not** the `bedrock` service; using the wrong client
yields a false `N/A`. If one API name is unavailable in the SDK, use the
equivalent under the correct service rather than marking the check `N/A`.

Produce one finding per check per applicable region, conforming exactly to the
schema in `references/finding-schema-and-report.md`, including the `Verifiability`
field.

### Step 4 — Assemble and present the report

Consolidate all findings and produce the report described in
`references/finding-schema-and-report.md`: an executive summary (counts by
severity, by region/scope, and by verifiability), a priority list of High-severity
`Failed` findings, the full findings table, and a machine-readable JSON block. Do
not omit `Passed` or `N/A` findings from the machine-readable output.

## Multi-region execution

Some findings are **global** (derived from IAM or AWS Organizations data) and are
identical across regions. Emit each global check **once**, tagged
`Region: "Global"`, on the first (primary) region only. All other findings carry
their actual region.

Global (emit once, `Region: "Global"`): `BR-01`, `BR-03`, `BR-14`, `BR-15`. Every
other BR check is regional. When Bedrock is unavailable in a region, emit its
regional checks as `N/A` for that region rather than skipping them. In
multi-account runs, "emit once" means once **per account**, because IAM/Org
posture differs by account.

## Multi-account execution

Cross-account access comes from the **Agent Space associations**, not from this
skill. The DevOps Agent service assumes the read-only monitoring role in each
associated account directly — **do not attempt `sts:AssumeRole` yourself**. See
`references/finding-schema-and-report.md` → "Account resolution".

- **Default:** assess only the **primary** account.
- **Explicit list:** assess the account IDs the user names; each must be an
  associated account in this Agent Space.
- **"all accounts"/"the organization":** assess every associated account.

For each in-scope account, scope every read-only call to that account, set the
`Account` field on every finding, and emit each global check once per account.

## Coordinating with aiml-access-diagnostics

This skill (proactive posture) and `aiml-access-diagnostics` (reactive
denial-tracing) share a Bedrock config-read + IAM-read surface. To stay
consistent:
- **Ownership:** this skill owns the *point-in-time posture snapshot*;
  `aiml-access-diagnostics` owns *tracing a specific `AccessDenied`*. If a user
  reports a specific failing call, hand off to `aiml-access-diagnostics` rather
  than inferring the cause here.
- **Shared verify-vs-prescribe model:** both skills use the same rule — a control
  that cannot be read under the platform's read-only guardrail is reported as
  `N/A`/Prescribe-only, never `Passed`. Keep this wording aligned across both
  skills.

## Notes and limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls (IAM,
  encryption, network isolation, logging), not AWS-managed infrastructure.
- **Coverage:** Amazon Bedrock only. Other AI/ML services are separate skills.
