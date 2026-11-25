# Changelog

## 1.0.0
- Description: missing traces, spans or logs and observability setup go to `agentcore-observability-setup` (the 3-iteration run loaded this skill for `neg-ac-obs-transaction-search` 3 of 3 times).
- Output rules: mask both ARNs in a quoted `AccessDenied` message or log line, and name the check-id in short chat answers too (3-iteration run: one answer quoted the account, one gave no check-id).
- Evals: `ac-obs-transaction-search` is the negative `neg-ac-obs-transaction-search`, following the move of observability setup to `agentcore-observability-setup` (fork PR #5).
- Evals: `ac-iam-passrole` is removed (scored the same with and without the skill in two runs).
- Description: covers an agent that cannot call its model, and says to load the skill before delegating or searching AWS documentation (runs had delegated or gone to the docs instead). Evals: `ac-scp-explicit-deny` gives the error text; `ac-vpc-endpoint-missing` is removed (answered from AWS docs the same with or without the skill).
- The account-ID rule covers naming the account that was checked ("the connected account").
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Evals: `agentcore-runtime-cannot-invoke` targets the eval runtime whose execution role lacks `bedrock:InvokeModel` (LLM-AC-001). `bedrock-agent-empty-response` gives the alias, version and guardrail facts in the prompt, because new Bedrock Agents cannot be created in the eval account (maintenance mode).
- `related-skills.md` is a markdown link with its load condition (best-practices BP-05).
- Evals: `ac-runtime-container-arch` is removed (general knowledge, answered the same without the skill); check-id assertions are dropped from questions that name no account resource.

- PR #268 review item 5: `metadata.author` is the owner's GitHub username, `dimwael`.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: never calls `iam:SimulatePrincipalPolicy` or `s3:GetObject`; permission checks are labelled "evaluated from policy documents, not simulated", and each read gated by `EnableOpsaiBedrockAgentCore` states its fallback.
- PR #268 overlap review: observability setup and posture reviews are left to `agentcore-observability-setup` and `agentcore-ops-review` on `main`. LLM-AC-005, 006 and 007 are removed (ids retired, not reused); the description no longer mentions traces or a health review; both skills are named in `references/related-skills.md`.
- Initial release in this repository.
- Diagnoses Amazon Bedrock AgentCore and Bedrock Agents failures: invocation, gateways, action groups and live versions.
- Renamed from the earlier agent runtime skill.
- Works on its own: sibling skills are optional, with a fallback check per area in `references/related-skills.md`.
