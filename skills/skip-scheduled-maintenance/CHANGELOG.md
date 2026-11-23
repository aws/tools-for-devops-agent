# Changelog

## 1.0.4
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (1 file). Agent types: Incident Triage (`INCIDENT_TRIAGE`). The intro notes that the catalog copy has the sample's hardcoded window, so adapt `SKILL.md` and use Option B. Removed the GitHub import and Asset API options.

## 1.0.3
- Added `technical-domains` (`Operations`), so catalogs list the skill under Operations. It names no AWS service, so it has no `aws-services`.

## 1.0.2
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## 1.0.1
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.

## 1.0.0

- Initial version
- Skip MEDIUM and LOW severity incidents during maintenance window (2025-03-15 02:00–06:00 UTC)
- Preserve investigation for HIGH and CRITICAL severity incidents
