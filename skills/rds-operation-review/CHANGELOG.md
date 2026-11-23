# Changelog

## [1.0.3] - 2026-11-19
- README: rewrote "Uploading to AWS DevOps Agent": Option A (recommended) adds the skill from the Skills Catalog; Option B uploads a zip for customization, with the zip command and expected structure (3 files). Agent types: On-demand (`CHAT`), the names the web app shows, instead of `Chat tasks` and `All agents`. "Connect additional observability sources" moved out of the upload steps into its own section.

## [1.0.2] - 2026-10-21
- README: corrected the agent types to the names the operator app shows (`Chat tasks`, `Incident triage`, `All agents`) and removed `Evaluation` and `On-demand`, which are not agent types.

## [1.0.1] - 2026-10-21
- Agent types now use the API values in `metadata.aws-devops-agent-skills.agent-types` (`CHAT`, `INCIDENT_RCA`, `INCIDENT_TRIAGE`), the field that sets which agents load the skill.
