# Changelog

## 1.0.3
- Updated the link to the skill IAM policies template, which moved to `cloudformation/devops-agent-skill-policies/`.

## 1.0.2
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0
- Initial release
- DMS operational review with 5-category health scoring (100 points)
- Troubleshooting workflow with 8 error classification categories
- Migration cutover runbook (pre-cutover, execution, rollback, cleanup)
- Version lifecycle tracking with known bug cross-reference
- DMS Serverless vs provisioned suitability assessment
- Homogeneous data migration evaluation
- Pre-migration assessment guidance (Fleet Advisor, SCT)
- Data validation failure investigation
- Cost optimization with right-sizing and idle resource detection
- Reference files: best practices, validation checklist, version reference
- Evaluation test cases (10 functional evals, 6 trigger queries)
