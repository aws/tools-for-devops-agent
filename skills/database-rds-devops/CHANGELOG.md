# Changelog

## [1.0.2] - 2026-10-21
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## [1.0.1] - 2026-10-21
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## [1.0.0] - 2026-07-16

### Added
- Initial release adapted from internal database expertise skill
- 12-dimension AWS-level health scoring for Aurora MySQL/PostgreSQL
- 8-dimension database-level health scoring (50 points max)
- 23 MySQL health check queries across 9 diagnostic categories
- 4 PostgreSQL health check queries (active sessions, bloat, top queries, wraparound)
- CloudWatch Metrics analysis with severity thresholds
- CloudWatch Logs Insights integration (slow query, error, PostgreSQL logs)
- 33-check Aurora operational validation checklist
- Platform-aware diagnostics (Aurora MySQL vs RDS MySQL vs Aurora PostgreSQL)
- Correlation engine for cross-layer diagnostic findings
- Error pattern recognition for common MySQL/PostgreSQL issues
- Support for Aurora MySQL 2.x/3.x, RDS MySQL 5.7/8.0, Aurora/RDS PostgreSQL
