# SageMaker Batch Transform Job — Health Report
> Area: batch transform. Real-time and serverless/async endpoints use their own report templates in this skill.
> Read-only review of Amazon SageMaker batch transform jobs used for offline LLM scoring (bulk
> classification, offline generation).
> Every finding carries an `LLM-SM-BATCH-*` check-id, a catalog severity, and the observed evidence.
> No job was mutated. Account IDs and secret / scored-data values are redacted.
## Scope
- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Transform jobs reviewed:** `<count and names>`
- **Window:** `<lookback window, e.g. last 14 days of job submissions>`
- **Not covered (disclosed):** `<jobs / regions / S3 prefixes / checks skipped, with reason — permissions, budget, region-unsupported>`
## Per-Job State
| Job | `TransformJobStatus` | `FailureReason` (summarized — no scored-data content) | `ContentType` / `SplitType` | `MaxConcurrentTransforms` / `MaxPayloadInMB` / `BatchStrategy` | `TransformOutput.KmsKeyId` set? |
|---|---|---|---|---|---|
| `<name>` | `<InProgress / Completed / Failed / Stopped>` | `<one-line summary, no raw data>` | `<type / split>` | `<n / MB / SingleRecord or MultiRecord>` | `<yes (CMK) / no>` |
## Failure Classification
For each **failed** job, name the cause and cite `LLM-SM-BATCH-001`:
| Job | Cause (input format / `ContentType`-`SplitType` mismatch / S3 access on input or output) | check-id | Evidence |
|---|---|---|---|
| `<name>` | `<cause>` | `LLM-SM-BATCH-001` | `<the FailureReason signal that placed it in this bucket>` |
> A `Failed` job is usually the data or the role, not the model container. Read `FailureReason` before
> blaming the container.
## Output Reconciliation
| Job | Input files | Output `.out` objects (`ListObjectsV2`) | Reconciled? | check-id |
|---|---|---|---|---|
| `<name>` | `<n>` | `<n>` | `<yes / short by n / output prefix empty>` | `<LLM-SM-BATCH-003 if short>` |
> `Completed` means the job ran to the end, not that every record was scored (api-quirks §4).
> Reconcile output against input before calling a run complete. CloudWatch "no datapoints" is not a
> measured zero (api-quirks §3); read the transform logs too.
## Findings
| check-id | severity | job | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-BATCH-00X` | `<catalog severity>` | `<name>` | `<concrete observed value>` | `<exact CLI command>` |
Only findings backed by an observed value appear here (evidence or silence). Each severity is the
catalog severity; a tuning threshold AWS does not publish (e.g. parallelism for LLM-SM-BATCH-002) is
marked `workload-specific` and reported against the observed dataset size, never an invented target.
## Prioritized Recommendations
1. `<HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`
