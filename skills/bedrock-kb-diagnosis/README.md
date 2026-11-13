# Bedrock Knowledge Base Diagnosis

Reactive, read-only diagnosis of a deployed Amazon Bedrock Knowledge Base when it stops
answering correctly - no sources, stale answers, a failed or missing sync, a document that
never indexed, indexing failures, or throttled ingestion. The skill starts from the reported
symptom, walks the RAG pipeline in order (source -> ingestion -> embedding -> vector store ->
query), stops at the first layer with evidence of a fault, and returns the fix as a command or
console step for the operator to run.

## What This Skill Does

Ties a reported symptom to a pipeline layer using ingestion-job history, per-document status,
ingestion logs, and vector-store state - the evidence existing tooling doesn't read.
Ad-hoc Q&A tends to stop at `GetKnowledgeBase` returning `ACTIVE`, which only confirms the
resource and index wiring, not that any data was indexed. Runs in two passes: an always-on
cheap pass (resource + data sources + ingestion-job statistics) and a targeted pass that runs
only the reads for the branch the symptom points to.

**Example prompts:**
- "My Bedrock knowledge base returns no sources for any query"
- "Our KB answers are missing documents we uploaded this week"
- "The last sync on my knowledge base failed partway through"
- "One document never shows up in my knowledge base"
- "Indexing keeps failing on my OpenSearch Serverless knowledge base"
- "The KB keeps citing a document we deleted"

## Prerequisites

### IAM Permissions Required

The DevOps Agent role needs read-only access. Most APIs the skill uses are covered by the
[AIDevOpsAgentAccessPolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
managed policy (verified against **v15**). Two capabilities are NOT covered by default and
ship together as an opt-in parameter in the shared `cloudformation/devops-agent-skill-policies`
template (see `references/opt-in-policy.md` for the exact grant and snippet):

- **Source-bucket reads** - `s3:ListBucket` and `s3:GetBucketLocation`, scoped to the data
  source buckets. The managed policy allows `s3:ListBucket` only for the `AWSLogs/*` prefix, so
  without this grant the staleness and file checks cannot run and are reported as **Not checked**.
- **`bedrock:GetIngestionJob`** - the only call that returns `failureReasons`, and the only way
  to name a file dropped at intake (an oversized or unsupported file is absent from both
  `ListKnowledgeBaseDocuments` and the ingestion logs). Without this grant, the skill infers a
  drop from the job `statistics` (`scanned - indexed - failed - skipped`) and reports the file
  identities as **Not checked**.

**Not in the managed policy, disclosed rather than skipped silently:**
- `s3vectors:*` reads - S3 Vectors stores are reported as **Not checked**.
- `bedrock:Retrieve` - left out by design (it returns document content).

**Note:** All operations are read-only. This skill does not modify any resources, makes no
`Retrieve`/`RetrieveAndGenerate` call, reads no document or chunk content, and masks account
IDs in quoted ARNs.

### AWS Resources

- A deployed knowledge base with at least one data source. Ingestion-job history is read via
  `ListIngestionJobs`; no job existing is itself a finding.
- CloudWatch Logs ingestion-log delivery is optional - failure reasons for
  `EMBEDDING_FAILED`/`INDEXING_FAILED` are only queryable when delivery goes to CloudWatch
  Logs. S3/Firehose destinations are disclosed as not queryable.
- Cross-account source buckets may deny the S3 listing; those checks are reported as Not
  checked, not passed.

## How to Use with DevOps Agent

1. Upload this skill to your DevOps Agent Space.
2. Select the "Chat tasks" subagent (also surfaces for `INCIDENT_RCA`).
3. Ensure the DevOps Agent role has the permissions above (plus the opt-in parameter if you
   want job-level failure reasons without logs).
4. Describe the symptom in natural language.

**Agent types:** Chat tasks, Incident RCA

## Output

- The faulty pipeline layer named, with evidence (API, field, value) and a fix command/step.
- A pipeline walk showing each layer's verdict (Root cause / Contributing / Inspect / Ruled
  out / Not checked).
- Findings by severity; data-plane facts reported as Inspect with the exact operator check.

## Key Features

- **Two-pass:** cheap always-on pass answers "was anything indexed" and "did the last sync
  succeed" for every data source before any targeted reads.
- **Evidence-based verdicts:** `ACTIVE` is never "healthy"; "populated" requires a `COMPLETE`
  job that indexed documents, cited by job ID.
- **Store-scoped checks:** AOSS and Aurora checks fire only on that store; third-party and S3
  Vectors stores are disclosed as Not checked.
- **Clean boundaries:** hands off IAM to `aiml-access-diagnostics`, posture to
  `bedrock-operation-review`, quota to `service-quota-check`.
- **Read-only and safe:** no writes, no `Retrieve`, no content reads; account IDs masked.

## Limitations

- Does not measure retrieval quality, run evaluation jobs, or judge answer correctness.
- Naming a file dropped at intake needs the opt-in `bedrock:GetIngestionJob`; without it the
  skill reports a drop count from job statistics but not the file identities.
- AOSS index engine and Aurora table columns are data-plane facts - reported as Inspect.
- S3 Vectors stores and third-party stores (Pinecone, Redis Enterprise Cloud, MongoDB Atlas)
  are not checkable from AWS APIs.
- Kendra GenAI index, structured (Redshift), and graph (Neptune Analytics) knowledge bases are
  deferred to a later version.

## Disclaimer

> This skill is sample code, not intended for production use without additional review and
> testing. Users should validate findings in a non-production environment first.
> Recommendations are based on AWS best practices as of the skill version date and may not
> reflect the latest service changes.
