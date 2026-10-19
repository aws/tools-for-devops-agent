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
| `baseline` | the **7 days immediately before** the window start, per operation |
| `slo` | optional — a latency objective the user states, e.g. "p99 under 25 ms for GetItem" |
| `reported_window` | optional — when the user says their client saw slowness, if different from the analysis window |

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
| `CreationDateTime` | `Table.CreationDateTime` | coverage guard, baseline span |
| `BillingModeSummary.BillingMode` | `Table` | whether provisioned metrics apply |
| `ProvisionedThroughput` | `Table` | capacity context for the throttling handoff |
| `ItemCount`, `TableSizeBytes` | `Table` | mean item size — **see the staleness rule below** |
| `GlobalSecondaryIndexes[].IndexName` | `Table` | GSI throttle queries in Step 3; stating that per-index latency is not measurable |
| `Replicas[]` | `Table` | whether Global Tables already place data closer to callers |

**`ItemCount` and `TableSizeBytes` refresh only about every six hours.** Treat a mean item
size derived from them as an approximation, and when either is `0` while the table is taking
writes in the window, mark mean item size **not determinable (stale metadata)** rather than
computing `0`. Never report `0 KB` mean item size.

If `DescribeTable` returns `ResourceNotFoundException`, abort: "Table `<name>` does not exist
in `<region>`, or the role cannot describe it." Do not probe other regions.

### Step 2 — Latency per operation: window and baseline

All queries in this step: namespace `AWS/DynamoDB`, metric `SuccessfulRequestLatency`,
dimensions `TableName=<table>` **and** `Operation=<op>`.

Operations to query — omit none, and record which returned no datapoints:

| Class | Operations |
|---|---|
| Singleton | `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` |
| Multi-item | `Query`, `Scan`, `BatchGetItem`, `BatchWriteItem` |
| Transactional | `TransactGetItems`, `TransactWriteItems` |

**2a — Window series.** For every operation, over the window at `period_seconds`:
`Average`, `p50`, `p90`, `p99`, `Maximum`, `SampleCount`.

**2b — Baseline.** For every operation that has window datapoints, one query per statistic
over the 7 days ending at the window start, with **`Period` = 604800** so CloudWatch returns a
single datapoint computed over every request in that span: `p50`, `p99`, `SampleCount`.

Do not compute a baseline by averaging or taking the median of datapoints yourself — that is
error-prone in context and statistically wrong for percentiles. Let CloudWatch compute it.

The baseline is **usable** when its `SampleCount` is ≥ 1,000. Otherwise record
`baseline.status = "insufficient"` and say why (table younger than the baseline span, the
operation was rarely called, or no datapoints). A baseline that includes an earlier incident
is still a baseline; if the user mentions one in that week, say the baseline may be inflated.

**2c — In-window fallback reference.** Only for a multi-item or transactional operation whose
baseline is `insufficient`: query `p50`, `p99`, and `SampleCount` over the window with `Period`
= one third of the window, rounded down to a multiple of 60 seconds. The first datapoint is the
fallback reference. `references/finding-logic.md` caps its confidence at Low, because a problem
that began before the window contaminates it.

An operation with no window datapoints was not called in the window. That is information, not
an error: record `NoData` and list it as not exercised.

**Do not fall back to the table-wide `SuccessfulRequestLatency`** (no `Operation` dimension)
as the basis for classification. It blends operation classes whose documented expectations
differ by an order of magnitude.

### Step 3 — Errors and throttles

Same window and period, statistic `Sum`. **Mind the dimensions — querying a metric on a
dimension set DynamoDB does not publish returns an empty series that looks exactly like "no
errors".**

| Metric | Dimensions | Query |
|---|---|---|
| `SystemErrors` | `TableName` + `Operation` | **every** operation in the Step 2 list — including ones with no latency datapoints, because an operation whose every request failed has no successful latency at all. **Never on `TableName` alone** — DynamoDB does not publish it there |
| `FaultInjectionServiceInducedErrors` | `TableName` + `Operation` | every operation for which `SystemErrors` is recorded |
| `ThrottledRequests` | `TableName` + `Operation` | **every** operation in the Step 2 list — a fully throttled operation also has no successful latency |
| `ReadThrottleEvents`, `WriteThrottleEvents` | `TableName` | table level — excludes GSIs |
| `ReadThrottleEvents`, `WriteThrottleEvents` | `TableName` + `GlobalSecondaryIndexName` | once per GSI from Step 1 |

For each series record the total, the per-period values, and the **timestamps of non-zero
periods** — the overlap between those timestamps and the latency rise is what `LT-01` and
`LT-02` test. A total alone cannot establish coincidence.

`UserErrors` is **not a table metric** — it aggregates HTTP 400s for the whole account and
Region. Do not collect it as evidence about this table. If you report it at all, label it
"account-wide, all tables".

### Step 4 — Capacity context

One request, same window and period, statistic `Sum` for consumed, `Average` for provisioned:

`ConsumedReadCapacityUnits`, `ConsumedWriteCapacityUnits` (dimension `TableName`)

and, only when `BillingMode` is `PROVISIONED`:

`ProvisionedReadCapacityUnits`, `ProvisionedWriteCapacityUnits`

If Step 3 recorded GSI throttling, add the same consumed (and, if provisioned, provisioned)
metrics for that index with `TableName` + `GlobalSecondaryIndexName`.

Keep the **per-period** consumed series, not just the total: the throttling handoff (`CF-04`)
reports capacity in the throttled periods. Convert a period's `Sum` to units per second by
dividing by `period_seconds` before comparing it with provisioned capacity, which is already a
per-second rate.

On a `PAY_PER_REQUEST` table the provisioned metrics do not exist. Record `NotApplicable`,
never `NoData`, and never present it as a gap.

### Step 5 — Result-set size (multi-item operations only)

For every `Query` and `Scan` with window datapoints: `ReturnedItemCount`, dimensions
`TableName` + `Operation`, statistic `Average` (items returned per request) — at
`period_seconds` over the window, and as one `Period` = 604800 datapoint over the baseline
span.

`ReturnedItemCount` counts items *returned*, not items *evaluated*: a `Scan` whose filter
discards most of what it reads looks small here. Treat it as supporting evidence only.

## Statuses — compute these before applying any rule

### Event counters: `recorded`, `none_recorded`, or unknown

`SystemErrors`, `FaultInjectionServiceInducedErrors`, `ThrottledRequests`, and the throttle-event
metrics publish datapoints **only when an event occurs** (see
[`dynamodb-facts.md`](dynamodb-facts.md)). An empty series is the normal shape of a healthy
table — but only if you can show the table was active and the query was correct. Assign:

| Status | Condition |
|---|---|
| `recorded` | the series has datapoints; carry the total and the non-zero period timestamps |
| `none_recorded` | the call succeeded, used the dimensions in the Step 3 table, returned no datapoints, **and** `SuccessfulRequestLatency` for the same operation (for table- or index-level throttle events: for any operation) has datapoints in the window. Treat as zero events |
| `not_exercised` | the call succeeded and returned nothing for an operation that also has no `SuccessfulRequestLatency` datapoints — the operation was not called. Not relevant to the classification, and does **not** block `LT-05` |
| `NoData` | the call succeeded and returned nothing, but activity cannot be confirmed for a counter the classification depends on — e.g. a table-level throttle counter when no operation has latency datapoints. Unknown, not zero |
| `AccessDenied` / `ToolingFailure` | see Error classification |

Say "no `SystemErrors` recorded", never "`SystemErrors` measured 0".

### Per-period assessability (the `SampleCount` floor)

A percentile over a handful of requests is noise. For each operation and period:

- the period is **p99-assessable** when `SampleCount` ≥ 100
- the period is **p50-assessable** when `SampleCount` ≥ 10

Periods below the floor are counted as **low volume** and excluded from elevation tests. An
operation whose assessable periods are fewer than 10, or fewer than half its periods with
data, is **not assessable** for that statistic — say so; do not classify it.

### Coverage

For each operation, the coverage is the span between its first and last datapoint, **not** the
window you requested:

```
coverage_minutes = (last_datapoint_ts - first_datapoint_ts) in minutes
coverage_ratio   = coverage_minutes / window_minutes
```

- `coverage_ratio < 0.5` for every operation with data → `LT-00` indeterminate unless the
  shortfall is explained by table age.
- A table younger than the window cannot have full coverage. State the table age and the
  actual coverage. Never describe a young table's short series as a regression.

### Elevated periods

`references/finding-logic.md` defines when a period counts as **p50-elevated** or
**p99-elevated** for each operation class, with and without a usable baseline. Compute both
lists per operation, from assessable periods only, and carry them in the output object. Every
correlation rule intersects these lists with the non-zero period lists from Step 3.

## Error classification

Classify every failed call into exactly one bucket, and carry the bucket into the report:

| Bucket | Trigger | Consequence |
|---|---|---|
| `AccessDenied` | `AccessDeniedException`, `UnauthorizedOperation`, or an explicit IAM denial | present the permissions audit and wait |
| `NotFound` | `ResourceNotFoundException` on `DescribeTable` | abort with the not-found message |
| `NoData` | the call succeeded, returned an empty series, and the empty series cannot be read as `none_recorded` | a measurable absence — record it, never coerce to `0` |
| `NotApplicable` | the metric cannot exist for this configuration | expected, not a gap |
| `Throttled` | `ThrottlingException` from CloudWatch or DynamoDB | retry once with backoff, then treat as `ToolingFailure` |
| `ToolingFailure` | anything else — malformed response, timeout, tool error | present the tooling notice and wait |

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
  "baseline_span": {"start": "2026-09-12T09:00:00Z", "end": "2026-09-19T09:00:00Z"},
  "user_context": {"slo": null, "reported_window": null, "reported_symptom": "p99 alarm fired twice"},
  "latency_by_operation": {
    "GetItem": {
      "class": "singleton",
      "sample_count": 1841233,
      "average_ms": 4.1, "p50_ms": 3.6, "p90_ms": 7.2, "p99_ms": 68.4, "maximum_ms": 412.0,
      "assessable_periods": {"p50": 180, "p99": 180, "low_volume": 0},
      "baseline": {"p50_ms": 3.4, "p99_ms": 14.9, "sample_count": 98213004, "status": "ok"},
      "p50_elevated_periods": [],
      "p99_elevated_periods": ["2026-09-19T10:14:00Z", "2026-09-19T11:31:00Z"],
      "p50_pattern": "none",
      "p99_pattern": "isolated",
      "coverage_minutes": 180,
      "coverage_ratio": 1.0,
      "status": "ok"
    },
    "Scan": {"status": "NoData"}
  },
  "errors_by_operation": {
    "GetItem": {
      "system_errors": {"status": "none_recorded"},
      "fis_errors": {"status": "none_recorded"}
    }
  },
  "throttles": {
    "throttled_requests_by_operation": {"GetItem": {"status": "none_recorded"}},
    "table_read_throttle_events": {"status": "none_recorded"},
    "table_write_throttle_events": {"status": "none_recorded"},
    "gsi": {
      "orders-by-status": {
        "read_throttle_events": {"status": "none_recorded"},
        "write_throttle_events": {"status": "none_recorded"}
      }
    }
  },
  "capacity": {
    "consumed_read": {"total": 812334, "peak_units_per_second": 214.0, "series": "per period", "status": "ok"},
    "consumed_write": {"total": 91233, "peak_units_per_second": 31.5, "series": "per period", "status": "ok"},
    "provisioned_read": {"average": 1200, "status": "ok"},
    "provisioned_write": {"average": 400, "status": "ok"}
  },
  "returned_item_count": {}
}
```

A `recorded` counter carries `{"total": n, "nonzero_periods": [...], "status": "recorded"}`.

Rules on the schema:

- `NoData`, `none_recorded`, and `not_exercised` carry **no** numeric value. Never write
  `total: 0` beside any of them.
- `p50_pattern` / `p99_pattern` take one of `none`, `isolated`, `recurring`, `sustained`, or
  `not_assessable`, as defined in `references/finding-logic.md`.
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
| `dynamodb:DescribeContributorInsights`, `cloudwatch:GetInsightRuleReport` | Hot-key identification is out of scope, and contributor reports contain key values |
| `cloudwatch:DescribeAlarms`, `PutMetricAlarm` | Alarm audit and creation are out of scope |
| `application-autoscaling:*` | Capacity sizing is out of scope |
| `servicequotas:*`, `support:*` | Quota increases are out of scope |
| Any `Put*`, `Update*`, `Delete*`, `Create*` | Read-only skill |

## Critical rules

- **Collect per operation**, including `SystemErrors` and `ThrottledRequests` — both are
  published per `Operation`, and `SystemErrors` *only* per `Operation`.
- **Let CloudWatch compute aggregates.** Baselines come from a single long-period datapoint,
  not from your own arithmetic over a series.
- **Keep the timestamps.** Totals cannot establish that an event and the latency rise
  coincided; period lists can.
- **`none_recorded` requires proof of activity; `NoData` is unknown; `NotApplicable` is not a
  gap.** The classification turns on that distinction.
- **Apply the `SampleCount` floor and compute coverage before any threshold.**
- **Never add a data-plane call.** If a question needs item-level evidence, say that it does
  and name the skill or method that provides it.
