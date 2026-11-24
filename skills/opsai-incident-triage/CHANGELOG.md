# Changelog

## 1.0.0

- PR #268 review item 1 (IAM reads and action names):
  - IAM: new `EnableOpsaiIncidentTriage` template parameter (`bedrock:GetFoundationModelAvailability`, `bedrock:GetIngestionJob`, AgentCore status reads); `bedrock-agent:` names corrected to `bedrock:`; `iam:SimulatePrincipalPolicy` replaced by a static policy read.
- Initial release in this repository.
- Triages live model-call failures (errors, throttling, latency) and rules whether the fault is the provider, infrastructure or app.
- Renamed from the earlier incident triage skill. `Remediation owner` now names an owner track from `references/related-skills.md` instead of a skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
