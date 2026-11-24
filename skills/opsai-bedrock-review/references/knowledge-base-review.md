# Knowledge base and RAG review (LLM-KB)

Read this file before the first API call of a knowledge base or RAG question. Paths are relative to the skill root. The rules in `SKILL.md` (Output rule, Guardrails) apply throughout.

## Router
How to read each API and metric is in `references/collection-reference.md`. Load it with any row.

| Operator says | First read | Load |
|---|---|---|
| The knowledge base returns nothing | `ListIngestionJobs` for each data source (empty = never synced), not KB status | `references/checks-rag-knowledgebase.md` (LLM-KB-001), `references/api-quirks.md` |
| The ingestion job failed, documents are missing | Latest `GetIngestionJob` `status`, `statistics`, `failureReasons` | `references/checks-rag-knowledgebase.md` (LLM-KB-002) |
| RAG answers are out of date, sync is not running | `ListIngestionJobs` recency and sync automation | `references/checks-rag-knowledgebase.md` (LLM-KB-001, LLM-KB-010) |
| Which chunking strategy should I use | `GetDataSource` `vectorIngestionConfiguration.chunkingConfiguration` | `references/checks-rag-knowledgebase.md` (LLM-KB-003), `references/api-quirks.md` |
| Is my embedding model current | `GetKnowledgeBase` `embeddingModelArn` | `references/checks-rag-knowledgebase.md` (LLM-KB-004) |
| Is the data source or vector store encrypted | `GetDataSource` `serverSideEncryptionConfiguration`, the source bucket's `GetBucketEncryption`, and the vector store's own encryption and network policy (the KB response has no encryption key) | `references/checks-rag-knowledgebase.md` (LLM-KB-005, LLM-KB-006) |
| Retrieval quality is poor on codes, IDs, SKUs | Retrieval `overrideSearchType` (SEMANTIC vs HYBRID) | `references/checks-rag-knowledgebase.md` (LLM-KB-007) |
| Is this knowledge base unused | `ListAgents` → `ListAgentVersions` → `ListAgentKnowledgeBases`; application use is unverified unless CloudTrail records KB data events | `references/checks-rag-knowledgebase.md` (LLM-KB-008) |
| Has retrieval quality ever been measured | A `RagEvaluation` job whose `ragIdentifiers` include this KB (a `ModelEvaluation` job does not count) | `references/checks-rag-knowledgebase.md` (LLM-KB-009) |
| Ingestion or `Retrieve` fails with access denied or not authorized | Latest `GetIngestionJob` `failureReasons`, then the KB role's policy documents (`iam:SimulatePrincipalPolicy` is refused in the DevOps Agent runtime; `diagnosis-playbook.md` fallback), the role trust policy (`iam:GetRole`), `s3:GetBucketPolicy`, and SCPs (`organizations:ListPoliciesForTarget`, readable only from the management or a delegated-admin account) | `references/checks-rag-knowledgebase.md` (LLM-KB-011), `references/api-quirks.md` |
| Ingestion is slow or `Retrieve` is throttled | `InvocationThrottles` for the embedding model, then `servicequotas:GetServiceQuota` (service-code `bedrock`) | `references/checks-rag-knowledgebase.md` (LLM-KB-012), `references/api-quirks.md` |
| Ingestion or `Retrieve` just started failing, is it AWS or us | `health:DescribeEvents` for an active Bedrock event in the region, before any customer fix | `references/collection-reference.md` (`health:DescribeEvents`), `references/checks-rag-knowledgebase.md` (LLM-KB-011, LLM-KB-012) |
| Vector-store or retrieval metric looks like zero | `AWS/AOSS` and retrieval signals, no-datapoints vs measured zero | `references/metrics-and-logs.md` |

## The RAG Health Review
This is the main procedure. The exact calls, fields and decision rules for every step are in
`references/rag-review-playbook.md`; follow it. Where it is more specific than a shared reference, the
playbook governs.

For a **full review**, run all ten steps in order. For a **focused question**, run the steps it needs
plus Steps 1–2 (they identify the KB and data sources), and list the steps you did not run under
**Scope not covered**. Never present a conclusion from a step you did not run.

- [ ] Step 1: `ListKnowledgeBases`, then `GetKnowledgeBase` for embedding model and `storageConfiguration` (store type and id). The KB response has no encryption key.
- [ ] Step 2: `ListDataSources`, then `GetDataSource` for `chunkingConfiguration`, `serverSideEncryptionConfiguration`, bucket and inclusion prefixes.
- [ ] Step 3: `ListIngestionJobs` sorted `STARTED_AT` `DESCENDING`, all pages. An **empty list means never synced** (LLM-KB-001, HIGH).
- [ ] Step 4: For the latest terminal job (`COMPLETE` / `FAILED` / `STOPPED`), read `status`, the `numberOf…` statistics and `failureReasons` (LLM-KB-002).
    - **Service-vs-customer transient verdict first.** On a `FAILED` ingestion job, before prescribing any customer fix, decide whether the fault is **service-side** (regional capacity / a Bedrock service event — check `health:DescribeEvents` for an active event in the region) or **customer-side** (config / permissions / quota). Only prescribe a customer fix once a service event is ruled out; if a service event is active, report it as transient and advise retry rather than a config change.
    - If `failureReasons` indicate an **access/authorization** denial (not a data problem), run **LLM-KB-011** (simulate the execution role, inspect trust/bucket policy and SCPs) and return the exact missing statement.
    - If ingestion is **slow or throttled** rather than a hard data failure, run **LLM-KB-012**: `servicequotas:GetServiceQuota` (service-code `bedrock`) for the embedding-model requests-per-minute quota (embedding models are throttled by requests per minute, not tokens per minute) and the KB quotas, and correlate CloudWatch `InvocationThrottles` and `Invocations` on the embedding model over the window; report `workload-specific`/`INFO` where AWS publishes no number.
- [ ] Step 5: Decide **populated** from a `COMPLETE` job with `numberOfNewDocumentsIndexed` > 0. A later no-change sync (0 new, 0 modified) is not emptiness. If populated but answers have no sources, follow the playbook's candidate-cause table; never diagnose by elimination.
- [ ] Step 6: Chunking (LLM-KB-003), embedding-model currency (LLM-KB-004), and staleness: newest S3 `LastModified` under the prefix vs the latest `COMPLETE` job's `updatedAt`.
- [ ] Step 7: Encryption of the data source and transient storage (LLM-KB-005) and of the vector store, plus its network policy (LLM-KB-006). Keep field absent / AWS-owned key / CMK apart. Access & authorization (LLM-KB-011) when ingestion or `Retrieve` is denied: `iam:SimulatePrincipalPolicy` on the KB / data-source execution role for `s3:GetObject` / `s3:ListBucket` and `kms:Decrypt`, the role trust policy for `bedrock.amazonaws.com`, and `s3:GetBucketPolicy` for a cross-account bucket policy; SCP reads (`organizations:ListPoliciesForTarget` / `DescribePolicy`) work only from the management or a delegated-admin account. On a denial, return the exact missing statement with the account segment masked.
- [ ] Step 8: Search type (LLM-KB-007, INFO) and, only if needed and allowed, one bounded `Retrieve` probe (counts, URIs, scores).
    - If a `Retrieve` / `RetrieveAndGenerate` call (the probe or the user's) fails or is throttled, apply the **service-vs-customer transient verdict** first (`health:DescribeEvents` for an active Bedrock event in the Region), then classify: `AccessDenied` → **LLM-KB-011**; `ThrottlingException` or quota pressure on retrieval or the embedding model → **LLM-KB-012**. Report chunk counts, sources and scores only, never chunk content.
- [ ] Step 9: `ListAgents` → `ListAgentVersions` → `ListAgentKnowledgeBases`, and whether CloudTrail records KB data events (LLM-KB-008).
- [ ] Step 10: Sync automation (LLM-KB-010, INFO) and whether a `RagEvaluation` job covers this KB (LLM-KB-009); running the evaluation is output-quality work (follow *Related skills (optional)* in `SKILL.md`).

**Always land a result in a single turn.** Each step is best-effort: if an API is denied, a list is
empty for an unknown reason, or a region does not support a feature, record that signal as
`unavailable` or `not checked` and move on. A review built on the signals you could read plus a clear
disclosure of what you skipped is a correct and useful answer; an exhaustive hunt that never produces
a response is not.

The decisive signal for the most common complaint ("returns nothing") is **ingestion-job history, not
KB status** — Step 3 and Step 4 are where you resolve it.

## Before You Present — Validate Your Own Output
A confident "your KB is healthy" when it is actually empty is worse than a slow answer. Before you
present a result, re-check it against this list. Treat it as a gate, not a suggestion.

- [ ] For every KB called "populated/healthy", a `COMPLETE` job with `numberOfNewDocumentsIndexed`
  > 0 was actually observed and its job id is cited — not merely `GetKnowledgeBase` `status: ACTIVE`.
- [ ] Any KB with an **empty `ListIngestionJobs`** (all pages) is reported as **never synced /
  EMPTY** (LLM-KB-001, HIGH), not as a healthy ACTIVE resource.
- [ ] Every finding carries a matching `LLM-KB-0NN` check-id with the catalog severity, and that id
  corresponds to what was actually observed (not a near-miss id reused for convenience).
- [ ] Every cited value was **actually observed, not inferred** — distinguish "measured zero failed
  docs" from "no job to read" (`references/api-quirks.md`).
- [ ] Encryption claims say which of field absent / AWS-owned key / CMK applies and name the field
  read. Nothing encrypted with an AWS-owned key or SSE-S3 is called "unencrypted".
- [ ] LLM-KB-008 says what was checked and that application use is unverified unless CloudTrail data
  events were read; LLM-KB-009 quotes `applicationType` verbatim.
- [ ] **No retrieved chunk text is reproduced anywhere** in the output — only chunk counts, source
  identifiers, and relevance scores.
- [ ] Scan the draft for any 12-digit number. No raw AWS account ID appears anywhere; ARNs have the
  account segment masked.
- [ ] For an LLM-KB-011 finding, any policy/trust/bucket/SCP statement quoted as evidence has its account segment masked and no secret-shaped condition value is echoed.
- [ ] Thresholds marked `workload-specific` (003, 007, 010) are reported as `INFO`, not promoted.
- [ ] Scope you did not cover (regions, KBs, steps not run, permission-blocked calls) is
  **disclosed**, not silently dropped.
- [ ] When a full report is requested, the output follows `assets/rag-health-report-template.md`.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Check Family — LLM-KB
Full detection rules, remediations, and citations: `references/checks-rag-knowledgebase.md`.

| check-id | pillar | severity | What it catches |
|---|---|---|---|
| LLM-KB-001 | Operational Excellence | HIGH | `ListIngestionJobs` empty (all pages) / no `COMPLETE` job ever indexed documents — vector store empty, retrieval returns nothing. |
| LLM-KB-002 | Reliability | HIGH | Latest terminal job `FAILED` or `STOPPED`, or `numberOfDocumentsFailed` > 0 — content stale/partial. |
| LLM-KB-003 | Performance | INFO | Chunking strategy may not fit the documents (default is about 300 tokens). `workload-specific`. |
| LLM-KB-004 | Performance | MEDIUM | Embedding model `LEGACY` or no longer supported for knowledge bases. Never fires on `titan-embed-text-v2:0`. |
| LLM-KB-005 | Security | HIGH | Neither the data source (`serverSideEncryptionConfiguration`) nor the source bucket uses a customer managed key. |
| LLM-KB-006 | Security | HIGH | Vector store uses an AWS-owned key rather than a CMK, and/or its network policy allows public access. |
| LLM-KB-007 | Performance | INFO | Exact-match terms (codes, IDs, SKUs) where hybrid search is supported but use is unconfirmed. `workload-specific`. |
| LLM-KB-008 | Operational Excellence | LOW | KB not attached to any agent; application use unverified unless CloudTrail data events are recorded. |
| LLM-KB-009 | Quality & Evaluation | MEDIUM | No `RagEvaluation` job covers this KB — retrieval relevance unmeasured (running an evaluation: see *Related skills (optional)*). |
| LLM-KB-010 | Operational Excellence | INFO | Sync appears manual for a changing corpus, from a named signal. `workload-specific`. |
| LLM-KB-011 | Security | HIGH | Ingestion or `Retrieve` fails for a permissions reason — KB role can't `s3:GetObject`/`ListBucket` the data source, can't `kms:Decrypt` the CMK, trust policy omits `bedrock.amazonaws.com`, or a cross-account bucket policy / SCP explicit-deny blocks it. Returns the exact missing statement. |
| LLM-KB-012 | Reliability | MEDIUM | Ingestion slow/failing or `Retrieve` throttled because an embedding-model invocation quota or a KB/Retrieve request-rate quota is hit / has no burst headroom; MEDIUM needs observed throttles, headroom alone is INFO. |

Collection APIs for each check: `references/rag-review-playbook.md` (governs) and
`references/collection-reference.md`. Underlying vector-store and retrieval signals:
`references/metrics-and-logs.md`.

## Common wrong answers
- "`GetKnowledgeBase` returns `status: ACTIVE`, so the KB is ready and populated." ACTIVE only means the resource and vector-index wiring are valid; a KB with no completed ingestion job is EMPTY and a RAG query against it silently returns nothing. Verify ingestion-job history, never KB status (`references/api-quirks.md` §8).
- "`ListIngestionJobs` is empty, so there is nothing to report." An empty job list means the data source was never synced, which is LLM-KB-001 (HIGH), not a healthy or neutral state. Report it as never synced / EMPTY.
- "The chunking configuration is absent, so each document is one chunk." An unset `chunkingConfiguration` means the service default (about 300 tokens, sentence boundaries preserved); `NONE` is the setting that keeps one chunk per document. Judge fit against the observed documents and report it at INFO (LLM-KB-003, `references/rag-review-playbook.md`).
- "The KB is in `ListKnowledgeBases`, so it is attached and in use." Listed is not attached. A KB can be listed yet referenced by no agent or application. Confirm via `ListAgentKnowledgeBases` before treating it as in use, and against LLM-KB-008 before calling it orphaned.
- "The vector-store metric shows no datapoints, so the measured value is zero." No datapoints usually means no traffic or the metric was not emitted in that window, not a measured zero. Distinguish "zero measured" from "nothing reported" (`references/api-quirks.md` §10).
- "`SimulatePrincipalPolicy` came back clean, so authorization is fine." The denial may come from a resource policy (cross-account S3 bucket policy) or an Organizations SCP explicit deny, which identity-policy simulation does not evaluate. A clean simulation does not clear LLM-KB-011; read the bucket policy and SCPs and the role trust policy before ruling it out (`references/api-quirks.md`).
- "`ThrottlingException` means we hit our quota." Throttling can be burst pressure with headroom left, or a service-side event. Correlate sustained `InvocationThrottles` with the applied quota and rule out a Bedrock service event before firing LLM-KB-012 (`references/api-quirks.md`).
- "The ingestion job `FAILED` or `Retrieve` errored, so fix the customer config." Decide service-side versus customer-side first. Check `health:DescribeEvents` for an active Bedrock event in the region; if one is active, report it as transient and advise retry rather than a config change. Only then classify an access denial as LLM-KB-011 or throttling as LLM-KB-012 (`references/collection-reference.md`, `references/api-quirks.md`).
- "I measured zero failed documents." If there was no completed job to read, you measured nothing, not zero. Distinguish "measured zero failed docs" from "no job to read" before reporting ingestion as clean (`references/api-quirks.md`).

## Severity Definitions — LLM-KB
| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Reserved; no LLM-KB catalog check carries it | 24–48 hours |
| **HIGH** | Retrieval empty or partial, or a serious security exposure (never-synced or failed ingestion, no CMK, public vector store) | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice (legacy embedding model, unmeasured relevance) | Within 30 days |
| **LOW** | Minor hardening (KB not attached to any agent) | When convenient |
| **INFO** | Observation with no AWS-published threshold (chunking fit, hybrid search, sync cadence) | N/A — document / monitor |

SLAs are operational guidance (**derived**), not AWS-published commitments.

## Error Handling
Before interpreting any response, consult `references/api-quirks.md` — it enumerates the misleading
responses that cause false positives and false negatives in a RAG review. Where it conflicts with
`references/rag-review-playbook.md`, the playbook governs.

**The highest-value trap — read this first:** a Knowledge Base with `status: ACTIVE` and **no completed
ingestion job is EMPTY.** `GetKnowledgeBase` returning `ACTIVE` only means the resource and
vector-index wiring are valid — it does **not** mean any data was ingested. **ACTIVE does not mean
populated**, and a RAG query against such a KB **silently returns nothing** (no error, just empty).
You must verify ingestion-job history, never KB status, before calling a KB healthy
(`references/api-quirks.md` §8).

Corollary: an **empty `ListIngestionJobs` means the data source was never synced** — LLM-KB-001,
**HIGH** — *not* a healthy or neutral state. Do not read an empty job list as "nothing to report".
The reverse also holds: when ingestion history shows indexed documents, say the KB is populated, even
if the user believes it is empty.

Other traps:

- **Unset chunking configuration** — when `chunkingConfiguration` is absent, the service chunks at
  about 300 tokens, preserving sentence boundaries. It is not "no chunking" (`NONE` is that). State
  the default; do not guess a strategy (LLM-KB-003, INFO). This overrides `api-quirks.md` §13.
- **Listed ≠ attached** — a KB in `ListKnowledgeBases` is not necessarily referenced by any agent;
  confirm via `ListAgentKnowledgeBases` for every agent version before LLM-KB-008.
- **An evaluation job exists ≠ retrieval measured** — only `applicationType` `RagEvaluation` counts
  for LLM-KB-009.
- **CloudWatch "no datapoints" ≠ zero** (§10) — underlying vector store (`AWS/AOSS`) or retrieval
  signals with no datapoints usually mean no traffic, not a measured zero.
- **`AccessDenied` on ingestion/retrieval ≠ a broken identity policy** (§18) — a clean
  `iam:SimulatePrincipalPolicy` does not clear LLM-KB-011; a cross-account bucket policy or an SCP
  explicit deny needs `s3:GetBucketPolicy` / `organizations:*` too.
- **`ThrottlingException` ≠ quota exhausted** (§19) — correlate `servicequotas:GetServiceQuota` against
  sustained throttling and rule out a service event before firing LLM-KB-012.

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read (masking the account), continue with the rest, and list the gap — never guess. The
playbook lists calls the DevOps Agent's standard policy commonly denies (`GetIngestionJob`,
`Retrieve`, CloudTrail). On a **region unsupported for a feature**, record it as a disclosed
assumption, not a finding. On **throttling of describe/list calls**, back off and paginate. On
**ambiguous scope**, ask or default to the caller's current region and say so.

## AWS documentation

- [Knowledge Bases — how it works](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-how-it-works.html)
- [Set up a knowledge base and vector store](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)
- [Sync / ingest a data source](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)
- [Customize ingestion (chunking default)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-customize-ingestion.html)
- [How content chunking works](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html)
- [Supported embedding models](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-supported.html)
- [Encryption of knowledge base resources](https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-kb.html)
- [Test and configure retrieval (hybrid search)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html)
- [Evaluate a knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html)
- [Knowledge base setup / service-role permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html)
- [Service quotas for Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html)
- [Monitoring Bedrock with CloudWatch](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)
