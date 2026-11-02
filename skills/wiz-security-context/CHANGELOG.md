# Changelog

## 1.2.0
- Now a partner-managed skill, offered by the Wiz connector (`connectors/wiz`) after a customer connects. Wiz maintains it.
- Also loads for incident triage (`INCIDENT_TRIAGE`).
- README: the prerequisites and setup now point to the Wiz connector.
- Added the standard partner-managed `evals/exemptions.json`. The existing eval definitions stay for maintainers.

## 1.1.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.1.0

- Clarified in Prerequisites that all `?toolset=devops` tools are read-only and the full toolset should be allowlisted
- Streamlined the SKILL.md description to focus on trigger conditions

## 1.0.0

- Initial version
