# Changelog

## 1.0.1

- PR #268 review item 1 (IAM reads and action names):
  - IAM: the reads `AIDevOpsAgentAccessPolicy` lacks come from the `EnableOpsaiBedrockSecurity` template parameter (now also the AgentCore status reads); invoke actions name `bedrock:InvokeModel` / `InvokeModelWithResponseStream`, which authorize Converse / ConverseStream.
  - SCP assets: removed the Converse and ConverseStream entries, which are not IAM actions; `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`, already in the statements, authorize those API calls.

## 1.0.0

- Initial version, merged from the earlier Bedrock permissions audit skill (LLM-BPA, long-lived
  credentials that can invoke Amazon Bedrock) and guardrails skill (LLM-GRD, Bedrock Guardrails posture
  and troubleshooting). Both check families and their catalogs are kept unchanged.
- `SKILL.md` is a short entry point with the shared Output rule and guardrails; each area's operating
  rules and procedure live in `references/credential-audit.md` and `references/guardrails-review.md`,
  with that area's reference files under `references/` and `references/`.
- Works on its own: sibling skills are optional, with a fallback check per area in
  `references/related-skills.md`.
