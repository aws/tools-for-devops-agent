# Changelog

## 1.0.5
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (4 files). Agent types: On-demand (`CHAT`). The optional observability-sources table moved to its own section, "Connecting additional observability sources (optional)". The Agent Types section says **On-demand** and **Generic** instead of **Chat tasks** and **All agents**.

## 1.0.4
- `technical-domains` uses the approved value `Databases` instead of `Database`, so the skill is listed with the other database skills.
- `metadata.author` is the contributor's GitHub username, `abhit-cloud`, so catalogs link to their profile.

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
