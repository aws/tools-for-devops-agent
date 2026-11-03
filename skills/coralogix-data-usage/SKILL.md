---
name: coralogix-data-usage
description: Data usage, billing units, plan consumption, quota metrics, anomaly detection, and time-series analysis concepts and query workflow. Load when the user asks about data usage, ingestion volumes, billing, plan limits, overage, quota attribution, usage anomalies, or usage trends over time.
metadata:
  summary: "Analyze Coralogix data usage, billing units, quotas, anomalies, and consumption trends."
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT"
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

See [the metric catalog](references/metrics.md) for Prometheus query names, metric meanings, and the default concept-to-metric mapping.

## Labels And Dimensions

See [the labels and dimensions reference](references/dimensions.md) before choosing breakdowns or filters.

## Calculation Rules

See [the calculation rules](references/calculation-rules.md) for daily totals, deltas, plan consumption, and PAYG interpretation.

## Anomaly Detection

See [the anomaly-detection guidance](references/anomaly-detection.md) for metric selection, baselines, breakdowns, and partial-day cautions.

## Unpacking Vague Time-Series Requests

See [the time-series request guidance](references/time-series-requests.md) for bucket selection, partial-period handling, and analysis plans.

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

This skill covers what to query and how to interpret results. Use the Data Usage Query API for billing answers. For PromQL-only analysis, load [`coralogix-metrics-query`](skill://coralogix-metrics-query/SKILL.md).

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