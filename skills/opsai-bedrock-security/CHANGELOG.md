# Changelog

## 1.0.0
- Description: covers pasted guardrail configs and how-to questions (two runs skipped the skill, one delegating the SCP report to sub-agents).
- Description: covers AccessDenied that began when a guardrail was added (missing `bedrock:ApplyGuardrail`). It had excluded every AccessDenied, so the agent skipped the skill for `gr-no-apply`.
- The account-ID rule covers naming the account that was checked. Evals: `bpa-dormant-keys` accepts that the eval account has no dormant key and checks that no active key is recommended for deletion.
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Eval run 2026-11-24: LLM-BPA-006 remediation is a staged decommission (deactivate, watch, then delete) instead of immediate deletion.
- Evals: `grounding-score-far-below-threshold` is removed (scored the same with and without the skill); `gr-no-apply` asks the agent to check the account; check-id assertions are dropped from questions that name no account resource.

- PR #268 review item 3 (evals): `grounding-score-near-threshold-invented-fact` is removed; it is reasoning over text given in the prompt and scored 7/7 with and without the skill. `guardrail-latency-streaming` asserts the trace fields `guardrailProcessingLatency` and `guardrailCoverage`; `tool-results-not-evaluated` asserts ruling out the ordinary zero-intervention causes and naming `ApplyGuardrail` for the application to call.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: the reads `AIDevOpsAgentAccessPolicy` lacks come from the `EnableOpsaiBedrockSecurity` template parameter (now also the AgentCore status reads); invoke actions name `bedrock:InvokeModel` / `InvokeModelWithResponseStream`, which authorize Converse / ConverseStream.
  - SCP assets: removed the Converse and ConverseStream entries, which are not IAM actions; `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`, already in the statements, authorize those API calls.
- Initial version, merged from the earlier Bedrock permissions audit skill (LLM-BPA, long-lived
  credentials that can invoke Amazon Bedrock) and guardrails skill (LLM-GRD, Bedrock Guardrails posture
  and troubleshooting). Both check families and their catalogs are kept unchanged.
- `SKILL.md` is a short entry point with the shared Output rule and guardrails; each area's operating
  rules and procedure live in `references/credential-audit.md` and `references/guardrails-review.md`,
  with that area's reference files under `references/` and `references/`.
- Works on its own: sibling skills are optional, with a fallback check per area in
  `references/related-skills.md`.
