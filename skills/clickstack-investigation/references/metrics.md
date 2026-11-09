# Querying ClickStack metrics

ClickStack stores OpenTelemetry metrics by kind: gauge, sum, histogram, exponential histogram and summary. Each kind is a separate table, and the same metric name can exist in more than one kind.

## Discover before querying

1. `clickstack_describe_source` on the metric source returns a sample of metric names per kind.
2. `clickstack_list_metrics` pages through the full catalog. Filter by kind or name pattern, and pass `nextCursor` back unchanged for the next page.
3. `clickstack_describe_metric` with the metric name and its `kind` returns the attribute keys and sampled values for that metric. Attribute keys differ per metric, so call it before grouping or filtering on a metric you haven't queried yet.

## Query with clickstack_timeseries or clickstack_table

Every `select` item on a metric source must set `metricType` and `metricName`. `valueExpression` defaults to `Value`.

| Kind | Use |
|---|---|
| gauge | `last_value`, `avg`, `min` or `max` |
| sum (counters) | `aggFn: "increase"` for the counter increase per bucket. With `groupBy`, only the top 20 groups are returned |
| histogram, exponential histogram | `aggFn: "quantile"` with `level` (`0.5`, `0.9`, `0.95`, `0.99`) for percentiles, or `count` |
| summary | Not supported by the query tools. Use `clickstack_sql` against the table named in the source's `metricTables.summary` |

Example, p99 HTTP server latency by service:

```json
{
  "select": [{
    "aggFn": "quantile",
    "level": "0.99",
    "metricType": "histogram",
    "metricName": "http.server.request.duration",
    "alias": "p99 latency"
  }],
  "groupBy": "ServiceName",
  "granularity": "1 minute"
}
```

## Runtime metrics for a flagged service

When a service is flagged, check its own resources before blaming a dependency. Look for metrics such as:

- CPU and memory: `container.cpu.usage`, `container.memory.usage`, `process.runtime.*`
- Restarts: `k8s.container.restarts`
- Garbage collection and thread or connection pools, named by the language runtime

Names depend on the collector and instrumentation the customer runs. Find them with `clickstack_list_metrics` rather than assuming them.

## Granularity

`granularity` takes a number and a full unit name: `"1 minute"`, `"5 minute"`, `"1 hour"`. Abbreviations such as `"5m"` are rejected. Omit it to let ClickStack choose from the window.
