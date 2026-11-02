# Temporal Aggregation Reference

Temporal aggregation aligns raw metric timeseries into fixed-duration time steps before
spatial aggregation (SELECT operations like AVG, SUM, P99) is applied. Understanding
this two-phase process is essential for interpreting metrics query results correctly.

## How It Works

When you run a metrics query, Honeycomb:

1. Identifies relevant timeseries based on filters and time range. Each unique
   combination of metric name + attributes is a separate timeseries.
2. Divides the query time range into evenly-spaced steps using the granularity
   (e.g., 60-second intervals).
3. Applies a temporal aggregation function to each timeseries within each step,
   producing one value per timeseries per step.
4. Applies spatial aggregation (your SELECT operations) across the aligned timeseries
   to produce the final result.

## Temporal Aggregation Functions

### LAST(metric)

Returns the most recent data point in each time step.

**Use for:** Gauges, non-monotonic sums — metrics that represent a current state or
snapshot (memory usage, CPU utilization, queue depth, thread count).

**Behavior:** If a time step contains data points at t=10s, t=20s, t=30s, LAST returns
the value at t=30s.

### SUMMARIZE(metric)

Sums all values within each time step, with interpolation to handle values that span
step boundaries.

**Use for:** Delta metrics that track counts or totals within a reporting window
(requests received, log entries written, bytes transferred per interval).

**Behavior:** If a delta metric reports [50, 60, 45] within a one-minute step,
SUMMARIZE returns 155. For values that span step boundaries, Honeycomb interpolates
proportionally.

**For histograms:** SUMMARIZE adds bucket values independently, preserving the bucket
structure. This means percentile computations on SUMMARIZE'd histograms remain valid.

### INCREASE(metric[, range_interval_seconds])

Measures the change in a cumulative metric's value across a range. Handles counter
resets automatically.

**Use for:** Monotonic cumulative counters (total requests served, total bytes sent,
total errors since startup).

**Behavior:** Computes `value_at_end - value_at_start` for each time step. If a counter
reset is detected (a later value is lower than an earlier one, or the OTel start_time
changes), Honeycomb treats it as a restart and counts from the new baseline.

**Counter reset example:**
```
10:01:05 — 8,450
10:01:30 — 8,700    (increase of 250)
10:01:45 — 250      (reset detected — service restarted)
```
Without reset handling, the raw delta would be -8,200. With INCREASE, Honeycomb
computes: +250 (before reset) + 250 (after reset, from zero) = **500**.

**For histograms:** INCREASE calculates the difference for each bucket independently.
If data points are missing at interval boundaries, Honeycomb extrapolates up to half
the captured interval duration to avoid overestimation.

### RATE(metric[, range_interval_seconds])

Per-second rate of change. Equivalent to `INCREASE(metric) / time_in_seconds`.

**Use for:** Normalizing counters to per-second throughput (requests/sec, bytes/sec,
errors/sec). Useful for comparing metrics with different reporting intervals or
smoothing spikes.

**Behavior:** Same as INCREASE but divides by the time range to produce a rate.

## The range_interval_seconds Parameter

Both `INCREASE` and `RATE` accept an optional second argument: the lookback window
in seconds for calculating changes.

**Default:** Uses the query's granularity as the range interval.

**When to override:**
- **Sparse data:** If metrics report every 60s but your granularity is 10s, many steps
  will have no data. Setting `range_interval_seconds` to 120 or 300 lets Honeycomb
  look back further for the previous value.
- **Smoothing:** A larger range_interval_seconds averages changes over a wider window,
  reducing noise.
- **Consistent results across zoom levels:** Without it, zooming in (smaller granularity)
  can change the apparent rate because fewer data points fall in each step.

**Example:** `RATE($http.server.requests, 300)` computes the per-second rate using a
5-minute lookback window, regardless of query granularity.

## Default Function by Metric Type

| MetricInfo Value | Default | Rationale |
|------------------|---------|-----------|
| `gauge` | `LAST()` | Point-in-time value; latest sample is most representative |
| `sum(cumulative,monotonic)` | `INCREASE()` | Ever-increasing counter; change per step is meaningful |
| `sum(cumulative)` | `LAST()` | Can go up or down; latest value is most useful |
| `sum(delta)` | `SUMMARIZE()` | Each report is a delta; sum them for per-step total |
| `sum(delta,monotonic)` | `SUMMARIZE()` | Delta counter; sum for per-step total |
| `histogram(cumulative)` | `INCREASE()` | Cumulative buckets; differences show per-step distribution |
| `histogram(delta)` | `SUMMARIZE()` | Delta buckets; sum for per-step distribution |
| `summary` | `LAST()` | Pre-aggregated summary; latest value used |

## Overriding Defaults via Calculated Fields

To use a temporal aggregation function different from the default, create a
query-scoped calculated field in the `calculated_fields` array, then reference
that field in `calculations`:

```json
{
  "calculated_fields": [
    { "name": "my_rate", "expression": "RATE($http.server.requests, 300)" }
  ],
  "calculations": [
    { "op": "HEATMAP", "column": "my_rate" }
  ]
}
```

**Rules for calculated field temporal overrides:**
- The `$metric` syntax (with `$` prefix) references a raw metric name
- You must still apply a spatial aggregation in `calculations` — the temporal
  function alone does not produce results
- The calculated field name can be used in `breakdowns`, `filters`, `havings`,
  and `orders` just like any other field
- Calculated fields defined in one query step are available in all steps when
  using query math
- You cannot nest temporal aggregation functions (e.g., `RATE(INCREASE($m))` is invalid)
- You cannot reference other calculated fields inside temporal aggregation expressions

## Interaction with Granularity

Granularity defines the size of each time step. For metrics with regular reporting
intervals, aligning granularity matters:

- A metric that reports every 10 seconds: use granularity of 10, 30, 60, 120, etc.
- A metric that reports every 60 seconds: use granularity of 60, 120, 300, etc.
- Misaligned granularity (e.g., 15s granularity for 10s reporting) causes uneven
  numbers of data points per bucket, producing noisy results — especially with
  SUM-based aggregations.

When querying via the MCP tools, granularity is auto-calculated if omitted.
The auto-calculation targets approximately 80 data points, which generally
produces reasonable alignment.
