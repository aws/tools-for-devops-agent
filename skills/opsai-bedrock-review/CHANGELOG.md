# Changelog

## 1.0.0

- PR #268 review item 3 (evals): `kb-retrieval-throttling-quota` asks for one reply with no status message first (both runs had ended on "waiting for the scan"), asserts the embedding model's requests-per-minute quota and `LLM-KB-012`, and its expected output no longer names the non-existent `EstimatedQuotaConsumption` metric.
- PR #268 review item 1 (IAM reads and action names):
  - IAM: no `bedrock:Retrieve` probe (retrieval questions use ingestion-job statistics), no `iam:SimulatePrincipalPolicy` (policies evaluated statically); `EnableOpsaiBedrockReview` also grants the AgentCore status reads.
  - Report template: the SimulatePrincipalPolicy example now reads "not called → evaluated from policy documents, not simulated".
- Initial version, merged from the earlier Bedrock configuration skill (LLM-INV, model access and
  configuration) and RAG knowledge base skill (LLM-KB). Both check families and their catalogs
  are kept unchanged.
- `SKILL.md` is a short entry point that picks the area; each area's procedure lives in
  `references/model-access-review.md` and `references/knowledge-base-review.md`.
- The two copies of `api-quirks.md`, `collection-reference.md` and `metrics-and-logs.md` are merged into
  one each; the knowledge-base quirks are §18 and §19.
- Works on its own: sibling skills are optional, with a fallback check per area in
  `references/related-skills.md`.
- The `description` says the skill is not for Bedrock spend or bills (`opsai-capacity-cost`) or for who
  holds keys that can call Bedrock (`opsai-bedrock-security`), even when those skills aren't installed.
