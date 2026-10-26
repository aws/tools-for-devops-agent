# Changelog

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
