# Changelog

## 1.0.2
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (3 files). Agent types: On-demand (`CHAT`), Incident RCA (`INCIDENT_RCA`). Removed the GitHub import and Asset API options. The Agent Types list says **On-demand** instead of **Chat tasks**.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0

- Initial version
