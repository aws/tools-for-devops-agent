# Pipeline layers - reads and per-layer sequences

All APIs are read-only. No `Create*`/`Update*`/`Delete*`/`Start*`, no
`Retrieve`/`RetrieveAndGenerate`, no object content reads.

## API inventory (by service)

- **bedrock / bedrock-agent:** `ListKnowledgeBases`, `GetKnowledgeBase`, `ListDataSources`,
  `GetDataSource`, `ListIngestionJobs`, `ListKnowledgeBaseDocuments`, `GetFoundationModel`
  (embedding model lifecycle), `ListAgents`, `ListAgentVersions`, `ListAgentKnowledgeBases`,
  `GetAgentKnowledgeBase`. Optional opt-in: `GetIngestionJob` (job-level `failureReasons`).
- **logs:** `DescribeDeliverySources`, `DescribeDeliveries`, `DescribeDeliveryDestinations`
  (find the KB's `APPLICATION_LOGS` destination), `StartQuery`, `GetQueryResults`.
- **s3:** `ListBucket`, `GetBucketLocation`.
- **aoss:** `BatchGetCollection`, `GetSecurityPolicy`, `ListSecurityPolicies`,
  `GetAccessPolicy`, `ListAccessPolicies`, `ListVpcEndpoints`.
- **rds:** `DescribeDBClusters`. **secretsmanager:** `DescribeSecret` (existence only, never
  the value). **kms:** `DescribeKey`.
- **cloudwatch:** `GetMetricData`. **health:** `DescribeEvents`. **cloudtrail:** `LookupEvents`
  (who started/changed syncs).
- **scheduler:** `ListSchedules`, `GetSchedule`. **events:** `ListRules`, `ListTargetsByRule`
  (sync automation).

## Pass 1 - always runs (cheap)

For the scoped KB and each data source:
1. `ListKnowledgeBases` / `GetKnowledgeBase` - resource status, embedding model, vector store type.
2. `ListDataSources` / `GetDataSource` - type, `inclusionPrefixes`, `dataDeletionPolicy`,
   `chunkingConfiguration`, parser.
3. `ListIngestionJobs` newest-first per data source - read `statistics`.

Pass 1 answers for every data source: **was anything ever indexed** (a `COMPLETE` job that
indexed > 0 docs, cited by job ID) and **did the last sync succeed**.

- `status: ACTIVE` is NOT healthy - it confirms resource/index wiring only.
- A no-change sync is not emptiness.

## Pass 2 - targeted (only the selected branch)

### Source
- S3 `ListBucket` + `GetBucketLocation` on the inclusion prefix: keys, sizes, `LastModified`
  only. Staleness: newest `LastModified` vs last `COMPLETE` job `updatedAt`.
- File checks: unsupported extension; > 50 MB (images > 3.75 MB); `.metadata.json` must carry
  the source file's full name + extension (`doc.pdf.metadata.json`); object outside
  `inclusionPrefixes`.
- Cross-account bucket (`bucketOwnerAccountId`): if listing denied, report staleness/file
  checks as **Not checked**, not passed.

### Ingestion / per-document
- Latest job `status` + `statistics` (from Pass 1).
- `ListKnowledgeBaseDocuments` - per-document `FAILED`/`IGNORED`. `statusReason` returned only
  for `IGNORED`.
- `EMBEDDING_FAILED` / `INDEXING_FAILED` reasons: KB `APPLICATION_LOGS` `status_reasons`
  (CloudWatch Logs only). Or the optional `GetIngestionJob` for job-level `failureReasons`.
- Finding the logs: `logs:DescribeDeliverySources` / `DescribeDeliveries`. Disclose
  S3/Firehose destinations as not queryable. Log delivery is not supported for structured
  stores or Kendra GenAI indexes.

### Embedding
- `AWS/Bedrock` `InvocationThrottles` for the embedding `ModelId` during the job window
  (`cloudwatch:GetMetricData`). Match to the window, then hand off to `service-quota-check`.
- `GetFoundationModel` - flag `LEGACY` embedding model.

### Vector store
- See `references/vector-stores.md`.

### Query
- Hybrid-search support (store type) and chunking strategy. Search type is per-request, not
  stored -> **Inspect**. Hierarchical chunking / table-page context can return fewer results
  than `numberOfResults` - expected, explain.

### Resource
- KB or data source `status` `FAILED`/`UPDATE_UNSUCCESSFUL`/`DELETE_UNSUCCESSFUL` +
  `failureReasons`.

### Automation (LOW)
- `scheduler:ListSchedules`/`GetSchedule`, `events:ListRules`/`ListTargetsByRule` - is there
  anything starting ingestion for a corpus that changes?

## Cross-cutting rules
- Check **AWS Health** (`health:DescribeEvents`) for an active Bedrock event in the region
  before prescribing any customer-side fix.
- Paginate every list call to the end.
- Knowledge bases are regional - use the user's region or the current region, and say which.
