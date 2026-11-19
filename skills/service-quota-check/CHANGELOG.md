# Changelog

## 1.0.3
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (2 files). Agent types: On-demand (`CHAT`), Incident RCA (`INCIDENT_RCA`). Removed the GitHub import and Asset API options. The Agent Types list says **On-demand** instead of **Chat tasks**.

## 1.0.2
- `metadata.author` is the contributor's GitHub username, `yprikhodko`, so catalogs link to their profile.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0

- Initial version
- Quota value retrieval via get-service-quota and list-service-quotas
- Utilization calculation using CloudWatch UsageMetric or resource counting
- Risk assessment with 85% threshold for triggering increase recommendations
- Automated quota increase request via request-service-quota-increase API
- Support case recommendation for non-adjustable quotas
- Duplicate request detection via pending request check
- Common quota codes reference for frequently checked services
