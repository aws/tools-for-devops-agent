# Changelog

## 1.0.0

- Initial version, merged from `llmops-bedrock-permissions-audit` (LLM-BPA, long-lived credentials
  that can invoke Amazon Bedrock) and `llmops-guardrails` (LLM-GRD, Bedrock Guardrails posture and
  troubleshooting). Both check families and their catalogs are kept unchanged.
- `SKILL.md` is a short entry point with the shared Output rule and guardrails; each area's operating
  rules and procedure live in `references/credential-audit.md` and `references/guardrails-review.md`,
  with that area's reference files under `references/credential-audit/` and `references/guardrails/`.
- Works on its own: sibling skills are optional, with a fallback check per area in
  `references/related-skills.md`.
- One inline IAM policy (`opsai-bedrock-security-readonly`) now covers both areas.
