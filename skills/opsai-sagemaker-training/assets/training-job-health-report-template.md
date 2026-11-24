# SageMaker Training / Customization Job — Health Report

> Read-only review of Amazon SageMaker training and customization (Nova / JumpStart) jobs for an LLM
> workload.
> Every finding carries an LLM-SM `check-id`, a catalog severity, and the observed evidence.
> No job was mutated. Account IDs and secret/training-data values are redacted.

## Scope

- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Jobs reviewed:** `<count and names across training / customization>`
- **Window:** `<lookback window, e.g. last 14 days of job submissions>`
- **Not covered (disclosed):** `<jobs / regions / checks skipped, with reason — permissions, budget, region-unsupported>`

## Per-Job State

| Job | Type (training / customization) | Status (`TrainingJobStatus`) | `SecondaryStatus` | `FailureReason` (summarized — no secret/data content) | Checkpoint / output produced? (from S3) |
|---|---|---|---|---|---|
| `<name>` | `<type>` | `<InProgress / Completed / Failed / Stopped>` | `<Starting / Pending / Training / …>` | `<one-line summary, no raw data>` | `<yes/no — from ListObjectsV2>` |

> `InProgress` with `SecondaryStatus` `Starting`/`Pending` waiting on GPU capacity is **NOT** `Failed`
> (api-quirks §1). A Pending-on-capacity job is reported as Pending, never as a failure, and gets no
> config recommendation.

## Failure Classification

For each **failed** job, name the bucket and the matching `LLM-SM-TRAIN-*` check-id:

| Job | Bucket (data / AWS-capacity / customer-quota / recipe-hyperparam / IAM-S3 / channel-URI) | check-id | Evidence |
|---|---|---|---|
| `<name>` | `<bucket>` | `<LLM-SM-TRAIN-00X>` | `<the FailureReason signal that placed it in this bucket>` |

> **Capacity vs quota (api-quirks §2):** `InsufficientCapacityError` is an AWS-side shortfall
> (LLM-SM-TRAIN-002 — retry/alternate instance, do **not** request a quota increase); a
> `service-quotas get-service-quota` `Value` of **0** for the instance type is a customer quota
> (LLM-SM-TRAIN-003 — request an increase). Cite the observed `service-quotas` value when classifying.

## Findings

| check-id | severity | job | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-TRAIN-00X` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<name>` | `<concrete observed value>` | `<exact CLI command>` |

Only findings backed by an observed value appear here (evidence or silence). Thresholds AWS does not
publish are marked `workload-specific` at `INFO`.

## Cost Note

| Job | Outcome | Billed GPU time | check-id |
|---|---|---|---|
| `<name>` | `<failed / empty-output / stalled>` | `<BillableTimeInSeconds or instance-hours>` | `<LLM-SM-TRAIN-002 / 007 / 008>` |

Every failed or empty-output GPU run that started on instances is billed, from `TrainingStartTime`
to `TrainingEndTime`; a job that never started (for example a capacity failure) is not. Surface the
cost so a repeated failure is not silently re-billed.

## Prioritized Recommendations

1. `<CRITICAL/HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`
