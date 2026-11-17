# LLMOps RAG & Knowledge Base Health Report

Fill in every `<placeholder>`. Delete a row only when it genuinely does not apply, and
when you do, say why in **Scope not covered**. Never leave a placeholder unresolved in a
delivered report. **Never paste retrieved chunk text into this report** — counts, sources,
and scores only.

## Scope

- **Region examined:** `<region>`
- **Knowledge bases in scope:** `<kb-ids / count>`
- **Account under review:** `<alias — never the raw 12-digit id>`
- **Time of review:** `<ts>` (`<tz>`)

## Knowledge Base inventory

| KB (id/alias) | status | populated? | embedding model | vector store | attached to |
|---|---|---|---|---|---|
| `<kb-id>` | `<ACTIVE/...>` | `<yes: job <id> COMPLETE, numberOfNewDocumentsIndexed N / NO: never synced>` | `<model id / lifecycle status>` | `<type / AWS-owned or CMK / public or private>` | `<agent id(s) / no agent; application use unverified>` |

> `populated?` MUST be decided by a `COMPLETE` ingestion job with non-zero documents
> indexed — **not** by `status: ACTIVE`. ACTIVE with no completed job = EMPTY.

## Ingestion evidence

| KB / data source | ListIngestionJobs (all pages) | latest terminal job id / status / finished (`updatedAt`) | `numberOfDocumentsScanned` / `numberOfNewDocumentsIndexed` / `numberOfModifiedDocumentsIndexed` / `numberOfDocumentsFailed` | failureReasons |
|---|---|---|---|---|
| `<kb-id>/<ds-id>` | `<N jobs / EMPTY = never synced>` | `<job-id> / <COMPLETE/FAILED/STOPPED / none> / <ts>` | `<n / n / n / n>` | `<reason / none / not readable>` |

> An **empty** `ListIngestionJobs` is **never synced** → LLM-KB-001, HIGH.
> Write `no job to read` (not `0`) when there is no job. A later sync with 0 new and 0 modified
> documents means nothing changed, not an empty KB.

## Freshness and encryption evidence

| Item | Field read | Observed |
|---|---|---|
| Newest source object vs last sync | S3 `LastModified` under the inclusion prefix; job `updatedAt` | `<ts> vs <ts> → current / stale / undetermined>` |
| Data source transient storage | `serverSideEncryptionConfiguration.kmsKeyArn` | `<absent = AWS-owned key / CMK>` |
| Source bucket | `GetBucketEncryption` `SSEAlgorithm` | `<AES256 = SSE-S3 / aws:kms + key>` |
| Vector store at rest | `<kmsKeyArn / AWSOwnedKey / StorageEncrypted>` | `<AWS-owned / CMK / not checkable>` |
| Vector store network | `<AllowFromPublic / PubliclyAccessible / VPCOptions>` | `<public / private / not checkable>` |

## Findings

| check-id | severity | observed value | remediation |
|---|---|---|---|
| `<LLM-KB-0NN>` | `<HIGH/MEDIUM/LOW/INFO (catalog)>` | `<concrete value that triggered it>` | `<exact read-only-recommended fix / command>` |
| `<LLM-KB-0NN>` | `<...>` | `<...>` | `<...>` |

> No freelance findings — every row cites an `LLM-KB` catalog check-id and that check's
> severity. Thresholds marked `workload-specific` are reported as `INFO`.

## Recommended remediation commands (for the operator to run)

The skill is read-only and does **not** run these. Where a sync is the fix:

```
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <kb-id> \
  --data-source-id <ds-id>
```

Then confirm a `COMPLETE` job with non-zero documents indexed via `get-ingestion-job`.

## Retrieval test (if run)

- Query `<query>`: `<N>` results; `<s3-uri>` score `<score>` (one line per result).

> Counts, sources, and scores only. **Do not reproduce chunk text**, even when asked.

## Scope not covered

- Steps not run (focused question): `<steps / none>`
- Regions skipped: `<regions / none>`
- KBs / data sources skipped: `<ids / none>`
- Checks blocked by permissions: `<API + resource you could not read / none>`
- Region-unsupported features: `<feature / none>`
- Other disclosed assumptions: `<budget bound, etc. / none>`
