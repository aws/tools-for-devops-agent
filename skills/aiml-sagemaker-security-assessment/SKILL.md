---
name: aiml-sagemaker-security-assessment
description: "Run a read-only Amazon SageMaker AI security posture assessment across an AWS account, regions, and associated accounts. Use when asked to assess, audit, or review the security of Amazon SageMaker AI workloads: notebook and domain direct-internet exposure and VPC-only deployment, notebook instance privileged-access settings, KMS encryption at rest (notebooks, models, Feature Store offline store, processing/transform/hyperparameter-tuning/compilation/AutoML volumes and output), model network isolation, container-repository (ECR) access mode, endpoint high-availability, Model Monitor and drift detection, GuardDuty coverage, and MLOps governance (Model Registry versioning, approval workflow, lineage). Produces structured findings (Check_ID, severity, status, verifiability, remediation) and a consolidated report. Strictly read-only (describe/list/get only); never mutates or remediates. Proactive posture audit only — for a specific access denial use aiml-access-diagnostics."
metadata:
  author: apparaka
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Prevention"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI"
  aws-devops-agent-skills.technical-domains: "Machine Learning, Security"
---

# Amazon SageMaker AI Security Assessment

Assess the security posture of Amazon SageMaker AI workloads on AWS and produce a
consolidated, severity-rated findings report. **You (the agent) run read-only
checks directly** using your AWS API access, then assemble the report. No
infrastructure is deployed.

This is the SageMaker domain of a per-domain family of AI/ML security posture
skills. It covers **25 SageMaker checks (`SM-01`..`SM-25`)**. Amazon Bedrock and
Amazon Bedrock AgentCore are separate skills, not phases of this one.

Guidance is aligned with the AWS Well-Architected Machine Learning Lens and the
Amazon SageMaker security documentation; several checks cross-reference an AWS
Security Hub control (SageMaker.1–5) for convenience.

## Scope: what this skill owns vs. defers

**Owns** — *proactive, point-in-time security misconfiguration posture* of
SageMaker resources: network exposure and isolation, encryption at rest,
notebook instance privileged-access settings, endpoint availability,
monitoring/drift, and MLOps governance signals.

**Defers to `aiml-access-diagnostics`** (reactive) — diagnosing *why a specific
SageMaker call was denied* by tracing the authorization chain (`iam:PassRole`,
trust policy, permissions, resource policy, SCPs). This skill never diagnoses a
specific denial; it reports static IAM *posture* only.

**Cross-references, does not call** — Security Hub control IDs (SageMaker.1–5) are
cited in findings for convenience; this skill does **not** call `securityhub:*`.

**Out of scope entirely** — Amazon Bedrock, Amazon Bedrock AgentCore, Responsible
AI GRC, and OWASP Top 10 for LLM. Each is a separate skill.

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
- Treat every account as production unless told otherwise.

If asked to remediate, first present the findings, then confirm explicitly with
the user before proposing any change — and even then, propose, do not apply,
unless separately authorized.

## Verify vs. prescribe (determinism contract)

Not every best practice is provable from the control plane. Every check in
`references/sagemaker-checks.md` carries a **Verifiability** classification, and
you MUST honor it so the report never marks an unread control as `Passed`:

- **Verifiable** — a read-only `Describe`/`List` returns the exact configuration.
  Emit `Passed`/`Failed`/`N/A` strictly from the returned data.
- **Heuristic** — readable, but the verdict is an inference (e.g. MLOps maturity
  or IAM least-privilege judged from contents). Apply the check's stated rule
  exactly and **cite the concrete evidence** (resource id, field value) in
  `Finding_Details`. If the evidence is ambiguous or the needed read is denied,
  emit `N/A` with the reason — **never guess `Passed`**.
- **Prescribe-only** — cannot be proven read-only under the DevOps Agent (the
  required verb is blocked, or no control-plane field exposes the state). Emit
  `N/A` and put the recommended configuration in `Resolution`. **Never emit
  `Passed`/`Failed`.**

**`SM-02` is a mixed check.** Its AmazonSageMakerFullAccess detection is
**Heuristic** (evaluated from attached policies). Its two other aspects are
**Prescribe-only** and MUST NOT be marked Passed: *stale SageMaker access* (needs
`iam:GenerateServiceLastAccessedDetails`, a blocked `Generate*` verb) and *IAM
Identity Center configuration* (not exposed on the control plane). Do not call
`Generate*`; report those aspects as prescribe guidance in the resolution.

When read access is denied for any check, the status is `N/A` (reason:
`AccessDenied`), never `Passed`.

## Workflow

Follow these steps in order.

### Step 1 — Confirm intent and scope

1. Confirm the user wants a **read-only** Amazon SageMaker security assessment.
   State the read-only guarantee above.
2. This skill runs the SageMaker family (`SM-01`..`SM-25`) only. If the user asks
   for Bedrock or AgentCore, tell them those are separate skills.
3. Determine which **accounts** are in scope (default primary; or named IDs / "all
   accounts").
4. Record the account ID(s) (`sts:GetCallerIdentity` per account) for the header.

### Step 2 — Resolve target regions

See `references/finding-schema-and-report.md` → "Region resolution": default is
the current region; an explicit list uses those; "all regions" uses the union of
regions where `sagemaker` is available.

### Step 3 — Run the SageMaker checks per region

Open `references/sagemaker-checks.md` and execute every check. Each entry gives
the read-only API call(s), the pass/fail/N-A logic, severity, **verifiability**,
resolution text, and an `https` documentation reference. All SageMaker checks are
**regional** — emit each per scanned region; when SageMaker has no matching
resources in a region, emit the check as `N/A` for that region.

Produce one finding per check per applicable region, conforming exactly to the
schema in `references/finding-schema-and-report.md`, including the `Verifiability`
field.

### Step 4 — Assemble and present the report

Consolidate all findings and produce the report described in
`references/finding-schema-and-report.md`: an executive summary (counts by
severity, by region, by verifiability), a priority list of High-severity `Failed`
findings, the full findings table, and a machine-readable JSON block. Do not omit
`Passed` or `N/A` findings from the machine-readable output.

## Multi-region execution

All SageMaker checks are regional. Emit each check per scanned region; when
SageMaker is unavailable or has no matching resources in a region, emit the
check as `N/A` for that region rather than skipping it.

## Multi-account execution

Cross-account access comes from the **Agent Space associations**, not from this
skill. The DevOps Agent service assumes the read-only monitoring role in each
associated account directly — **do not attempt `sts:AssumeRole` yourself**. See
`references/finding-schema-and-report.md` → "Account resolution". For each
in-scope account, scope every read-only call to that account and set the
`Account` field on every finding.

## Notes and limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls (IAM,
  encryption, network isolation), not AWS-managed infrastructure.
- **Coverage:** Amazon SageMaker AI only. Other AI/ML services are separate skills.
