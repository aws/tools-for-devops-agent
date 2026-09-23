# Amazon SageMaker AI Security Assessment — AWS DevOps Agent Skill

An AWS DevOps Agent skill that runs a **read-only** Amazon SageMaker AI security
posture assessment across an AWS account, regions, and associated accounts. It
covers **25 checks (`SM-01`..`SM-25`)** spanning network exposure/isolation, KMS
encryption at rest, notebook root access, endpoint availability, monitoring and
drift detection, GuardDuty coverage, and MLOps governance, and produces a
consolidated, severity-rated findings report.

The DevOps Agent runs the read-only checks directly using its AWS API access,
then assembles the report. No infrastructure is deployed in the account.

> ⚠️ This skill is sample code, not intended for production use without additional
> review and testing. Validate in a non-production environment first.

## Scope: what it owns vs. defers

This is the **SageMaker domain** of a per-domain family of AI/ML security posture
skills.

- **Owns** — proactive, point-in-time **security misconfiguration posture** of
  SageMaker resources.
- **Defers to
  [`aiml-access-diagnostics`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-access-diagnostics/SKILL.md)**
  — reactive diagnosis of *why a specific SageMaker call was denied*. This skill
  reports static IAM posture only, never a specific denial.
- **Cross-references, does not call** — AWS Security Hub control IDs
  (SageMaker.1–5) are cited for convenience; the skill never calls `securityhub:*`.
- **Out of scope** — Amazon Bedrock and Amazon Bedrock AgentCore (separate
  skills), Responsible AI GRC, and OWASP Top 10 for LLM.

## Verify vs. prescribe

Every check is classified so the report never marks an unread control as
`Passed`:

- **Verifiable (18 checks)** — a read-only call returns the exact config.
- **Heuristic (7 checks)** — readable but inferred (MLOps maturity, IAM
  least-privilege); the verdict cites evidence, and ambiguous/denied reads become
  `N/A`, not `Passed`.
- **`SM-02` mixed** — AmazonSageMakerFullAccess detection is Heuristic; its
  *stale-access* aspect (needs `iam:GenerateServiceLastAccessedDetails`, a
  `Generate*` verb blocked by the read-only guardrail) and *IAM Identity Center*
  aspect (not control-plane readable) are **Prescribe-only** and are never marked
  `Passed`.

See
[`references/sagemaker-checks.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-sagemaker-security-assessment/references/sagemaker-checks.md)
for the per-check classification and
[`references/finding-schema-and-report.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aiml-sagemaker-security-assessment/references/finding-schema-and-report.md)
for the output contract.

## Read-only guarantee

Every check is read-only (`Describe*`/`List*`/`Get*`). The skill never creates,
modifies, deletes, enables, or disables any resource, and never calls non-read
verbs (including analysis verbs like `iam:GenerateServiceLastAccessedDetails`).
Remediation is reported as guidance only.

## Prerequisites

- An AWS DevOps Agent **Agent Space** with this skill imported.
- The agent's execution role needs read-only access to the assessed services. The
  baseline **`AIDevOpsAgentAccessPolicy`** covers most reads; the SageMaker-specific
  reads (`sagemaker:List*`/`Describe*`) and `guardduty:ListDetectors` are delivered
  as a **gated read-only inline policy** (`EnableAIMLSageMakerSecurityAssessment`,
  default `true`) in the repository's `cloudformation/devops-agent-skill-policies.yaml`.
  Checks whose reads are not granted return `N/A (AccessDenied)`.
- **(Multi-account, optional)** Associate each additional account with the Agent
  Space as a secondary source with a monitoring role carrying
  `AIDevOpsAgentAccessPolicy` plus the gated add-on.

## Usage

Invoke the agent conversationally, e.g.:

- "Run the Amazon SageMaker security assessment in `us-east-1` (read-only)."
- "Audit our SageMaker notebooks and domains for internet exposure and encryption
  at rest across `us-east-1` and `us-west-2`."
- "Assess SageMaker security across all associated accounts and give me a
  per-account breakdown."

## Importing the skill

Zip the `aiml-sagemaker-security-assessment/` directory (must contain `SKILL.md`
with frontmatter) and upload via the Operator Web App, or import from the GitHub
directory. ZIP only, ≤ 6 MB, ≤ 100 files, no `scripts/` directory.

## Limitations

- **Point-in-time:** results reflect configuration at scan time; re-run regularly.
- **No guarantee of security/compliance:** identifies common misconfigurations
  against AWS best practices; does not replace formal audits.
- **Shared Responsibility Model:** assesses customer-configurable controls, not
  AWS-managed infrastructure.
- **Coverage:** Amazon SageMaker AI only.

## Provenance

SageMaker check definitions, severities, API calls, and reference URLs derive from
the open-source
[AWS AI/ML Security Assessment](https://github.com/aws-samples/sample-aiml-security-assessment)
framework, licensed MIT-0 upstream.
