# Changelog

## 1.0.0

- PR #268 review item 5: `metadata.author` is the owner's GitHub username, `dimwael`.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: never calls `iam:SimulatePrincipalPolicy` or `s3:GetObject`; permission checks are labelled "evaluated from policy documents, not simulated", and each read gated by `EnableOpsaiBedrockAgentCore` states its fallback.
- Initial release in this repository.
- Reviews Amazon Bedrock AgentCore and Bedrock Agents health: invocation, gateways, action groups, traces and live versions.
- Renamed from the earlier agent runtime skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
