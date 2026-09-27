# Changelog

All notable changes to the `aiml-agentcore-security-assessment` skill are
documented here. This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-17

### Added
- Initial release. Read-only Amazon Bedrock AgentCore security posture assessment
  as an AWS DevOps Agent skill — the AgentCore domain of a per-domain AI/ML
  security posture family.
- **16 read-only AgentCore checks** (`AC-01`, `AC-02`, `AC-03`, `AC-05`..`AC-17`)
  covering runtime VPC configuration, IAM least-privilege, KMS encryption of ECR
  repositories / agent memory / policy engine / gateways, VPC endpoints, the
  service-linked role, resource-based policies, browser-tool recording storage,
  and gateway security — configuration plus native gateway checks for inbound
  authorization, tool-policy enforcement, error-detail exposure, and WAF
  protection (`AC-14`..`AC-17`).
- **Verify-vs-prescribe determinism contract:** each check is classified
  `Verifiable` (13), `Heuristic` (2: `AC-02`, `AC-10`), or `Prescribe-only`
  (1: `AC-03`). The report never marks an unread or access-denied control as
  `Passed`; `AC-03` (stale access) is always `N/A` under the read-only guardrail.
- **Owns-vs-defers boundary:** `AC-04` (observability) is intentionally excluded
  and deferred to the merged `agentcore-observability-setup` skill; reactive
  access-denial diagnosis is deferred to `aiml-access-diagnostics`.
- Orchestrator `SKILL.md`, per-check catalog (`references/agentcore-checks.md`),
  and finding schema + report format (`references/finding-schema-and-report.md`).
- Multi-region and multi-account support via AWS DevOps Agent account associations.

### Notes
- Uses the `bedrock-agentcore` IAM action prefix (the `-control` suffix is only
  the SDK client name).
- Scope is intentionally Amazon Bedrock AgentCore only. Bedrock and SageMaker are
  separate skills, not phases of this one.
