# AWS Batch silent failure modes

A *silent failure* is a job that AWS Batch reports as `SUCCEEDED` with `exitCode: 0`
while the work did not actually complete. Batch records what happened, but it records
it in a field other than `status`.

These modes are the reason `status` alone is not a reliable completion signal.

## The three observed modes

| Mode | `status` | `exitCode` | Where the truth is | Field value |
|---|---|---|---|---|
| Silent OOM | `SUCCEEDED` | `0` | `container.reason` | `OutOfMemoryError: Container killed due to memory usage` |
| Silent timeout | `SUCCEEDED` | `0` | `statusReason` | `Job attempt duration exceeded timeout` |
| Reported OOM | `FAILED` | non-zero | `container.reason` | `OutOfMemoryError: Container killed due to memory usage` |

The third row is the control case, and it matters: the same underlying OOM condition
can surface with either status. Neither field implies the other. Do not infer the
status from the reason, and do not infer the reason from the status — read both.

## Silent timeout is the most damaging

A job definition carries `attemptDurationSeconds`. When the attempt exceeds it, Batch
terminates the job, writes `Job attempt duration exceeded timeout` into `statusReason`,
and may still set `status` to `SUCCEEDED` with `exitCode: 0`.

The work is truncated at the timeout. Any consumer trusting `status` treats a partial
result as a complete one.

This is easy to introduce accidentally: a job definition whose `attemptDurationSeconds`
is shorter than the workload it is asked to run will cap every job silently. In one
observed population, 122 jobs intended to run ~300s all stopped between 120.2s and
188.9s against an `attemptDurationSeconds` of 180. Ten of those jobs reported
`SUCCEEDED`.

**`container.reason` is null for this mode.** An OOM detector alone will miss every
silent timeout. Both fields must be read.

## Where to read these fields

`container.reason`, `statusReason`, `status`, `exitCode`, `startedAt` and `stoppedAt`
are all present on the **`ListJobs` summary object**. Detecting silent failures does
**not** require a `DescribeJobs` call per job.

The `ListJobs` summary carries:

```
jobArn, jobId, jobName, capacityUsage, createdAt, shareIdentifier,
status, statusReason, startedAt, stoppedAt, container{exitCode, reason}
```

This matters for two reasons:

1. Scanning a queue for silent failures is a single paginated `ListJobs` per status,
   not an N+1 fan-out.
2. It works with `batch:ListJobs` alone. `batch:DescribeJobs` is not required for
   silent-failure detection, only for the deeper checks in
   `capacity-and-compute-environments.md`.

## Reproducing the modes

For silent OOM, request memory across **multiple containers** that together exceed the
job's memory allocation. A single container asked to allocate more than its limit did
not reliably populate `container.reason` in observation; two containers each allocating
half the excess did.

For silent timeout, set `attemptDurationSeconds` shorter than the work the container
performs. The job will stop at the limit.

## Detection guidance

Treat these as distinct signals with distinct metrics. Emitting one combined
"silent failure" counter loses the information about which mode occurred, and the two
modes have different fixes (memory sizing versus timeout sizing).

When graphing a silent-failure count, put it on its own widget. Plotted beside a
cumulative `SUCCEEDED` count, a 0-or-1 signal is visually flat and unreadable.

Scope the detection window so the signal can clear. Keying on jobs whose `stoppedAt`
falls inside a recent lookback window lets an alarm return to OK; keying on all
historical jobs produces a counter that only ever rises.
