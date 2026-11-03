# Metrics Query Examples

Organized by use case. Each example shows the `run_query` parameter format
for querying metrics datasets. All examples assume `dataset_slug: "metrics"` —
verify the actual slug via `get_environment` (look for `dataset_type: metrics`).

## Discovery Workflow

Before querying, discover what metrics exist and what attributes they have.

### Step 1: Find available metrics
Use `get_dataset_columns` without `metric_name` to browse metric names and types:
```
get_dataset_columns(environment_slug="prod", dataset_slug="metrics")
```
Or search for specific metrics with `find_columns`:
```
find_columns(environment_slug="prod", dataset_slug="metrics", input="cpu utilization")
```

### Step 2: Find attributes for a specific metric
Use `get_dataset_columns` with `metric_name` to discover filterable/groupable attributes:
```
get_dataset_columns(environment_slug="prod", dataset_slug="metrics", metric_name="k8s.pod.cpu_limit_utilization")
```
This returns resource attributes (like `k8s.namespace.name`, `k8s.pod.name`) and data point
attributes with sample values.

## Infrastructure Monitoring

### CPU utilization by pod
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.cpu_limit_utilization" },
    { "op": "MAX", "column": "k8s.pod.cpu_limit_utilization" }
  ],
  "breakdowns": ["k8s.pod.name"],
  "orders": [{ "op": "MAX", "column": "k8s.pod.cpu_limit_utilization", "order": "descending" }],
  "limit": 20,
  "time_range": "1h"
}
```

### Memory usage by node
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.memory.usage" },
    { "op": "HEATMAP", "column": "k8s.pod.memory.usage" }
  ],
  "breakdowns": ["k8s.node.name"],
  "time_range": "6h"
}
```

### Memory utilization percentage (query math)
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
  "limit": 20,
  "time_range": "1h"
}
```

### Disk I/O over time (cumulative monotonic counter)

`system.disk.io` is a `sum(cumulative,monotonic)` — temporal aggregation automatically
applies `INCREASE()` to show the change per step, not the raw cumulative total.

```json
{
  "calculations": [
    { "op": "SUM", "column": "system.disk.io" }
  ],
  "breakdowns": ["k8s.node.name"],
  "time_range": "6h"
}
```

### Network packet drops (cumulative counter)
```json
{
  "calculations": [
    { "op": "SUM", "column": "system.network.dropped" }
  ],
  "breakdowns": ["k8s.node.name"],
  "time_range": "6h"
}
```

### Filesystem usage by node
```json
{
  "calculations": [
    { "op": "AVG", "column": "system.filesystem.usage" },
    { "op": "MAX", "column": "system.filesystem.usage" }
  ],
  "breakdowns": ["k8s.node.name"],
  "time_range": "24h"
}
```

## Application Metrics

### HTTP request duration distribution (histogram)
```json
{
  "calculations": [
    { "op": "HEATMAP", "column": "http.server.duration" },
    { "op": "P99", "column": "http.server.duration" },
    { "op": "P50", "column": "http.server.duration" }
  ],
  "time_range": "1h"
}
```

### HTTP duration by service (histogram with breakdown)
```json
{
  "calculations": [
    { "op": "P99", "column": "http.server.duration" },
    { "op": "AVG", "column": "http.server.duration" }
  ],
  "breakdowns": ["service.name"],
  "orders": [{ "op": "P99", "column": "http.server.duration", "order": "descending" }],
  "limit": 20,
  "time_range": "1h"
}
```

### Histogram tail ratio (query math)
```json
{
  "calculations": [
    { "op": "P50", "column": "http.server.duration", "name": "median" },
    { "op": "P99", "column": "http.server.duration", "name": "tail" },
    { "op": "AVG", "column": "http.server.duration", "name": "avg" }
  ],
  "formulas": [
    { "name": "tail_ratio", "expression": "$tail / $median" }
  ],
  "breakdowns": ["service.name"],
  "orders": [{ "column": "tail_ratio", "order": "descending" }],
  "limit": 20,
  "time_range": "1h"
}
```

### Worst-case p99 across hosts (histogram sub-field)
Use `MAX` on the pre-computed sub-field to find the single worst-reporting timeseries:
```json
{
  "calculations": [
    { "op": "MAX", "column": "http.server.duration.p99" }
  ],
  "breakdowns": ["k8s.node.name"],
  "time_range": "1h"
}
```

## Temporal Aggregation Overrides

### Per-second request rate (RATE override)
For a cumulative counter where you want rate instead of the default INCREASE:
```json
{
  "calculated_fields": [
    { "name": "req_rate", "expression": "RATE($http.server.requests, 300)" }
  ],
  "calculations": [
    { "op": "AVG", "column": "req_rate" }
  ],
  "time_range": "1h"
}
```

### Request rate with smoothing by breakdown
```json
{
  "calculated_fields": [
    { "name": "req_rate", "expression": "RATE($http.server.requests, 300)" }
  ],
  "calculations": [
    { "op": "AVG", "column": "req_rate" },
    { "op": "HEATMAP", "column": "req_rate" }
  ],
  "breakdowns": ["service.name"],
  "time_range": "1h"
}
```

### P99 of rate (combine temporal and spatial)
```json
{
  "calculated_fields": [
    { "name": "body_rate", "expression": "RATE($http.server.request.body.size, 60)" }
  ],
  "calculations": [
    { "op": "P99", "column": "body_rate" }
  ],
  "time_range": "1h"
}
```

### Delta metric totals (SUMMARIZE)
For delta-style sums where you want per-step totals:
```json
{
  "calculated_fields": [
    { "name": "total_requests", "expression": "SUMMARIZE($http.requests.delta_count)" }
  ],
  "calculations": [
    { "op": "SUM", "column": "total_requests" }
  ],
  "time_range": "1h"
}
```

### Error rate from counters (RATE + query math)
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
  ],
  "time_range": "1h"
}
```

## Comparing Across Dimensions

### CPU by namespace
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.cpu_limit_utilization" }
  ],
  "breakdowns": ["k8s.namespace.name"],
  "time_range": "6h"
}
```

### Container memory by deployment
```json
{
  "calculations": [
    { "op": "AVG", "column": "container.memory.usage" },
    { "op": "MAX", "column": "container.memory.usage" }
  ],
  "breakdowns": ["k8s.deployment.name"],
  "orders": [{ "op": "MAX", "column": "container.memory.usage", "order": "descending" }],
  "limit": 20,
  "time_range": "6h"
}
```

## Filtering Metrics

### Filter to a specific namespace
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.memory.usage" }
  ],
  "filters": [
    { "column": "k8s.namespace.name", "op": "=", "value": "honeycomb-production" }
  ],
  "breakdowns": ["k8s.pod.name"],
  "time_range": "1h"
}
```

### Filter to a specific pod pattern
```json
{
  "calculations": [
    { "op": "AVG", "column": "container.cpu.utilization" }
  ],
  "filters": [
    { "column": "k8s.pod.name", "op": "contains", "value": "retriever" }
  ],
  "breakdowns": ["k8s.pod.name"],
  "time_range": "1h"
}
```

### HAVING filter for high-utilization pods only
```json
{
  "calculations": [
    { "op": "AVG", "column": "k8s.pod.cpu_limit_utilization" }
  ],
  "breakdowns": ["k8s.pod.name"],
  "havings": [
    { "calculate_op": "AVG", "column": "k8s.pod.cpu_limit_utilization", "op": ">", "value": 0.8 }
  ],
  "time_range": "1h"
}
```
