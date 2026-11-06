# OpenTelemetry Metric Types in Honeycomb

This reference explains how OpenTelemetry metric types are stored in Honeycomb,
how to identify them, and what operations to use on each type.

## Identifying Metric Types

When you call `get_dataset_columns` on a metrics dataset, each column includes a
`MetricInfo` field that describes the metric type. The format is:

```
type(temporality[,monotonic])
```

### MetricInfo Values and Their Meanings

| MetricInfo | OTel Type | Description | Example Metrics |
|------------|-----------|-------------|-----------------|
| `gauge` | Gauge | Point-in-time value; can go up or down | CPU utilization, memory usage, temperature, queue depth |
| `sum(cumulative,monotonic)` | Monotonic Cumulative Sum | Ever-increasing counter that resets to zero on restart | Total requests served, total bytes sent, total errors, uptime |
| `sum(cumulative)` | Non-monotonic Cumulative Sum | Cumulative value that can increase or decrease | Active connections, pending operations |
| `sum(delta)` | Delta Sum (non-monotonic) | Change since last measurement | Requests in last interval |
| `sum(delta,monotonic)` | Monotonic Delta Sum | Positive-only change since last measurement | New events in last interval |
| `histogram(cumulative)` | Cumulative Histogram | Distribution with cumulative bucket counts | Request duration, response size |
| `histogram(delta)` | Delta Histogram | Distribution with per-interval bucket counts | Request duration (delta reporting) |
| `summary` | Summary | Pre-aggregated quantiles (from Prometheus) | AWS CloudWatch metrics via Firehose |

Columns without MetricInfo (no value in that field) are **attributes**, not metrics.
These are used in WHERE and GROUP BY, not in calculations.

## Gauges

Gauges represent a snapshot value at a point in time. The value can go up, down,
or stay the same between measurements.

**Default temporal aggregation:** `LAST()` — returns the most recent value per step.

**Recommended operations:**
- `AVG(gauge)` — average value across timeseries in each step
- `MAX(gauge)` — peak value across timeseries
- `HEATMAP(gauge)` — distribution of values across timeseries
- `P99(gauge)` — worst-case across timeseries

**Examples:** `k8s.pod.cpu_limit_utilization`, `container.memory.usage`,
`system.cpu.load_average.15m`

**Common mistake:** Using `SUM` on a gauge. Summing CPU utilization across pods
gives a meaningless total. Use `AVG` for typical or `MAX` for worst-case.

## Sums (Counters)

Sums track a running total or incremental count. They come in four variants based
on monotonicity and temporality.

### Monotonic Cumulative Sums (`sum(cumulative,monotonic)`)

The most common counter type. Value always increases; resets to zero on service restart.

**Default temporal aggregation:** `INCREASE()` — shows change per step, handles resets.

**Recommended operations:**
- `SUM(counter)` — total increase across all timeseries per step
- `AVG(counter)` — average increase per timeseries per step
- `MAX(counter)` — largest increase from any single timeseries

**To get per-second rate:** Use a calculated field: `RATE($counter)`

**Examples:** `k8s.pod.uptime`, `system.disk.io`, `system.network.io`,
`container.cpu.time`

### Non-monotonic Cumulative Sums (`sum(cumulative)`)

Cumulative value that can go up or down.

**Default temporal aggregation:** `LAST()` — latest value, since direction is unpredictable.

**Recommended operations:** Same as gauges — `AVG`, `MAX`, `HEATMAP`.

**Examples:** `system.memory.usage`, `system.network.connections`,
`system.disk.pending_operations`

### Delta Sums (`sum(delta)` or `sum(delta,monotonic)`)

Each data point represents the change since the previous measurement, not a running total.

**Default temporal aggregation:** `SUMMARIZE()` — sums the deltas within each step.

**Recommended operations:**
- `SUM(delta)` — total count per step across all timeseries
- `AVG(delta)` — average count per timeseries per step

**Examples:** `incoming_router_otlp_trace_http_proto`, `peer_router_otlp_log_http_json`

## Histograms

OpenTelemetry histograms are distributions: a collection of buckets, each storing the
count of values that fell within that bucket's range during the reporting period.

### How Honeycomb Stores Histograms

A histogram named `http.server.duration` produces these fields:

| Field | Type | Meaning |
|-------|------|---------|
| `http.server.duration` | (parent) | The histogram itself — use with HEATMAP, percentiles |
| `http.server.duration.count` | integer | Total number of observations |
| `http.server.duration.sum` | float | Sum of all observed values |
| `http.server.duration.avg` | float | Mean value (sum / count) |
| `http.server.duration.p001` | float | 0.1th percentile |
| `http.server.duration.p01` | float | 1st percentile |
| `http.server.duration.p05` | float | 5th percentile |
| `http.server.duration.p10` | float | 10th percentile |
| `http.server.duration.p20` | float | 20th percentile |
| `http.server.duration.p25` | float | 25th percentile |
| `http.server.duration.p50` | float | 50th percentile (median) |
| `http.server.duration.p75` | float | 75th percentile |
| `http.server.duration.p80` | float | 80th percentile |
| `http.server.duration.p90` | float | 90th percentile |
| `http.server.duration.p95` | float | 95th percentile |
| `http.server.duration.p99` | float | 99th percentile |
| `http.server.duration.p999` | float | 99.9th percentile |

### Querying Histograms: Parent Column vs. Sub-fields

**Parent column** — use for standard analysis:
```json
{ "op": "P99", "column": "http.server.duration" }
{ "op": "HEATMAP", "column": "http.server.duration" }
{ "op": "AVG", "column": "http.server.duration" }
```
These operations recompute aggregates across all timeseries in each step.
`P99(http.server.duration)` gives the true 99th percentile across all data points.

**Sub-fields** — use for worst-case bounds:
```json
{ "op": "MAX", "column": "http.server.duration.p99" }
```
`MAX(http.server.duration.p99)` returns the highest pre-computed p99 from any single
timeseries in the step. This answers "what was the worst p99 reported by any
individual source?" rather than "what was the overall p99?"

**Throughput from histograms:**
```json
{ "op": "SUM", "column": "http.server.duration.count" }
```
This gives the total number of observations per step — useful for request volume.

### Default Temporal Aggregation

- **Cumulative histograms** (`histogram(cumulative)`): `INCREASE()` per bucket
- **Delta histograms** (`histogram(delta)`): `SUMMARIZE()` per bucket

Both preserve the bucket structure so percentile operations remain valid after
temporal aggregation.

## Summaries

Summaries are pre-aggregated quantile data, typically from Prometheus-style sources
or AWS CloudWatch metrics via Firehose.

**Default temporal aggregation:** `LAST()`

**MetricInfo:** `summary`

Summaries behave like gauges for querying purposes — use `AVG`, `MAX`, `HEATMAP`.

## Attributes vs. Metrics

In a metrics dataset, not every column is a metric. Columns without `MetricInfo` are
**attributes** — metadata attached to metric events:

- **Resource attributes** describe the source (e.g., `k8s.pod.name`, `host.name`,
  `service.name`)
- **Data point attributes** describe measurement context (e.g., `http.route`,
  `disk.direction`)
- **`meta.signal_type`** is a system field indicating the signal type

Attributes are used in **WHERE** and **GROUP BY** clauses, never in calculations.

**Critical:** Each metric has its own set of attributes. Use `get_dataset_columns`
with `metric_name` to discover what attributes are available for a specific metric.
Do not assume that attributes from one metric exist on another.
