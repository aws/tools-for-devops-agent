# Changelog

## 1.0.4
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (1 file). Agent types: Incident Triage (`INCIDENT_TRIAGE`). Removed the GitHub import option, the GitHub-connection note, and the Asset API option.

## 1.0.3
- Added `aws-services` (`AWS Lambda, Amazon SQS, Amazon Aurora DSQL`) and `technical-domains` (`Operations, Observability`), so catalogs list the skill under the services its description names and under those domains.

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
