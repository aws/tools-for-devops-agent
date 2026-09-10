# Changelog

All notable changes to the `aiml-bedrock-security-assessment` skill are documented
here. This project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-09

### Added
- Initial release. Read-only Amazon Bedrock security posture assessment as an AWS
  DevOps Agent skill — the Bedrock domain of a per-domain AI/ML security posture
  family.
- **33 read-only Bedrock checks (`BR-01`..`BR-33`)** covering guardrail coverage
  (content filters, sensitive-information, contextual grounding, automated
  reasoning, tiers), KMS encryption (custom/imported models, knowledge bases,
  invocation logs, batch output), VPC private connectivity, agent and
  action-group IAM least privilege, agent guardrail association and idle-session
  TTL, CloudTrail coverage, CloudWatch alarms, service-quota throttling, and
  Inspector Lambda scanning.
- **Verify-vs-prescribe determinism contract:** each check is classified
  `Verifiable` (22), `Heuristic` (10), or `Prescribe-only` (1). The report never
  marks an unread or access-denied control as `Passed`; `BR-14` (stale access) is
  always `N/A` under the DevOps Agent read-only guardrail.
- **Owns-vs-defers boundaries** against `bedrock-adoption-readiness`,
  `aiml-access-diagnostics`, and `agentcore-observability-setup`.
- Orchestrator `SKILL.md`, per-check catalog
  (`references/bedrock-checks.md`), and finding schema + report format
  (`references/finding-schema-and-report.md`).
- Multi-region and multi-account support via AWS DevOps Agent account
  associations (findings carry an `Account` field; global IAM/Org checks emitted
  once per account; the skill never assumes roles itself).

### Notes
- Scope is intentionally Amazon Bedrock only. SageMaker, AgentCore, Agentic-AI,
  Responsible AI GRC, and OWASP Top 10 for LLM are separate skills, not phases of
  this one.
