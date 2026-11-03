---
name: honeycomb-metrics-queries
description: 'Load before querying a Honeycomb OpenTelemetry metrics dataset (dataset_type=metrics): gauges, counters, histograms and sums, including infrastructure metrics such as CPU, memory, disk I/O and network. Metrics follow different rules from trace datasets: bare COUNT, RATE_SUM, RATE_AVG, RATE_MAX and CONCURRENCY are rejected, temporal aggregation is automatic, and each metric has its own attributes. Not for event datasets that only have metrics in their name.'
metadata:
  author: "honeycombio/agentic-intelligence"
  version: "1.0.0"
  summary: "Query Honeycomb OpenTelemetry metrics datasets with the right temporal and spatial aggregation."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Querying Metrics in Honeycomb

Requires the Honeycomb connector in the Agent Space, with its read tools enabled.

Metrics datasets in Honeycomb behave differently from tracing/event datasets.
Operations that work on traces may fail or produce misleading results on metrics.
This skill covers those differences so you construct correct, useful metrics queries.

## Finding the Metrics Dataset

Metrics datasets are **not** identified by having "metrics" in their name. Many event
datasets contain "metrics" in their slug (e.g., `kafka-metrics`, `refinery-metrics`,
`kubernetes-node-metrics`). These are ordinary event datasets, not metrics datasets.

**How to identify the real metrics dataset:**

1. Call `get_environment` and look for rows where `dataset_type` = **`metrics`**.
   The slug is typically `metrics` but may differ per environment.
2. Alternatively, call `get_dataset_columns` on a candidate dataset — metrics datasets
   return a **`MetricInfo`** column showing type metadata like `gauge`,
   `sum(cumulative,monotonic)`, or `histogram(delta)`. Event datasets do not have this.

**Do not guess the dataset.** Always verify via `get_environment` or `get_dataset_columns`
before constructing a metrics query. If the user says "metrics" but means an event dataset
with metrics-like fields (e.g., `telegraf`, `system_stats`), the query rules below do not apply —
those are event datasets and follow normal query patterns from the **honeycomb-query-patterns** skill.

## Discovering Metrics and Their Attributes

Metrics datasets have a fundamentally different schema from event datasets. Each metric
has its own set of resource and data point attributes. Two metrics in the same dataset
may have completely different attributes available for filtering and grouping.

**Workflow for discovering what to query:**

1. **Find metric names:** Call `get_dataset_columns` on the metrics dataset (without
   `metric_name`). This returns metric names with their types in `MetricInfo`.
   Use `find_columns` with keywords to search for specific metrics (e.g., "cpu", "memory",
   "http request duration").

2. **Find attributes for a specific metric:** Call `get_dataset_columns` with the
   `metric_name` parameter set to the metric you want to query (e.g.,
   `metric_name: "k8s.pod.memory.usage"`). This returns the resource attributes and
   data point attributes that co-occur with that metric, along with sample values.
   These are what you can use in WHERE and GROUP BY clauses.

3. **Validate before querying:** Not all attributes exist on all metrics. Always use
   step 2 to confirm available attributes before adding them to filters or breakdowns.

## Allowed vs. Forbidden Operations on Metrics Datasets

The following operations are **NOT allowed** on metrics datasets:

| Forbidden Operation | Why |
|---------------------|-----|
| `COUNT` (without column) | Counts metric events, not metric values — meaningless for metrics |
| `RATE_SUM` | Not supported on metrics datasets |
| `RATE_AVG` | Not supported on metrics datasets |
| `RATE_MAX` | Not supported on metrics datasets |
| `CONCURRENCY` | Requires span duration; metrics have no duration |

**Use these instead:**

| Goal | Use on Metrics |
|------|----------------|
| Visualize a gauge value | `AVG(metric)`, `MAX(metric)`, `HEATMAP(metric)` |
| Visualize a counter/sum | `SUM(metric)`, `AVG(metric)`, `MAX(metric)` |
| See distribution of values | `HEATMAP(metric)`, `P50(metric)`, `P99(metric)` |
| Track per-second rate of change | Override temporal aggregation with a calculated field (see below) |
| Percentile analysis | `P50(metric)`, `P90(metric)`, `P99(metric)` |
| Count of non-null values | `COUNT(metric)` (with a column specified) |

## Metric Types and Temporal Aggregation

Honeycomb automatically applies temporal aggregation to align raw metric values into
query time steps. The function it applies depends on the metric type, visible in the
`MetricInfo` column from `get_dataset_columns`.

### Default Temporal Aggregation by Metric Type

| MetricInfo | Type | Default Function | What It Does |
|------------|------|-----------------|--------------|
| `gauge` | Gauge | `LAST()` | Returns most recent value per time step |
| `sum(cumulative,monotonic)` | Monotonic cumulative sum | `INCREASE()` | Change between steps, handles counter resets |
| `sum(cumulative)` | Non-monotonic cumulative sum | `LAST()` | Most recent value (can go up or down) |
| `sum(delta)` or `sum(delta,monotonic)` | Delta sum | `SUMMARIZE()` | Sums all values in each step |
| `histogram(cumulative)` | Cumulative histogram | `INCREASE()` | Change per bucket between steps |
| `histogram(delta)` | Delta histogram | `SUMMARIZE()` | Sums bucket values in each step |

These defaults are applied automatically — you do not need to configure them.
The results you see from `AVG`, `MAX`, `P99`, etc. on a metrics dataset already
reflect temporal aggregation having been applied first.

### Overriding Temporal Aggregation

To override the default (e.g., to see RATE instead of INCREASE for a cumulative counter),
use a **query-scoped calculated field** wrapping the metric name in a temporal aggregation
function, then apply a spatial aggregation to that field in `calculations`.

```json
{
  "calculated_fields": [
    { "name": "req_rate", "expression": "RATE($http.server.requests, 300)" }
  ],
  "calculations": [
    { "op": "AVG", "column": "req_rate" }
  ]
}
```

Supported temporal aggregation functions for calculated fields:
- **`LAST($metric)`** — most recent data point per step (gauges, non-monotonic sums)
- **`SUMMARIZE($metric)`** — sum all values per step with interpolation (delta metrics)
- **`INCREASE($metric[, range_interval_seconds])`** — change in value across range, handles counter resets
- **`RATE($metric[, range_interval_seconds])`** — per-second rate of change (`INCREASE / time`)

The optional `range_interval_seconds` parameter (integer, in seconds) controls the lookback
window for calculating changes. Use it to smooth results or compensate for sparse data.
When omitted, the query's granularity is used as the range interval.

**Important:** You must still apply a spatial aggregation (`AVG`, `SUM`, `P99`, `HEATMAP`, etc.)
to the calculated field in `calculations`. The temporal aggregation function alone does not
produce a visualization — it transforms the raw metric values, then the spatial aggregation
summarizes across timeseries.

For detailed reference on temporal aggregation functions, counter reset handling, and
`range_interval_seconds`, see:
`references/temporal-aggregation.md`

## Querying Histogram Metrics

OpenTelemetry histograms are stored as a collection of sub-fields. For a histogram
named `http.server.duration`, Honeycomb creates:

| Field | Meaning |
|-------|---------|
| `http.server.duration.count` | Total number of data points |
| `http.server.duration.sum` | Sum of all values |
| `http.server.duration.avg` | Mean value (sum/count) |
| `http.server.duration.p50` | Median (50th percentile) |
| `http.server.duration.p99` | 99th percentile |
| `http.server.duration.p001` through `.p999` | Full range of percentiles |

**Two ways to query histograms:**

1. **Use the parent column name directly** with percentile or distribution operations.
   This is the recommended approach:
   ```json
   { "op": "P99", "column": "http.server.duration" }
   ```
   ```json
   { "op": "HEATMAP", "column": "http.server.duration" }
   ```

2. **Use sub-fields with MAX** when you want the worst-case pre-computed percentile
   across all timeseries in a step:
   ```json
   { "op": "MAX", "column": "http.server.duration.p99" }
   ```
   This returns the highest p99 value reported by any single timeseries in the time step,
   which differs from `P99(http.server.duration)` which computes the 99th percentile
   across all data.

**When to use which:**
- For most analysis: use `P99(parent_column)` or `HEATMAP(parent_column)`
- For worst-case bounds across hosts/pods: use `MAX(parent_column.p99)`
- For throughput from histograms: use `SUM(parent_column.count)` or `AVG(parent_column.count)`

## Query Math with Metrics

Query math (compound queries with named calculations and formulas) works on metrics
datasets the same way it works on event datasets. Name your calculations, add
per-calculation filters if needed, and define formulas to combine them.

**Common metrics formula patterns:**

### Utilization percentage
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.memory.usage", "name": "used" },
    { "op": "AVG", "column": "k8s.pod.memory.available", "name": "available" }
  ],
  "formulas": [
    { "name": "utilization_pct", "expression": "$used / ($used + $available) * 100" }
  ],
  "breakdowns": ["k8s.pod.name"],
  "orders": [{ "column": "utilization_pct", "order": "descending" }],
  "limit": 20
}
```

### Histogram tail ratio
```json
{
  "calculations": [
    { "op": "P50", "column": "http.server.duration", "name": "median" },
    { "op": "P99", "column": "http.server.duration", "name": "tail" }
  ],
  "formulas": [
    { "name": "tail_ratio", "expression": "$tail / $median" }
  ],
  "breakdowns": ["service.name"]
}
```

### Error rate from counters (with temporal aggregation override)
```json
{
  "calculated_fields": [
    { "name": "error_rate", "expression": "RATE($http.server.errors)" },
    { "name": "request_rate", "expression": "RATE($http.server.requests)" }
  ],
  "calculations": [
    { "op": "SUM", "column": "error_rate", "name": "errors_per_sec" },
    { "op": "SUM", "column": "request_rate", "name": "requests_per_sec" }
  ],
  "formulas": [
    { "name": "error_pct", "expression": "$errors_per_sec / $requests_per_sec * 100" }
  ]
}
```

For more query examples, see:
`references/metrics-query-examples.md`

## Granularity for Metrics

Metrics arrive at known, regular intervals (e.g., every 10s, 30s, or 60s). Granularity
matters more for metrics than for traces:

- **Align granularity with the reporting interval.** If metrics report every 60 seconds,
  use a granularity that divides evenly into 60 (e.g., 60, 120, 300). Misaligned
  granularity causes uneven bucket sizes that produce noisy results.
- **Spiky-looking graphs** usually mean the granularity is finer than the reporting interval.
  Increase granularity or, in the UI, enable "Omit Missing Values" to produce continuous lines.
- **RATE operations and granularity:** `RATE_SUM` (on event datasets) is particularly sensitive
  to granularity choice — inconsistent data points per bucket produce variable results.

## Common Pitfalls

1. **Using `COUNT` on metrics.** `COUNT` counts the number of metric *events*, not the metric
   value. Use `AVG`, `SUM`, `MAX`, or `HEATMAP` instead.
2. **Using `RATE_AVG`/`RATE_SUM`/`RATE_MAX` on metrics datasets.** These are not allowed.
   To get a rate, use a calculated field with `RATE($metric)` and then apply a spatial
   aggregation like `AVG` or `SUM`.
3. **Assuming all metrics share the same attributes.** Each metric has its own set of
   resource and data point attributes. Always call `get_dataset_columns` with `metric_name`
   to discover what's available for a specific metric before adding filters or breakdowns.
4. **Confusing event datasets with the metrics dataset.** Datasets named `kafka-metrics`,
   `refinery-metrics`, etc. are event datasets. Check `dataset_type` from `get_environment`.
5. **Querying histogram sub-fields when the parent column works.** Use `P99(http.server.duration)`
   rather than `AVG(http.server.duration.p99)` unless you specifically need worst-case bounds.
6. **Not specifying an aggregate function.** Metrics queries without a spatial aggregation
   in SELECT default to `COUNT`, which is meaningless for metrics.

## Additional Resources

### Reference Files
- **`references/metrics-query-examples.md`** — Metrics query cookbook with run_query examples for common scenarios
- **`references/temporal-aggregation.md`** — Deep reference on temporal aggregation functions, counter resets, and range_interval_seconds
- **`references/metric-types.md`** — OpenTelemetry metric types, how they map to Honeycomb, and what the MetricInfo values mean

### Cross-References
- For general query construction patterns (calculated fields, relational fields, result interpretation): **honeycomb-query-patterns** skill
- For investigating production issues using metrics alongside traces: **honeycomb-production-investigation** skill
- For SLO interpretation and burn alert design: **honeycomb-slos-and-triggers** skill
