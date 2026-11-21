# RAG Review Playbook

Per-step method for the RAG Health Review in `SKILL.md`: the exact read-only calls, the fields to
read, and how to decide each LLM-KB check. This file belongs to this skill only. Where it is more
specific than a shared reference (`collection-reference.md`, `api-quirks.md`, `metrics-and-logs.md`),
**this file governs**. Known conflicts it overrides:

- `collection-reference.md` lists a "KMS config" for `GetKnowledgeBase`. The `KnowledgeBase`
  response has no KMS field. Encryption is read from the data source and the vector store (Step 7).
- `collection-reference.md` says the data-plane clients are not used. This skill may run one
  bounded `Retrieve` probe (Step 8). It never calls `RetrieveAndGenerate`.
- `api-quirks.md` §13 says an unset chunking configuration "may be no chunking". It is not: the
  service then chunks at about 300 tokens (Step 6).

All calls are read-only. Never call `StartIngestionJob`, `StopIngestionJob`, `UpdateDataSource`,
`CreateSecurityPolicy`, `UpdateSecurityPolicy` or any other create/update/delete/start/stop API.

## Step 1 — knowledge bases

- `bedrock-agent list-knowledge-bases` (follow `nextToken`), then `get-knowledge-base` per KB.
- Read `status`, `knowledgeBaseConfiguration.vectorKnowledgeBaseConfiguration.embeddingModelArn`,
  `storageConfiguration.type` (`OPENSEARCH_SERVERLESS`, `OPENSEARCH_MANAGED_CLUSTER`, `RDS`,
  `PINECONE`, `REDIS_ENTERPRISE_CLOUD`, `MONGO_DB_ATLAS`, `NEPTUNE_ANALYTICS`, `S3_VECTORS`) and the
  store identifier (for AOSS, `opensearchServerlessConfiguration.collectionArn` and `fieldMapping`).
- The KB response carries no encryption key. Do not report one from it.

## Step 2 — data sources

- `list-data-sources` (follow `nextToken`), then `get-data-source` per data source.
- Read `vectorIngestionConfiguration.chunkingConfiguration` (state "not set" when absent),
  `serverSideEncryptionConfiguration.kmsKeyArn` (state "absent" when the object is missing),
  `dataSourceConfiguration.s3Configuration.bucketArn` and `inclusionPrefixes`, `dataDeletionPolicy`.

## Step 3 — ingestion history (LLM-KB-001)

- `list-ingestion-jobs --knowledge-base-id <kb> --data-source-id <ds>
  --sort-by attribute=STARTED_AT,order=DESCENDING`, following `nextToken` until it is absent. Do not
  rely on the default order. Report the total job count.
- Empty list after full pagination → **never synced** → LLM-KB-001, **HIGH**. Do not call it
  healthy or neutral.

## Step 4 — latest job (LLM-KB-002)

- The **latest terminal job** is the first job in the sorted list whose `status` is `COMPLETE`,
  `FAILED` or `STOPPED`. A newer `STARTING` / `IN_PROGRESS` / `STOPPING` job is reported as
  "sync in progress", not judged.
- Statistics are on each job summary and on `get-ingestion-job`: `numberOfDocumentsScanned`,
  `numberOfNewDocumentsIndexed`, `numberOfModifiedDocumentsIndexed`, `numberOfDocumentsDeleted`,
  `numberOfDocumentsFailed`, `numberOfDocumentsSkipped`, `numberOfMetadataDocumentsScanned`,
  `numberOfMetadataDocumentsModified`. Quote them by these names.
- `failureReasons` is only on `get-ingestion-job`. If that call is denied, say so and keep the
  verdict on the summary statistics.
- LLM-KB-002 fires when the latest terminal job is `FAILED` or `STOPPED`, or its
  `numberOfDocumentsFailed` > 0. Per-document failure detail lives in the KB's vended
  `APPLICATION_LOGS` if log delivery is configured (`logs describe-delivery-sources`); say whether it
  is configured.

## Step 5 — populated or empty

- **Populated** = at least one `COMPLETE` job with `numberOfNewDocumentsIndexed` > 0, and no later
  job deleted everything (`numberOfDocumentsDeleted` equal to everything indexed).
- Syncs are incremental. A later `COMPLETE` job with `numberOfNewDocumentsIndexed` 0 and
  `numberOfModifiedDocumentsIndexed` 0 means **nothing changed**, not that the KB is empty.
- Cite the job id, its status and the counter you used.

### Populated, but the user sees answers with no sources

Say plainly that the KB is populated and that LLM-KB-001 does not apply. Then list only causes you
can attach a signal to, each labelled **unverified** until its signal is read. Never conclude a cause
because the others were ruled out ("diagnosis by elimination").

| Candidate cause | Signal that would confirm it | Owner |
|---|---|---|
| The application queries a different KB id or Region | the application's configured KB id / Region | this skill (ask) |
| Retrieval returns 0 results for the user's query | a `Retrieve` probe with that query (Step 8) | this skill |
| A metadata filter or `numberOfResults` excludes results | the application's `retrievalConfiguration` | this skill (ask) |
| The application uses `Retrieve` and discards locations, or does not render citations | application code | application owner |
| A guardrail blocks or rewrites the response | guardrail intervention metrics / trace | guardrails area (`related-skills.md`) |
| An agent answers without consulting the KB | agent configuration | agent runtime area (`related-skills.md`) |
| Embeddings from a sync that just finished are not yet queryable | job `updatedAt` within the last few minutes | this skill |

## Step 6 — chunking, embedding model, staleness (LLM-KB-003, 004)

**Chunking (LLM-KB-003, INFO, workload-specific).**

- `chunkingConfiguration` absent → the service splits content into chunks of about **300 tokens,
  preserving sentence boundaries**. State that default; do not guess another strategy.
- `chunkingStrategy NONE` → each document is one chunk (whole document).
- `FIXED_SIZE` / `HIERARCHICAL` / `SEMANTIC` → report the configured values.
- Judge fit from document sizes: `s3api list-objects-v2 --bucket <b> --prefix <p>` (follow
  `NextContinuationToken`), report the object count and size range. The chunking strategy cannot be
  changed on an existing data source; a change needs a new data source and a re-sync.

**Embedding model (LLM-KB-004, MEDIUM).** Fires only when `bedrock get-foundation-model
--model-identifier <id>` shows `modelLifecycle.status` `LEGACY`, or the model is not on the
supported-embedding-models page. `amazon.titan-embed-text-v2:0` and `cohere.embed-*-v3` are current
and never fire. `amazon.titan-embed-text-v1` (Titan Embeddings G1 – Text) while it is `ACTIVE` is an
INFO note that a newer Titan generation exists, not a finding. Migrating means a new vector index,
re-embedding everything and re-evaluating retrieval.

**Staleness.** Compare the newest `LastModified` among the objects under the inclusion prefixes with
the latest `COMPLETE` job's `updatedAt` (its finish time, not `startedAt`). An object modified after
that time is content the KB has not ingested. Report both timestamps. If the bucket listing is
denied, say staleness is undetermined.

## Step 7 — encryption and reachability (LLM-KB-005, 006)

Keep three states apart and name the field you read: **field absent**, **AWS-owned key**,
**customer managed key (CMK)**. Never write "unencrypted" for data encrypted with an AWS-owned key
or SSE-S3.

**LLM-KB-005 (HIGH) — data source and transient ingestion storage.**

- `serverSideEncryptionConfiguration` absent on the data source → transient ingestion storage uses
  an **AWS-owned key** (Bedrock's default), not a CMK.
- Source bucket: `s3api get-bucket-encryption` → `SSEAlgorithm` `AES256` is SSE-S3 (not a CMK);
  `aws:kms` with a `KMSMasterKeyID` is SSE-KMS (check whether that key is customer managed).
- Fires when neither the data source nor the source bucket uses a CMK.

**LLM-KB-006 (HIGH) — vector store at rest and network.**

- `OPENSEARCH_SERVERLESS`:
  - `opensearchserverless batch-get-collection --ids <id>` → `kmsKeyArn` (`auto` = AWS-owned key).
  - `list-security-policies --type encryption` then `get-security-policy --type encryption --name
    <n>` for the policy whose rules match the collection → `AWSOwnedKey: true` means AWS-owned.
    Encryption at rest is always on for AOSS; the key cannot be changed after the collection is
    created, so moving to a CMK means a new collection and a re-sync.
  - `list-security-policies --type network` then `get-security-policy --type network` →
    `AllowFromPublic: true` on a `collection` rule means the collection endpoint is reachable from
    the internet (IAM and data access policies still apply). `false` with `SourceVPCEs` or
    `SourceServices` (`bedrock.amazonaws.com`) is private. `ListSecurityPolicies` returns summaries
    only; the policy document needs `GetSecurityPolicy`.
- `RDS`: `rds describe-db-clusters` → `StorageEncrypted`, `KmsKeyId`; instances' `PubliclyAccessible`.
- `OPENSEARCH_MANAGED_CLUSTER`: `opensearch describe-domain` → `EncryptionAtRestOptions`,
  `VPCOptions`.
- Third-party stores (Pinecone, Redis Enterprise Cloud, MongoDB Atlas) and others: encryption and
  network posture are not visible through AWS APIs. Record "not checkable from AWS" in Scope not
  covered; do not raise or clear 006.
- A denied policy read is recorded as unavailable, and the half it covers stays undetermined.

## Step 8 — search type and the Retrieve probe (LLM-KB-007)

**LLM-KB-007 (INFO, workload-specific).** The search type is not stored on the KB.
`overrideSearchType` (`HYBRID` / `SEMANTIC`) is a per-request field of `Retrieve` /
`RetrieveAndGenerate` `retrievalConfiguration.vectorSearchConfiguration`; when it is omitted,
Bedrock chooses. Hybrid search is supported only for Amazon RDS, Amazon OpenSearch Serverless and
MongoDB vector stores that contain a filterable text field. Report 007 as INFO, name the store
support, and name the missing signal: the application's `retrievalConfiguration`. Never write "the
KB is configured SEMANTIC-only".

**Retrieve probe (optional, read-only, billed).** Run it only when the user asks what retrieval
returns or when a Step 5 / 007 question needs it, and only if `bedrock:Retrieve` is allowed:

- `bedrock-agent-runtime retrieve --knowledge-base-id <kb> --retrieval-query text=<query>
  --retrieval-configuration` with `numberOfResults` ≤ 5; at most two queries.
- Report only: the result count, each result's `location` URI and its `score`. Discard `content`
  before writing anything. If denied, record it and continue.
- Even when the user explicitly asks to see the chunk text, do not show it: give counts, URIs and
  scores and say the text is withheld because KB content is often sensitive customer data. The user
  can open the source objects directly.

## Step 9 — attachment (LLM-KB-008, LOW)

- `bedrock-agent list-agents` (paginate). For each agent, `list-agent-versions`, then
  `list-agent-knowledge-bases --agent-id <id> --agent-version <v>` for each version, including
  `DRAFT`. The last call requires both ids, so it cannot run without the first two.
- Application callers of `Retrieve` / `RetrieveAndGenerate` appear only in CloudTrail **data
  events** for resource type `AWS::Bedrock::KnowledgeBase`. Check whether any trail selects them
  (`cloudtrail get-event-selectors`). If none does, application use is **unverified**.
- When no agent references the KB, report LLM-KB-008 LOW as "not attached to any agent
  (<what you checked>); application use unverified". Never write a flat "orphaned", and never
  recommend deletion on this evidence alone.

## Step 10 — sync automation and evaluation (LLM-KB-010, 009)

**LLM-KB-010 (INFO, workload-specific).** Signals, in order:

- CloudTrail `lookup-events --lookup-attributes AttributeKey=EventName,AttributeValue=StartIngestionJob`
  (management events, 90 days): an IAM user or console session points to manual syncs; a service
  role, Lambda or Scheduler principal points to automation.
- `scheduler list-schedules` / `get-schedule`: a target whose ARN ends in `startIngestionJob`.
- `events list-rules` / `list-targets-by-rule`: a rule whose target starts an ingestion job.
- If none of these can be read (CloudTrail is often not callable from the agent runtime), report
  010 as INFO "unconfirmed" and name the missing signal. Never promote 010 above INFO.

**LLM-KB-009 (MEDIUM).**

- `bedrock list-evaluation-jobs --application-type-equals RagEvaluation` (paginate), or list all and
  read each summary's `applicationType` verbatim.
- Only a `RagEvaluation` job whose `ragIdentifiers` include this KB's ARN counts. A
  `ModelEvaluation` job does not, whatever its status. Guardrail contextual-grounding settings are
  not a retrieval evaluation (they belong to the guardrails area).
- No qualifying job → 009 fires. Running an evaluation is output-quality
  work; follow *Related skills (optional)*.
- Bedrock evaluation is not available in every Region (`api-quirks.md` §2). If the API is
  unavailable in the Region, report 009 as INFO with that reason.

## Runtime limits seen from the DevOps Agent

The standard agent policy (`AIDevOpsAgentAccessPolicy`) does not list `bedrock:GetIngestionJob` or
`bedrock:Retrieve`, and the agent's tool may block CloudTrail calls. Expect these denials, use the
fallbacks above (job summaries for statistics; no probe; 010 unconfirmed), and record each one in
Scope not covered.

## AWS documentation

- [Sync / ingest a data source](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)
- [Customize ingestion (chunking default)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-customize-ingestion.html)
- [How content chunking works](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-chunking.html)
- [Supported embedding models](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-supported.html)
- [Encryption of knowledge base resources](https://docs.aws.amazon.com/bedrock/latest/userguide/encryption-kb.html)
- [OpenSearch Serverless encryption](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-encryption.html)
- [OpenSearch Serverless network access](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/serverless-network.html)
- [Search type (hybrid vs semantic)](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html)
- [Monitor knowledge bases with CloudWatch Logs](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-bases-logging.html)
- [Bedrock and CloudTrail (data events for knowledge bases)](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html)
- [Create a RAG evaluation job](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-evaluation-create-randg.html)
