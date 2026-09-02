# Fleet Orchestration

Loaded only for multi-file-system reviews (2+ file systems). Covers batching,
caching, the manifest for large fleets, and the two-layer report. Single-file-system
reviews never load this file.

## When this applies

Routing (from `SKILL.md`) sends 2+ file systems here:

| Count | Behavior |
|---|---|
| 2-10 | Single pass. Summary matrix + full details for **all** file systems. |
| 11-20 | Single pass. Summary matrix + details for **Low-rated** file systems only. |
| 21+ | Batched (10 per batch) with a manifest for progress tracking and resume. |

## Caching

Group the input file systems by `account_id` + `region` before collecting:

- **Account/region-level lookups once per group.** `sts get-caller-identity` runs
  once. `cloudwatch describe-alarms` can be listed once per region and matched to
  file systems locally, rather than called per file system.
- **Directory Service lookups deduplicated.** Multiple file systems may share one
  AWS Managed AD `directory_id`; call `ds describe-directories` once per unique
  directory and reuse the `Stage` result.
- **Per-file-system data** (`describe-file-systems`, `describe-backups`,
  `get-metric-data`) is still collected for each file system.

## Batching the metric queries

`cloudwatch get-metric-data` is limited to **5 file systems per call** (tool-use
payload size). For a fleet:

1. Chunk the file systems into groups of ≤5.
2. Issue one `get-metric-data` per chunk, each `MetricDataQueries[].Id` in
   snake_case and suffixed with a per-file-system index (e.g. `free_min_0`,
   `read_bytes_0`, `free_min_1`, ...).
3. Reassemble results back to each file system before applying finding logic.

## Manifest (21+ file systems)

For large fleets, create an in-memory manifest so the review can report progress and
resume if interrupted:

```json
{
  "review_id": "fsx-windows-sla-fleet-<YYYY-MM-DD>",
  "region": "us-east-1",
  "total": 34,
  "batches": [
    { "batch": 1, "file_system_ids": ["fs-a", "..."], "status": "completed" },
    { "batch": 2, "file_system_ids": ["fs-k", "..."], "status": "in_progress" },
    { "batch": 3, "file_system_ids": ["fs-u", "..."], "status": "pending" }
  ],
  "results": { "fs-a": { "rating": "Medium", "..." : "..." } }
}
```

- Process batch by batch; mark each `completed` as its findings are computed.
- If interrupted, resume at the first non-`completed` batch — do not re-collect
  completed file systems.
- Only render the final report once all batches are `completed`.

## Two-layer report

Produce the fleet report per `references/report-format.md`:

1. **Summary** — counts, SLA Readiness distribution, common-gaps table (finding →
   count, worst first), and a cost-optimization summary (how many file systems carry
   💰 notes).
2. **Dimensions Matrix** — one row per file system, terse cells from the short-state
   vocabulary, `💰` shown inline on the Throughput/Storage cells where applicable,
   and the per-file-system Rating in the last column.
3. **File System Details** — the full single-file-system report for **Low-rated**
   file systems (all file systems when the fleet is ≤10).

## Sort order

- **Default:** Rating worst-first (Low → Medium → High → Indeterminate). Within the
  same rating, alphabetical by file-system ID.
- **Input order:** when the user says "keep order" / "in order".
- Never ask; pick the default unless the user specified otherwise.

## Fleet consistency rules

- Apply the exact same finding logic and thresholds per file system as the
  single-file-system path — the fleet layer only aggregates.
- A file system whose core `describe-file-systems` failed is rated
  **Indeterminate** and listed as such; it does not block the rest of the fleet.
- The common-gaps table counts each distinct finding once per file system.
- 💰 cost notes are summarized but never roll into the SLA distribution counts.
