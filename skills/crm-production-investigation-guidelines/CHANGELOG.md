# Changelog

## 1.0.2
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0

- Initial version
- Investigation isolation rules for independent incident handling
- Structured investigation approach (symptoms → logs → audit → correlation → root cause → remediation)
- CRM application architecture documentation
- Common root cause patterns with specific AWS API calls to check
