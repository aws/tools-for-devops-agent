# Changelog

## [1.0.2] - 2026-10-21
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## [1.0.1] - 2026-10-21
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## [1.0.0] - 2026-08-21
### Added
- Initial release (4 dimensions)
- D1: IAM governance with full policy document inspection (managed + inline)
- D2: Data retention / ZDR with Covered Model detection fallback and three-regime model
- D3: Quota headroom with per-model comparison, cache awareness, and 5:1 burndown rate
- D6: Operational observability aligned with CWR checklist thresholds
- Dual-surface support: Standard Bedrock (AWS/Bedrock) and Mantle (AWS/BedrockMantle)
- Multi-region discovery and assessment
- Three-state dimension model: ASSESSED / NOT_ASSESSED / INSUFFICIENT_DATA
- Graceful degradation for member-account SCP access and retention API availability
- Severity-rated findings (CRITICAL/HIGH/MEDIUM/LOW/INFO)
- Structured report output with priority matrix and verdict
