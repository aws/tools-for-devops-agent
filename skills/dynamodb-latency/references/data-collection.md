# Data Collection (Phase A)

Every call here is read-only, control-plane or CloudWatch. **No data-plane operation appears
in this file, and none may be added.** This skill never reads item data.

## Data source

Use the agent's native `use_aws` tool with the role already assumed in the target account.
Never ask the user for credentials, access keys, or a profile name.

## Inputs

| Input | Default |
|---|---|
| `table_name` | required |
| `region` | the agent's default region; state which one you used |
| `window` | 3 hours for an active incident, 14 days for a review or trend question |
| `period_seconds` | 60 for windows ≤ 6 hours, 300 for longer windows |

`SuccessfulRequestLatency` aggregates at one-minute granularity, so a 60-second period is the
finest useful resolution. Do not request a period below 60.

## Execution flow

### Step 1 — Identity and table metadata (required, run first)

```
sts:GetCallerIdentity
dynamodb:DescribeTable --table-name <table>
```

Record, and carry into the report:

| Field | From | Used for |
|---|---|---|
| `TableStatus` | `Table.TableStatus` | abort unless `ACTIVE` or `UPDATING` |
| `CreationDateTime` | `Table.CreationDateTime` | data-sufficiency guard, on-demand ramp check |
| `BillingModeSummary.BillingMode` | `Table` | whether provisioned metrics apply |
| `ProvisionedThroughput` | `Table` | capacity context for throttling |
| `ItemCount`, `TableSizeBytes` | `Table` | mean item size — **see the staleness rule below** |
| `GlobalSecondaryIndexes[].IndexName` | `Table` | to state plainly that per-index latency is not measurable |
| `Replicas[]` | `Table` | whether Global Tables already place data closer to callers |

**`ItemCount` and `TableSizeBytes` refresh only about every six hours.** Treat a mean item
size derived from them as an approximation, and when either is `0` while the table is taking
writes in the window, mark mean item size **not determinable (stale metadata)** rather than
computing `0`. Never report `0 KB` mean item size.

If `DescribeTable` returns `ResourceNotFoundException`, abort: "Table `<name>` does not exist
in `<region>`, or the role cannot describe it." Do not probe other regions.

### Step 2 — Latency, per operation

One `cloudwatch:GetMetricData` request, namespace `AWS/DynamoDB`, metric
`SuccessfulRequestLatency`, dimensions `TableName=<table>` **and** `Operation=<op>`, for every
operation the workload uses. Request these statistics for each operation:

`Average`, `p50`, `p90`, `p99`, `Maximum`, `SampleCount`

Operations to query — omit none, and record which returned `NoData`:

| Class | Operations |
|---|---|
| Singleton | `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` |
| Multi-item | `Query`, `Scan`, `BatchGetItem`, `BatchWriteItem`, `TransactGetItems`, `TransactWriteItems` |

An operation with no datapoints means the workload did not call it in the window. That is
information, not an error: record `NoData`, and do not include the operation in the profile
table beyond noting it was not exercised.

**Do not fall back to the table-wide `SuccessfulRequestLatency`** (no `Operation` dimension)
as the basis for classification. It blends operation classes whose documented expectations
differ by an order of magnitude. Collect it only if you want a single trend line for the
report header, and label it as blended.

### Step 3 — Errors and throttles

One `cloudwatch:GetMetricData` request, namespace `AWS/DynamoDB`, dimension
`TableName=<table>`, statistic `Sum`, same window and period:

`SystemErrors`, `UserErrors`, `ThrottledRequests`, `ReadThrottleEvents`, `WriteThrottleEvents`

For each, record the total, the per-period series, and the **timestamps of non-zero periods** —
the overlap between those timestamps and the latency rise is what `LT-02` tests. A total alone
cannot establish coincidence.

### Step 4 — Capacity context

One `cloudwatch:GetMetricData` request, statistic `Sum` for consumed, `Average` for
provisioned:

`ConsumedReadCapacityUnits`, `ConsumedWriteCapacityUnits`

and, only when `BillingMode` is `PROVISIONED`:

`ProvisionedReadCapacityUnits`, `ProvisionedWriteCapacityUnits`

On a `PAY_PER_REQUEST` table the provisioned metrics do not exist. Their absence is expected —
record `NotApplicable`, never `NoData`, and never present it as a gap.

## Computing `metric_coverage_minutes` — do not skip this

For each metric, the coverage is the span between its first and last datapoint, **not** the
window you requested. Compute it, and compare it with the window:

```
coverage_minutes = (last_datapoint_ts - first_datapoint_ts) in minutes
coverage_ratio   = coverage_minutes / window_minutes
```

Two guards depend on it:

- `coverage_ratio < 0.5` for `SuccessfulRequestLatency` → the classification is `LT-00`
  indeterminate unless the shortfall is explained by table age.
- A table younger than the window cannot have full coverage. State the table age and say what
  the coverage actually was. Never describe a young table's short series as a regression.

## Error classification

Classify every failed call into exactly one bucket, and carry the bucket into the report:

| Bucket | Trigger | Consequence |
|---|---|---|
| `AccessDenied` | `AccessDeniedException`, `UnauthorizedOperation`, or an explicit IAM denial | present the permissions audit and wait |
| `NotFound` | `ResourceNotFoundException` on `DescribeTable` | abort with the not-found message |
| `NoData` | the call succeeded and returned an empty series | a measurable absence — record it, never coerce to `0` |
| `NotApplicable` | the metric cannot exist for this configuration | expected, not a gap |
| `Throttled` | `ThrottlingException` from CloudWatch or DynamoDB | retry once with backoff, then treat as `ToolingFailure` |
| `ToolingFailure` | anything else — malformed response, timeout, tool error | present the tooling notice and wait |

`NoData` and `NotApplicable` are the two buckets most often mishandled. `NoData` on
`SystemErrors` does **not** mean zero errors; it means the metric published nothing, and a
service-side cause cannot be ruled out. `NotApplicable` on `ProvisionedReadCapacityUnits` for
an on-demand table is simply the shape of the configuration.

## Pre-flight prompts

### Permissions audit

Render verbatim, substituting real values, then **wait**:

> **Permissions gap — the latency analysis would be incomplete**
>
> I could not complete these reads on `<table>` in `<region>` as
> `<caller-arn>`:
>
> | Check | Call | Result |
> |---|---|---|
> | `<check>` | `<api>` | `AccessDenied` |
>
> Missing these means: `<the specific classification or factor that cannot be evaluated>`.
>
> How would you like to proceed?
> 1. **Stop and fix the permissions (recommended)** — I list the exact actions to add.
> 2. **Continue with reduced accuracy** — I analyse what I can reach and mark everything
>    else "unable to verify". The health rating is capped at **Medium** and the
>    classification may be `LT-00` indeterminate.

The actions this skill needs, all of which are in the `AIDevOpsAgentAccessPolicy` managed
policy: `dynamodb:DescribeTable`, `cloudwatch:GetMetricData`. If they are denied, the denial
is a scoping or boundary policy, not a missing grant — say so.

### Tooling notice

Render verbatim, then **wait**:

> **Tooling failure — one or more reads did not complete**
>
> `<call>` failed with `<error class>`, not a permissions error. Affected: `<checks>`.
>
> 1. **Retry now (recommended)**
> 2. **Continue with reduced accuracy** — health rating capped at **Medium**.

## Output schema

Phase A produces one object per table. Every leaf carries a `status`.

```json
{
  "table": {
    "name": "orders-prod",
    "region": "us-east-1",
    "account": "111122223333",
    "caller_arn": "arn:aws:sts::111122223333:assumed-role/...",
    "status_field": "ACTIVE",
    "billing_mode": "PROVISIONED",
    "created": "2025-03-04T11:02:00Z",
    "age_days": 560,
    "item_count": 4820113,
    "table_size_bytes": 39122334455,
    "mean_item_size_bytes": {"value": 8116, "status": "ok"},
    "gsi_names": ["orders-by-status"],
    "replica_regions": [],
    "status": "ok"
  },
  "window": {
    "start": "2026-09-19T09:00:00Z",
    "end": "2026-09-19T12:00:00Z",
    "minutes": 180,
    "period_seconds": 60
  },
  "latency_by_operation": {
    "GetItem": {
      "sample_count": 1841233,
      "average_ms": 4.1,
      "p50_ms": 3.6,
      "p90_ms": 7.2,
      "p99_ms": 68.4,
      "maximum_ms": 412.0,
      "elevated_periods": ["2026-09-19T10:14:00Z", "2026-09-19T11:31:00Z"],
      "coverage_minutes": 180,
      "coverage_ratio": 1.0,
      "status": "ok"
    },
    "Scan": {"status": "NoData"}
  },
  "errors": {
    "system_errors": {"total": 0, "nonzero_periods": [], "status": "ok"},
    "user_errors": {"total": 14, "nonzero_periods": ["..."], "status": "ok"}
  },
  "throttles": {
    "throttled_requests": {"total": 0, "nonzero_periods": [], "status": "ok"},
    "read_throttle_events": {"total": 0, "nonzero_periods": [], "status": "ok"},
    "write_throttle_events": {"total": 0, "nonzero_periods": [], "status": "ok"}
  },
  "capacity": {
    "consumed_read": {"total": 812334, "status": "ok"},
    "consumed_write": {"total": 91233, "status": "ok"},
    "provisioned_read": {"average": 1200, "status": "ok"},
    "provisioned_write": {"average": 400, "status": "ok"}
  }
}
```

Rules on the schema:

- A `status` of `NoData` means the field's numeric value is **absent**, not zero. Do not
  populate `total: 0` alongside `status: "NoData"`.
- `elevated_periods` is the list of period timestamps whose p99 exceeded the operation's
  threshold. `LT-02` intersects this list with `nonzero_periods` from the throttle metrics;
  without both lists the coincidence cannot be established and the rule must not fire.
- `mean_item_size_bytes.status` is `stale` when `ItemCount` or `TableSizeBytes` is `0` while
  consumed write capacity is non-zero in the window.

## API allowlist

Exactly these operations. Anything not listed is out of scope for this skill, and a
data-plane call is a violation of its safety posture rather than an extension of it.

| Service | Operation |
|---|---|
| `sts` | `GetCallerIdentity` |
| `dynamodb` | `DescribeTable` |
| `cloudwatch` | `GetMetricData` (or `GetMetricStatistics` where the agent's tooling prefers it) |

Explicitly **not** in the allowlist, and why:

| Operation | Why not |
|---|---|
| `dynamodb:Scan`, `Query`, `GetItem`, `BatchGetItem` | This skill never reads item data. Mean item size comes from metadata |
| `dynamodb:DescribeContributorInsights`, `cloudwatch:GetInsightRuleReport` | Hot-key identification is out of scope |
| `cloudwatch:DescribeAlarms`, `PutMetricAlarm` | Alarm audit and creation are out of scope; alarm advice is given as prose, not derived from state |
| `application-autoscaling:*` | Capacity sizing is out of scope |
| `servicequotas:*`, `support:*` | Quota increases are out of scope |
| Any `Put*`, `Update*`, `Delete*`, `Create*` | Read-only skill |

## Critical rules

- **Collect per operation.** A table-wide latency average is not a valid basis for
  classification.
- **Keep the timestamps.** Totals cannot establish that throttling and the latency rise
  coincided; period lists can.
- **`NoData` is not zero, and `NotApplicable` is not a gap.** Three of the classification
  rules turn on that distinction.
- **Compute coverage before applying any threshold.** A short series on a young table is not
  a regression.
- **Never add a data-plane call.** If a question needs item-level evidence, say that it does
  and name the skill or method that provides it.
