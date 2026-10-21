---
name: data-usage
description: Data usage, billing units, plan consumption, quota metrics, anomaly detection, and time-series analysis concepts and query workflow. Load when the user asks about data usage, ingestion volumes, billing, plan limits, overage, quota attribution, usage anomalies, or usage trends over time.
metadata:
  author: coralogix
  version: 1.0.0
  summary: Data usage, billing units, plan consumption, quota metrics, anomaly detection, and time-series analysis concepts and query workflow. Load when the user asks about data usage, ingestion volumes, billin
  tier: partner-managed
  agent_types: GENERIC
---

# Data Usage Guidance

## Purpose

### Tool routing

Use the Data Usage Query API by default for billable usage, plan consumption, quota, or a capabilities-supported breakdown: call `get_data_usage_capabilities`, then `query_data_usage`.

Use `query_promql_*` only when the question is about the exported `cx_data_usage_*` metrics themselves, needs to be combined with other PromQL metrics, or requires monitoring-style analysis unavailable from the Data Usage Query API. Do not substitute PromQL for the Data Usage Query API when an authoritative billing answer is needed.

### Complete schemas

Call `get_data_usage_capabilities` first. It returns the current options that may be sent to `query_data_usage`: labels and their values, measurement kinds, units, and request limits. Retain the response for the session and use only its returned options in the second tool.

#### `get_data_usage_capabilities` response

```json
{
  "supportedLabels": [
    {
      "key": "string",
      "keyDescription": "string",
      "highCardinality": true,
      "knownValues": [
        {
          "value": "string",
          "description": "string"
        }
      ]
    }
  ],
  "supportedMeasurements": [
    {
      "kind": "server-defined measurement kind",
      "description": "string",
      "unit": "server-defined raw unit"
    }
  ],
  "maxUsageEntriesPerMessage": "integer",
  "maxGroupByLabels": "integer",
  "maxFilters": "integer",
  "maxFilterValues": "integer"
}
```

#### `query_data_usage` request

```json
{
  "daily": {
    "relativeRange": "DAILY_RELATIVE_RANGE_CURRENT_MONTH | DAILY_RELATIVE_RANGE_PREVIOUS_MONTH | DAILY_RELATIVE_RANGE_CURRENT_YEAR | DAILY_RELATIVE_RANGE_LAST_7_DAYS | DAILY_RELATIVE_RANGE_LAST_14_DAYS | DAILY_RELATIVE_RANGE_LAST_30_DAYS | DAILY_RELATIVE_RANGE_LAST_90_DAYS | DAILY_RELATIVE_RANGE_LAST_180_DAYS | DAILY_RELATIVE_RANGE_LAST_365_DAYS",
    "dateRange": {
      "start": {"year": 2026, "month": 7, "day": 1},
      "end": {"year": 2026, "month": 7, "day": 8}
    }
  },
  "hourly": {
    "relativeRange": "HOURLY_RELATIVE_RANGE_LAST_12_HOURS | HOURLY_RELATIVE_RANGE_LAST_24_HOURS | HOURLY_RELATIVE_RANGE_LAST_48_HOURS | HOURLY_RELATIVE_RANGE_LAST_7_DAYS | HOURLY_RELATIVE_RANGE_LAST_14_DAYS",
    "timeRange": {
      "start": "2026-07-20T00:00:00Z",
      "end": "2026-07-21T00:00:00Z"
    }
  },
  "groupBy": {
    "keys": ["capabilities.supportedLabels[].key"]
  },
  "filters": [
    {
      "key": "capabilities.supportedLabels[].key",
      "operator": "FILTER_OPERATOR_IN | FILTER_OPERATOR_NOT_IN",
      "values": ["string"]
    }
  ],
  "measurementKindFilter": [
    "capabilities.supportedMeasurements[].kind"
  ],
  "limit": {
    "perBucket": 100
  }
}
```

Rules:
- Send exactly one of `daily` or `hourly`.
- Inside `daily`, send exactly one of `relativeRange` or `dateRange`. Daily date ranges are half-open `[start, end)` UTC dates.
- Inside `hourly`, send exactly one of `relativeRange` or `timeRange`. Hourly absolute timestamps must be RFC 3339 values with a timezone, resolve to the top of a UTC hour, use a half-open `[start, end)` interval with `end` after `start`, and span at most 14 days.
- `groupBy`, `filters`, `measurementKindFilter`, and `limit` are optional.
- When supplied, `limit.perBucket` must be a positive integer.
- All labels, filter values, measurement kinds, and limits must be validated against the capabilities response.

#### `query_data_usage` response

```json
{
  "queryRange": {
    "start": "RFC3339 UTC timestamp",
    "end": "RFC3339 UTC timestamp"
  },
  "buckets": [
    {
      "range": {
        "start": "RFC3339 UTC timestamp",
        "end": "RFC3339 UTC timestamp"
      },
      "entries": [
        {
          "labels": [
            {
              "key": "string",
              "value": "string"
            }
          ],
          "measurements": [
            {
              "kind": "a kind returned by supportedMeasurements",
              "measuredValue": "uint64 encoded as string",
              "measuredUnit": "the unit associated with that returned kind",
              "cxQuotaUnits": {
                "value": "decimal string"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

`queryRange` is the server-resolved interval. `buckets` are one UTC day or one UTC hour each. An entry represents one unique `groupBy` label combination. `measuredValue` is raw usage in `measuredUnit`; `cxQuotaUnits.value` is the billable amount.

#### Capabilities field → query field mapping

| `get_data_usage_capabilities` field | Use in `query_data_usage` |
| --- | --- |
| `supportedLabels[].key` | Use as a value in `groupBy.keys` or `filters[].key`. |
| `supportedLabels[].knownValues[].value` | Use as a value in `filters[].values` for that same label key. |
| `supportedLabels[].keyDescription` / `knownValues[].description` | Choose the correct label/value for the user's question; never send these description fields in the query. |
| `supportedLabels[].highCardinality` | No direct query field. Prefer a narrow filter and small `limit.perBucket` before grouping by a high-cardinality label. |
| `supportedMeasurements[].kind` | Use as a value in `measurementKindFilter`. |
| `supportedMeasurements[].unit` | No direct query field. Use it to interpret `measurements[].measuredValue` in the response. |
| `maxGroupByLabels` | Maximum number of entries in `groupBy.keys`. |
| `maxFilters` | Maximum number of objects in `filters`. |
| `maxFilterValues` | Maximum number of strings in each `filters[].values`. |
| `maxUsageEntriesPerMessage` | No direct query field. Keep `limit.perBucket` and grouping scope small enough to avoid an oversized response. |

This document teaches the LLM how to answer customer-facing data-usage questions using the customer metrics exporter as the primary source of truth.

The LLM must understand:

- what each exported metric means
- how raw measurements relate to billable units
- which labels can be used for breakdowns
- how to calculate totals, averages, deltas, trends, and plan consumption correctly

The LLM should optimize for correctness over guesswork. If a question is about billing, plan consumption, overage, or usage attribution, it should rely on exported metrics and their labels, not on assumptions.

## Core Business Model

### Units

`Units` are the internal billing unit Coralogix charges on.

When a customer signs a plan, they agree to a number of units per day. The USD price per unit is not relevant for this document.

For billing and plan-consumption questions, the canonical metric is:

- `cx_data_usage_units`

### Other Measurements

Customers also produce other raw measurements. These measurements are not the billing unit themselves, but they can be converted into units depending on business rules and metadata such as pillar, entity type, priority, and feature.

Examples:

- processed bytes
- evaluation tokens
- egress/system bytes
- metrics samples
- events

The important rule is:

- do not try to infer units from raw bytes, tokens, samples, or events unless explicitly required and a conversion table is available
- for actual billed or plan-consumed usage, prefer `cx_data_usage_units`

## Measurement Types

The business measurement families in scope are:

- `ProcessedDataSize`: processed bytes
- `Evaluation`: measured in tokens
- `EgressDataSize`: system bytes
- `ProcessedMetricsSamples`: metric samples
- `Events`: event counts

Implementation note:

- current code also contains `InfraMonitoringIngressEvents`, `ReceivedDataSize`, and `Tokens`
- for customer-facing metrics in this document, `InfraMonitoringIngressEvents` and `Events` should be treated as the infrastructure-events family
- `ReceivedDataSize` and `Tokens` are not part of the current billing metrics scope described here

## Source Of Truth

The LLM should use the customer metrics exporter output as the primary source for data usage answers.

Important behavior of the exporter:

- it exports usage from UTC midnight up to an export timestamp
- each exported point represents the cumulative total for the current UTC day at the time of export
- the series reset at midnight UTC (`00:00:00 UTC`)
- exporter logic aggregates usage for the day and publishes the current daily snapshot, not a per-interval increment

This means:

- an instant query during the day returns "today so far"
- a full-day total must be taken from the last sample of that UTC day, or an equivalent end-of-day snapshot
- the LLM must never subtract points across a midnight boundary as if the series were continuous across days

## Metric Naming In Queries

The exporter defines OTLP metric names such as `cx_data_usage` and `cx_data_usage_units`.

When these metrics are queried through Prometheus-style naming, the LLM must distinguish between:

- raw usage metrics that should be queried with the `_total` suffix
- metrics that should be queried without `_total`, even if they may still represent current-day accumulated values

Metrics that should use `_total` in Prometheus-style queries:

- `cx_data_usage_bytes_total`
- `cx_data_usage_tokens_total`
- `cx_system_data_sent_bytes_total`
- `cx_infrastructure_monitoring_events_total`
- `cx_data_usage_samples_total`

Metrics that should not use `_total`:

- `cx_data_usage_units`
- `cx_data_plan_units_per_day`
- `cx_data_usage_payg_units`

Important:

- `cx_data_usage_bytes_total` is the Prometheus-style query name for the exported metric `cx_data_usage`
- `cx_data_usage_units` stays `cx_data_usage_units`; it does not become `cx_data_usage_units_total`
- `cx_data_usage_units` still behaves like the other current-day accumulated usage metrics: it increases during the UTC day and resets at midnight UTC
- `cx_data_plan_units_per_day` is snapshot-like and should not use `_total`
- `cx_data_usage_payg_units` should also be queried without `_total`

### 1. `cx_data_usage_units`

Meaning:

- the canonical daily billable usage in units

Use when the user asks:

- how many units were consumed
- how much of the daily plan was used
- which pillar, feature, priority, or entity type consumed the most billable usage

Notes:

- this is the main metric for billing-style questions
- raw measurements may differ, but units are the normalized billing view
- the metric is exported with the usage dimensions of each underlying usage record, so it can be broken down by labels

### 2. `cx_data_plan_units_per_day`

Meaning:

- the customer's current daily plan quota in units

Use when the user asks:

- what is the daily plan
- what percentage of the plan was consumed
- how many units remain in the plan

Notes:

- this is exported as a snapshot-style metric
- each data point represents the daily plan that is in effect at that moment
- in the current implementation it is not exported with detailed breakdown labels like pillar or feature

Plan snapshot semantics:

- if a team starts the UTC day with a 50-unit daily plan, `cx_data_plan_units_per_day` will continuously report `50`
- if the plan is increased at `16:00 UTC` to `100` units per day, `cx_data_plan_units_per_day` will jump from `50` to `100`
- unlike cumulative usage metrics, this metric does not accumulate during the day and does not require delta calculations
- when answering "what was the plan at time T?", use the value of `cx_data_plan_units_per_day` at time `T`
- when answering "what is the current daily plan?", use the latest value of `cx_data_plan_units_per_day`

### 3. `cx_data_usage_payg_units`

Meaning:

- the customer's daily overage usage in units

Use when the user asks:

- how much PAYG / overage was consumed today
- how much usage exceeded the daily plan

Notes:

- this is only meaningful when PAYG is enabled
- in the current implementation it is not exported with detailed breakdown labels

### 4. `cx_data_usage`

Meaning:

- processed data size in bytes

Use when the user asks:

- how many processed bytes were consumed
- how raw processed bytes break down by pillar, entity type, priority, or feature

Notes:

- this is a raw measurement metric
- use it for byte-level analysis, not as the final answer for billing unless the user explicitly wants bytes

### 5. `cx_data_usage_tokens`

Meaning:

- AI evaluation tokens only

Use when the user asks:

- how many AI evaluation tokens were used
- which evaluators or AI-related traffic generated token usage

Notes:

- in current exporter behavior this corresponds to `measurement_type=evaluation`
- at the time of writing, this metric is only about AI evaluation tokens
- at the time of writing, this metric does not represent Olly tokens
- use `cx_data_usage_units` if the question is about how those tokens affected billing or plan consumption

### 6. `cx_system_data_sent`

Meaning:

- system egress bytes

Use when the user asks:

- how much system data was sent
- how much egress traffic was generated

Notes:

- this is a raw egress metric
- it is not the canonical source for plan-consumed units

### 7. `cx_data_usage_samples`

Meaning:

- processed metric samples

Use when the user asks:

- how many metric samples were processed

Notes:

- this is a raw measurement metric
- use `cx_data_usage_units` for billing-style answers

### 8. `cx_infrastructure_monitoring_events`

Meaning:

- infrastructure monitoring event count

Use when the user asks:

- how many infra monitoring events were ingested

Notes:

- depending on the producer path, the associated label may appear as `measurement_type=infra_monitoring_ingress_events` or as the more generic events family
- treat both as the same business concept for customer explanations

## Default Concept-To-Metric Mapping

Use these defaults when the user is vague:

- billing / plan usage / consumption / overage -> `cx_data_usage_units`, plus `cx_data_plan_units_per_day` and `cx_data_usage_payg_units` when relevant
- processed bytes / data volume / ingested data -> `cx_data_usage_bytes_total`
- AI evaluation tokens / evaluations -> `cx_data_usage_tokens_total`
- system bytes / egress -> `cx_system_data_sent_bytes_total`
- infra events -> `cx_infrastructure_monitoring_events_total`
- metric samples -> `cx_data_usage_samples_total`

Important token-scope rule:

- at the time of writing, `cx_data_usage_tokens_total` means AI evaluation tokens only
- do not use `cx_data_usage_tokens_total` for Olly tokens unless the metric definition changes in the future

If the user asks for both raw usage and billing effect, answer with both:

- raw measurement metric for scale
- `cx_data_usage_units` for billing impact

## Labels And Dimensions

### Mandatory breakdown dimensions

For usage metrics that support breakdowns, the LLM should expect these core dimensions:

- `pillar`
- `entity_type`
- `priority`
- `measurement_type`
- `feature_group_id`
- `feature_id`

### Optional user-provided dimensions

- `application_name`
- `subsystem_name`

### Optional system-derived dimensions

- `tco_policy_id`
- `tco_policy_name`
- `severity`
- `evaluator_name`
- `evaluator_version`
- `data_set`
- `data_space`
- `cx_source`
- other system labels depending on the data type and exporter path

### Exporter normalization behavior

The metrics exporter normalizes some optional labels for dashboard stability:

- missing `application_name` may be exported as `cx_null`
- missing `subsystem_name` may be exported as `cx_null`
- missing `severity` may be exported as `cx_null`

For blocked processed-data traffic, the exporter may also derive:

- `blocking_reason_name`
- `blocking_reason_type`

These are helpful when a user asks why traffic was blocked or which policy caused blocked usage.

### Label availability rule

Not every label exists on every metric or every record.

The LLM must:

- treat the mandatory dimensions above as the main grouping dimensions for usage breakdowns
- only use optional dimensions when they are actually present
- treat `cx_null` as "label not set" rather than as a meaningful customer value
- avoid assuming that all entity types support all priorities

## Business Semantics Of Key Dimensions

### Pillar

The high-level product/data domain, for example:

- `logs`
- `spans`
- `binary`
- `metrics`

### Entity Type

A subtype within a pillar, for example:

- `logs`
- `browser_logs`
- `spans`
- `session_recordings`

This is more specific than pillar and is often the right level for customer attribution.

### Priority

Traffic priority, such as:

- `high`
- `medium`
- `low`
- `blocked`

Not every entity type has every priority combination.

### Measurement Type

The raw measurement family, such as:

- processed bytes
- tokens
- egress bytes
- samples
- events

### Feature

`feature_id` and `feature_group_id` identify the product capability or business area responsible for the usage. These are important for questions like:

- which feature caused the most usage
- how much usage belongs to logs vs AI vs metrics

## Calculation Rules

These rules are mandatory for the LLM.

### 1. Current-day total

For any usage metric, an instant value queried during a UTC day means:

- total accumulated since `00:00:00 UTC` of the current day up to query time

Example:

- `sum(cx_data_usage_units)` at `2026-03-12 15:00 UTC` means total units consumed on `2026-03-12` from midnight until `15:00 UTC`

### 2. Completed-day total

For a completed UTC day, the correct daily total is:

- the last value observed before the next midnight UTC

Safe interpretation:

- use the end-of-day sample when available
- if end-of-day sampling is incomplete, the maximum value observed within that UTC day is usually a safe fallback because the series represent cumulative daily snapshots

Default rule:

- for comparisons, averages, trend analysis, and anomaly detection, usually exclude the current UTC day because it is partial
- only include the current UTC day when the user explicitly asks for "today so far", "current status", or another partial-day view
- if the current UTC day is excluded, say so explicitly and explain that it was excluded because it is partial and would distort completed-day comparisons

### 3. Delta within the same day

To compute a delta between two times on the same UTC day:

- `delta = value_at_t2 - value_at_t1`

Constraints:

- both timestamps must be inside the same UTC day
- both values must use the same label scope
- if the subtraction becomes negative, check whether a UTC midnight reset was crossed or the wrong label set was used

### 4. Delta across days

Never subtract two arbitrary samples across a UTC midnight boundary as if the series were continuous.

Instead:

- compute each day independently
- compare completed-day totals

Good:

- compare `total(2026-03-11)` vs `total(2026-03-10)`

Bad:

- `value(2026-03-11 00:05 UTC) - value(2026-03-10 23:55 UTC)`

### 5. Average daily usage

To compute average daily usage across multiple days:

- first compute one completed-day total per UTC day
- then average those daily totals

Do not:

- average intra-day snapshots directly
- average mixed partial-day and full-day samples unless the user explicitly asked for "average so far"

### 6. Remaining daily plan

Use:

- `remaining_units = max(plan_units_per_day - current_usage_units, 0)`

Where:

- `plan_units_per_day = cx_data_plan_units_per_day`
- `current_usage_units = sum(cx_data_usage_units)`

Important:

- `cx_data_plan_units_per_day` is a snapshot metric, so use the plan value that was valid at the time of the comparison
- if the plan changes mid-day, do not assume the earlier and later parts of the day had the same quota snapshot

### 7. Plan-consumption percentage

Use:

- `consumed_percent = 100 * current_usage_units / plan_units_per_day`

If plan is missing or zero:

- do not invent a percentage
- say that the plan quota metric is unavailable

### 8. Overage / PAYG

Use:

- `cx_data_usage_payg_units`

Interpretation:

- the amount of daily usage that exceeded the included daily plan

If the user asks for "did we exceed the plan?":

- compare `sum(cx_data_usage_units)` with `cx_data_plan_units_per_day`
- if available, also report `cx_data_usage_payg_units` as the overage amount

## Anomaly Detection

The LLM should support anomaly detection, but it must do so conservatively and with explicit comparison logic.

### Scope

For anomaly detection, focus on actual usage metrics only:

- `cx_data_usage_units`
- `cx_data_usage_bytes_total`
- `cx_data_usage_tokens_total`
- `cx_system_data_sent_bytes_total`
- `cx_infrastructure_monitoring_events_total`
- `cx_data_usage_samples_total`

Exclude these from normal usage-anomaly detection:

- `cx_data_plan_units_per_day`
- `cx_data_usage_payg_units`

Reason:

- `cx_data_plan_units_per_day` is a plan snapshot, not usage
- `cx_data_usage_payg_units` is derived overage state, not the primary usage signal

### Default comparison strategy

The default anomaly strategy should be completed-day based.

The LLM should usually:

- exclude the current UTC day because it is partial
- compare completed UTC days to other completed UTC days
- prefer seasonality-aware baselines when the customer has weekday/weekend patterns

Only use current-day anomaly analysis when the user explicitly asks for it.

### Metric selection by user intent

Pick the anomaly metric that matches the user's requested concept:

- units anomaly -> `cx_data_usage_units`
- bytes anomaly -> `cx_data_usage_bytes_total`
- AI evaluation tokens anomaly -> `cx_data_usage_tokens_total`
- system egress anomaly -> `cx_system_data_sent_bytes_total`
- infra events anomaly -> `cx_infrastructure_monitoring_events_total`
- metrics samples anomaly -> `cx_data_usage_samples_total`

The LLM should not silently switch metric families. Use the default concept-to-metric mapping above if the user is vague.

### Recommended anomaly method

When the user asks for anomalies, the LLM should describe both:

- whether an anomaly exists
- what comparison method would best explain it

Recommended default method:

- build a baseline from comparable completed UTC days
- prefer same-weekday comparisons when customer traffic is seasonal
- if weekday seasonality is not relevant or history is limited, use a recent completed-day baseline
- compare the selected day to the baseline in relative and absolute terms

Because there are no fixed thresholds in this document:

- the LLM should avoid hard-coded anomaly thresholds
- the LLM should explain that anomaly judgment depends on historical variability

### Root-cause breakdown order

When an anomaly is found, the LLM should break it down in this order:

- `measurement_type`
- `pillar`
- `entity_type`
- `priority`
- `feature_group_id`
- `feature_id`
- `application_name`
- `subsystem_name`

The goal is to explain not just that usage changed, but which slice of usage changed.

### What the LLM should suggest

The LLM should suggest the most useful next comparison for the specific anomaly.

Examples:

- if units are anomalous, suggest checking whether the increase is concentrated in a specific `measurement_type`, `priority`, or `feature_group_id`
- if bytes are anomalous, suggest checking whether the spike is isolated to one `pillar` or `entity_type`
- if AI tokens are anomalous, suggest checking whether one evaluator-related slice drove the increase
- if seasonality may matter, suggest comparing against equivalent weekdays instead of adjacent calendar days

### Plan changes

Plan changes are not usage anomalies by default.

The LLM should treat plan changes as:

- expected state changes unless they happen unusually often

This means:

- do not flag a single jump in `cx_data_plan_units_per_day` as a usage anomaly
- if the user asks about repeated or frequent plan changes, the LLM may describe that pattern as unusual state behavior

### Partial-day caution

If the user asks for anomaly detection including today:

- clearly state that the current UTC day is partial
- compare today-so-far only against historical values from the same point-in-day whenever possible
- make clear that a partial-day anomaly is less reliable than a completed-day anomaly

### Suggested language

The LLM should use language like:

- "Compared with recent completed UTC days, this looks unusual."
- "This appears to be driven mainly by `measurement_type=...` and `feature_group_id=...`."
- "Because today is still in progress, this should be treated as a provisional anomaly assessment."
- "This may reflect seasonality, so a same-weekday comparison is more reliable than a simple day-over-day comparison."

## Unpacking Vague Time-Series Requests

Users will often ask vague questions such as:

- "Show me data usage over the last 5 months"
- "Give me weekly usage by pillar and priority"
- "Are there anomalies in usage?"
- "Break down data usage over time by feature"

The mission of the LLM is to unpack these into a concrete analysis plan before answering.

### Default unpacking checklist

For any request of the form "data usage over X time, aggregated by Y, anomalies", the LLM should make these choices explicit:

- which usage concept is being analyzed
- which metric maps to that concept
- which time bucket is being used
- whether partial periods are excluded
- which grouping labels are used
- whether deltas are absolute, percentage, or both
- how anomalies are being judged

### Metric choice by concept

Use the default concept-to-metric mapping above.

If the user does not specify the concept clearly, the LLM should not silently change between units and bytes. It should either:

- state the assumption it is using
- or ask a clarification question if the distinction materially changes the answer

### Time-bucket rule

When the user asks for aggregation by:

- day -> use completed UTC days
- week -> build weekly totals from completed UTC days
- month -> build monthly totals from completed UTC days
- hour -> treat this as partial-day / intraday analysis and warn accordingly

Important:

- weekly and monthly answers should not be derived directly from raw day-cumulative series
- the LLM should first derive completed daily totals, then roll those daily totals up into weeks or months

### Partial-period rule

Unless the user explicitly asks for a partial period:

- exclude the current UTC day
- exclude the current week if the requested output is weekly
- exclude the current month if the requested output is monthly
- say this clearly in the response and explain that partial periods distort completed-period comparisons

### Delta rule

When the user asks for "deltas", the LLM should default to:

- absolute delta for the requested bucket
- percentage delta for the requested bucket

If only one is shown, the LLM should say which one it chose.

### Analysis-plan phrasing

For vague requests, the LLM should translate the ask into wording like:

- "I will use `cx_data_usage_units`, derive completed daily UTC totals, roll them into completed UTC weeks, group by `pillar` and `priority`, and compute week-over-week deltas."

This removes ambiguity before presenting findings.

## Unsafe Query Patterns And Why They Fail

The LLM must avoid query patterns that look plausible but do not match the requested bucket semantics.

### Unsafe pattern: direct `max_over_time(...[1d])` for weekly analysis

Example:

- `sum by (pillar, priority) (max_over_time(cx_data_usage_units[1d]))`

Why this is unsafe:

- it returns a rolling 1-day maximum, not a completed weekly total
- the result depends on evaluation time
- if evaluated mid-day, the 1-day window can span parts of two UTC days
- by itself, it does not produce a week-by-week time series
- it does not explicitly exclude the current partial UTC day

### Unsafe pattern: dropping grouping too early

Example:

- `sum(max_over_time(cx_data_usage_units[1d]))`

Why this is unsafe:

- it removes `pillar` and `priority` before analysis
- it prevents correct root-cause breakdown by slice
- it still has the same rolling-window problem as the grouped version

### Required pattern for weekly or monthly usage

For weekly or monthly usage analysis, the LLM should reason in this order:

1. select the correct metric
2. derive completed daily UTC totals
3. aggregate those daily totals into the requested bucket
4. compute deltas between completed buckets
5. perform anomaly analysis on those completed buckets

The LLM should not jump straight from a current-day accumulated series to weekly or monthly conclusions.

## Response Quality Rules For Usage And Anomaly Answers

When answering usage-over-time or anomaly questions, the LLM should always make these points explicit:

- which metric was used
- which bucket was used
- whether current partial periods were excluded
- which grouping labels were used
- whether the anomaly analysis is completed-period or partial-period

### Do not overstate precision

The LLM should not present rough heuristics as if they were computed facts.

It should not write things like:

- "about 900-1,000 units/week"
- "week-over-week deltas mostly within +-5%"

unless those numbers were actually computed from the chosen metric and bucket definition.

### Separate observation from hypothesis

The LLM should distinguish between:

- observed metric behavior
- likely explanation

Good:

- "Weekly units dropped relative to the prior completed weeks."
- "The drop is concentrated in `measurement_type=...` and `pillar=...`."
- "A configuration or policy change is one possible explanation, but that is not proven by this metric alone."

Bad:

- "This was caused by a TCO change."

unless the underlying breakdown actually shows that.

### Prefer completed-bucket findings

For anomaly answers, the LLM should prefer statements like:

- "Completed UTC weeks are stable except for one positive spike."
- "Completed UTC days suggest a temporary spike rather than a sustained upward trend."

This is better than mixing partial-day and completed-day interpretations in one summary.

## Query Execution

This skill covers what to query and how to interpret results. Use the Data Usage Query API for billing answers. For PromQL-only analysis, load [`metrics-query`](skill://metrics-query/SKILL.md).

Quick reference for data-usage queries:

- **Billable totals, breakdowns, plan consumption, or quota** → `get_data_usage_capabilities`, then `query_data_usage`
- **PromQL metric monitoring or correlation with other metrics** → `query_promql_instant` / `query_promql_range`
  - Align `start` and `end` to UTC midnight (`00:00:00 UTC`). Do not use floating `now-7d..now` windows for daily, weekly, or monthly totals.
  - For completed-day/week/month totals and anomaly analysis, set `end` to the most recent completed UTC midnight (exclude the current partial day) unless the user explicitly wants "today so far".
- **Metric discovery** (verify a metric exists or explore its labels) → `search_relevant_metrics` / `get_metric_labels`

## How The LLM Should Answer Common Questions

### "How many units have we used today?"

Use:

- `sum(cx_data_usage_units)`

Answer as:

- today's units so far, in UTC-day semantics

### "What is our daily plan and how much is left?"

Use:

- `cx_data_plan_units_per_day`
- `sum(cx_data_usage_units)`
- optionally `cx_data_usage_payg_units`

Answer with:

- plan units
- used units today
- remaining units before overage
- PAYG units if already exceeded

### "Which feature is driving usage?"

Use:

- `sum by (feature_group_id, feature_id) (cx_data_usage_units)`

Answer with:

- the top feature groups or features by units

### "How much logs usage do we have today?"

Use:

- `sum(cx_data_usage_units{pillar="logs"})` for billing impact
- `sum(cx_data_usage_bytes_total{pillar="logs"})` for raw processed bytes

Answer with:

- units if the user cares about plan/billing
- bytes if the user cares about raw ingestion volume

### "How many AI evaluation tokens were used?"

Use:

- `sum(cx_data_usage_tokens_total)`

If the user also asks how that affected billing:

- add `sum(cx_data_usage_units{measurement_type=\"evaluation\"})`

### "How did today compare with yesterday?"

If the question is about usage totals:

- compare today's current partial total with yesterday's total only if you clearly say "today so far vs full yesterday"
- otherwise compare completed-day totals for both days

The LLM must make the comparison basis explicit.

## Interpretation Guardrails

The LLM must follow these rules:

- never treat bytes, tokens, samples, or events as billable units unless using `cx_data_usage_units`
- never compare values across UTC days without accounting for the midnight reset
- never assume optional labels exist on every series
- never assume all priorities are valid for all entity types
- never mix customers; queries must stay scoped to the relevant customer exporter or tenant scope
- when a user asks for "usage", prefer clarifying whether they want raw measurement or billable units, unless context already makes it obvious

## Known Naming Gaps To Keep In Mind

There are a few naming differences between business language and implementation:

- business conversations may say `events`, while current metric labels may use `infra_monitoring_ingress_events`
- internal code contains more enum variants than the current customer-facing metrics scope

The LLM should normalize these differences when reasoning, but should preserve the actual metric and label names when generating queries.