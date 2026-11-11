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

The DevOps Agent role needs read-only access. Every API the skill uses is covered by the
[AIDevOpsAgentAccessPolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html)
managed policy (verified against **v14**), with one optional add-on:

- **Optional (one action):** `bedrock:GetIngestionJob` is not in the managed policy. It is the
  only call that returns job-level `failureReasons` when ingestion-log delivery is not
  configured. It ships as an opt-in parameter in `cloudformation/devops-agent-skill-policies`
  (see `cloudformation/opt-in-getingestionjob.md`). Without it, the skill uses ingestion logs
  and per-document status and says job-level reasons are unavailable.

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
- Job-level failure reasons need either CloudWatch Logs delivery or the opt-in
  `bedrock:GetIngestionJob`.
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
