# Finding logic - verdicts, assessment rules, severity

## Verdict vocabulary

Every finding is exactly one of:

- **Root cause** - evidence shows this layer broke. A layer is only called root cause when
  the API shows it.
- **Contributing** - evidence shows a fault, but not the one behind the reported symptom.
- **Inspect** - the API cannot show it; give the exact operator check. Data-plane facts (AOSS
  index engine, Aurora table columns, per-request search type) resolve here, never pass/fail.
- **Ruled out** - the layer was checked and is healthy.
- **Not checked** - the call was denied, the region/store is unsupported, or scope was
  limited. State the reason.

## Assessment rules

- `ACTIVE` is never reported as healthy. "Populated" requires a `COMPLETE` job that indexed
  documents, cited by job ID.
- "Zero failed documents" is only stated when a completed job was actually read. If no job
  exists, nothing was measured.
- Ingestion logs are queried only when delivery goes to CloudWatch Logs. S3/Firehose
  destinations are disclosed as not queryable.
- `chunkingConfiguration` unset = service default (~300 tokens, sentence boundaries kept). It
  does NOT mean "no chunking". `NONE` = each document kept as one chunk.
- Chunking strategy and parser type cannot be changed on an existing data source -> the fix is
  "add a new data source and re-sync", not "edit the data source".
- Knowledge bases are regional. Use the user's region or the current region; say which.
- Check AWS Health for an active Bedrock event in the region before any customer-side fix.
- Paginate every list call to the end.
- Cross-account source bucket (`bucketOwnerAccountId`): if the S3 listing is denied, staleness
  and file checks are **Not checked**, not passed.
- Source-bucket listing is not in the default managed policy (`s3:ListBucket` is allowed there
  only for the `AWSLogs/*` prefix). Without the opt-in grant, staleness and file checks are
  **Not checked**, not passed.
- A file dropped at intake (over the size limit, or an unsupported type such as `.zip`) may be
  absent from `ListKnowledgeBaseDocuments` AND from `APPLICATION_LOGS`. Its reason is only in
  `GetIngestionJob.failureReasons` (opt-in). Without that grant, detect drops from the job
  `statistics` (`scanned - indexed - failed - skipped > 0`) and report the file identities as
  **Not checked**.
- A sync **rejected at start** (`StartIngestionJob` -> `ValidationException ... storage
  configuration provided is invalid`) creates no ingestion job. Do not read the resulting empty
  job list as "never synced"; route it to the vector store layer.

## Severity

| Finding | Severity |
| --- | --- |
| Data source with no ingestion job, or no `COMPLETE` job that indexed documents (retrieval returns nothing) - EXCEPT a sync rejected at start, which creates no job and is a vector-store fault | CRITICAL |
| Latest ingestion job `FAILED` or `STOPPED` | HIGH |
| Latest job `COMPLETE` with `numberOfDocumentsFailed` > 0 | HIGH |
| Source objects changed after the last `COMPLETE` sync, while user reports stale answers | HIGH |
| AOSS data-access policy missing the KB role, or private network policy without a Bedrock/VPC endpoint source | HIGH |
| Aurora Data API disabled, cluster not available, or credentials secret missing | HIGH |
| Data source removed with `RETAIN`, while user reports removed content still cited | HIGH |
| Documents `IGNORED`, with `statusReason` quoted | MEDIUM |
| Embedding-model throttles during the ingestion window (hand off to `service-quota-check`) | MEDIUM |
| Embedding model `LEGACY` in `GetFoundationModel` | MEDIUM |
| Files over the size limit or with unsupported extensions under the inclusion prefix | MEDIUM |
| `.metadata.json` without a matching source file | MEDIUM |
| No schedule/rule/automation that starts ingestion for a corpus that changes | LOW |
| Knowledge base attached to no agent | LOW ("not used" is never claimed - app calls are only in CloudTrail data events) |

## Not an access denial (looks like access, but isn't)

A few ingestion failures look like permission errors but are not an authorization decision on
the agent's own principal, so they are diagnosed locally and NOT routed to
`aiml-access-diagnostics`:

- A private AOSS collection whose network policy has no `SourceServices:
  ["bedrock.amazonaws.com"]` and no VPC endpoint (a connectivity gap, not a principal policy).
- An S3 source bucket in a different Region than expected, or a `GetBucketLocation` mismatch.

Everything that IS an authorization decision hands off, and the handoff is **required**:

- An `AccessDenied` on the ingestion or retrieval principal.
- An **S3 bucket-policy** denial and a **KMS key-policy** denial. `aiml-access-diagnostics`
  hop 5 covers resource policies and runs the full chain for the KB service role, so these go
  to the handoff with role, action, and resource - do not diagnose them here.
