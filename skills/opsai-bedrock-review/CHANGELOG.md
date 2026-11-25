# Changelog

## 1.0.0
- LLM-INV-002: the profile-only rule (`inferenceTypesSupported` = `INFERENCE_PROFILE` means every bare-ID call fails) is in `SKILL.md` guardrail 6 and the pre-answer checklist, not only the catalog (a 2026-11-25 run raised LLM-INV-002 but missed it).
- Evals: `stale-rag-ingestion-and-chunking` names the knowledge base (the account has 18, and both variants ended by asking which one).
- Description: load the skill before delegating (a 2026-11-25 run handed the bare-ID account scan for `bc-ip-required` to a sub-agent without loading it).
- The vector-store check uses CloudTrail `DeleteIndex` / `DeleteVectorBucket` events: DevOps Agent's tool policy blocks the `s3vectors` `GetIndex` and `ListIndexes` reads (38 blocked calls in the 2026-11-25 run). `s3vectors:GetIndex` is no longer added to `EnableOpsaiBedrockReview`.
- Description: guardrail questions go to opsai-bedrock-security; how-to questions included (one run skipped the skill for `access-denied-iam-vs-scp`, one loaded it for `neg-guardrail-blocks-correct-answers`).
- Evals: `access-denied-iam-vs-scp` no longer requires `iam:SimulatePrincipalPolicy`, which the skill does not call; `kb-active-but-empty` is removed (duplicate of `kb-never-synced`).
- Description: hands AccessDenied that began with a new guardrail to opsai-bedrock-security. Evals: `bc-ip-required` also asks whether other callers make the same bare-ID mistake.
- LLM-INV-002 reads `inferenceTypesSupported` first: bare-ID calls to a model that supports only inference profiles are reported as failing requests, not as a missed optimisation.
- Evals: the 12-digit account-ID regex ignores the documentation example IDs `123456789012` and `111122223333`.
- Eval run 2026-11-24: the knowledge base review confirms the vector store itself exists (`s3vectors:GetIndex`, or `aoss:BatchGetCollection`) when retrieval fails, since a KB stays ACTIVE after its index is deleted. `EnableOpsaiBedrockReview` adds `s3vectors:GetIndex`.
- `related-skills.md` is a markdown link with its load condition (best-practices BP-05).
- Evals: `bc-ip-required` asks the agent to check the account; check-id assertions are dropped from the three questions that name no account resource.

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
