# Changelog

## 1.0.0

- PR #268 review item 5: `metadata.author` is the owner's GitHub username, `dimwael`.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: never calls `iam:SimulatePrincipalPolicy` or `s3:GetObject`; permission checks are labelled "evaluated from policy documents, not simulated", and each read gated by `EnableOpsaiBedrockAgentCore` states its fallback.
- PR #268 overlap review: observability setup and posture reviews are left to `agentcore-observability-setup` and `agentcore-ops-review` on `main`. LLM-AC-005, 006 and 007 are removed (ids retired, not reused); the description no longer mentions traces or a health review; both skills are named in `references/related-skills.md`.
- Initial release in this repository.
- Diagnoses Amazon Bedrock AgentCore and Bedrock Agents failures: invocation, gateways, action groups and live versions.
- Renamed from the earlier agent runtime skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
