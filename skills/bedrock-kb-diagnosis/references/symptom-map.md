# Symptom map

Route the user's reported symptom to the pipeline layer checked first. Walk layers in order
(source -> ingestion -> embedding -> vector store -> query) and stop at the first with
evidence of a fault.

| Symptom | Layer checked first | Evidence | API-verifiable? |
| --- | --- | --- | --- |
| Queries return nothing / no sources | Ingestion | No ingestion job ever ran, or no `COMPLETE` job indexed new documents. A later no-change sync is not emptiness. | Yes |
| Answers miss recent documents | Source vs last sync | Newest S3 `LastModified` under the inclusion prefix is later than the last `COMPLETE` job's `updatedAt`. | Yes |
| Answers cite content that was removed | Data source lifecycle | Data source deleted or replaced with `dataDeletionPolicy: RETAIN`, which leaves its vectors in the store. | Yes |
| Sync failed or partial | Ingestion, per document | Job `status`/`statistics`. `ListKnowledgeBaseDocuments` shows `FAILED`/`IGNORED` (`statusReason` only returned for `IGNORED`). Ingestion log `status_reasons` explain `EMBEDDING_FAILED`/`INDEXING_FAILED`. | Yes (failure reasons need logs or the optional `GetIngestionJob`) |
| One document never shows up | Source | Unsupported extension; file over 50 MB (images over 3.75 MB); `.metadata.json` name doesn't match its source file; object outside `inclusionPrefixes`. | Yes |
| Indexing fails | Vector store | AOSS: collection not `ACTIVE`; private network policy with neither `SourceServices: bedrock.amazonaws.com` nor a VPC endpoint; data access policy missing the KB role. Aurora: cluster not available, Data API off, credentials secret missing. | Yes (index engine and table columns are **Inspect**) |
| Ingestion slow or throttled | Embedding | `AWS/Bedrock` `InvocationThrottles` for the embedding `ModelId` during the job window. | Yes |
| Knowledge base or data source stuck | Resource | `status` `FAILED`/`UPDATE_UNSUCCESSFUL`/`DELETE_UNSUCCESSFUL` with `failureReasons`. | Yes |
| Poor matches on IDs, codes, SKUs | Query | Store supports hybrid search (RDS/Aurora, OpenSearch Serverless, or MongoDB Atlas with a filterable text field); chunking strategy. Search type is set per request, not stored on the KB. | **Inspect** |
| Fewer results than `numberOfResults` | Query | Hierarchical chunking, or table/page context returned as one result. Expected behavior - explain, do not report as a fault. | Yes |
| Access denied on ingestion or retrieval | IAM | Hand off to `aiml-access-diagnostics` with role, action, resource. | Handoff |

**Scope boundary:** diagnoses a deployed KB from evidence the AWS APIs expose. Does not
measure retrieval quality, run evaluation jobs, or judge whether answers are correct.
