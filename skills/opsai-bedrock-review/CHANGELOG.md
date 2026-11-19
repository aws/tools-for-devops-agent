# Changelog

## 1.0.0

- Initial version, merged from `llmops-bedrock-configuration` (LLM-INV, model access and configuration)
  and `llmops-rag-knowledge` (LLM-KB, knowledge bases and RAG). Both check families and their catalogs
  are kept unchanged.
- `SKILL.md` is a short entry point that picks the area; each area's procedure lives in
  `references/model-access-review.md` and `references/knowledge-base-review.md`.
- The two copies of `api-quirks.md`, `collection-reference.md` and `metrics-and-logs.md` are merged into
  one each; the knowledge-base quirks are §18 and §19.
- Works on its own: sibling skills are optional, with a fallback check per area in
  `references/related-skills.md`.
