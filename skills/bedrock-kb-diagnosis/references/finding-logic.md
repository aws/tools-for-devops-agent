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

## Severity

| Finding | Severity |
| --- | --- |
| Data source with no ingestion job, or no `COMPLETE` job that indexed documents (retrieval returns nothing) | CRITICAL |
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

Some ingestion or query failures look like permission errors but are not an IAM
principal-policy gap, so they must **not** route to the `aiml-access-diagnostics` handoff.
Report them under a **"Not an access denial"** form: name the real cause and the fix.

- A VPC/private AOSS collection with no network-policy source for `bedrock.amazonaws.com` and
  no VPC endpoint (connectivity gap, not a principal policy).
- An S3 source bucket in a different Region than expected, or a `GetBucketLocation` mismatch.
- A cross-account source bucket whose **bucket policy** rejects the KB service role (a
  resource-policy gap on the remote side, not the agent's own IAM).
- A KMS key policy on the data source or vector store that the KB role is not a key user of.

These surface during ingestion as failures but are addressed by fixing the network policy,
Region, bucket policy, or key policy - not by editing the agent's IAM. A genuine
`AccessDenied` on the ingestion or retrieval principal still hands off to
`aiml-access-diagnostics` with role, action, and resource.
