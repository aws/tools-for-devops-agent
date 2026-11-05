# Query Result Interpretation Reference

Complete guide to interpreting Honeycomb query results. The MCP tools return formatted
markdown (tables, ASCII charts) plus metadata — but the most precise data lives in the
raw JSON behind the `query_result_json` URL.

## Raw Result Access

Every query result includes a `query_result_json` URL in its metadata. This is a signed,
time-limited URL that returns the full JSON payload — exact numeric values, complete time
series arrays, heatmap bucket counts, and sample data that the ASCII rendering can only
approximate.

**Always download and parse the raw JSON when you need:**
- Exact numeric values (not rounded for display)
- Full time series data for trend detection
- Heatmap bucket distributions for statistical comparison
- Sample event data for extracting trace IDs

### Downloading and Parsing with jq

Extract all result rows:
```bash
curl -s "$URL" | jq '.results[].data'
```

Extract a specific time series value:
```bash
curl -s "$URL" | jq '.series[] | select(.data.name == "checkout") | .data["P99(duration_ms)"]'
```

Sum heatmap bucket counts:
```bash
curl -s "$URL" | jq '[.results[].data["HEATMAP(duration_ms)"].counts] | add'
```

### Parsing with Python

```python
import json, urllib.request

raw = json.loads(urllib.request.urlopen(url).read())

# Compute error rate from COUNT results
total = sum(r["data"]["COUNT"] for r in raw["results"])
errors = sum(r["data"]["COUNT"] for r in raw["results"] if r["data"].get("error") == True)
error_rate = errors / total if total > 0 else 0

# Detect latency trend from time series
series = [s for s in raw["series"] if s["data"].get("name") == "api-gateway"]
p99_values = [s["data"]["P99(duration_ms)"] for s in series if s["data"].get("P99(duration_ms)") is not None]
trend = "increasing" if len(p99_values) > 1 and p99_values[-1] > p99_values[0] * 1.2 else "stable"

# Compare heatmap distributions across groups
for r in raw["results"]:
    heatmap = r["data"].get("HEATMAP(duration_ms)", {})
    counts = heatmap.get("counts", [])
    name = r["data"].get("name", "unknown")
    print(f"{name}: {sum(counts)} total events across {len(counts)} buckets")
```

## Raw JSON Schema Reference

### Top-Level Fields

| Field | Description |
|-------|-------------|
| `results` | Array of aggregate result rows |
| `series` | Array of time series data points |
| `header` | Column metadata for the result set |
| `info` | Query execution metadata |
| `template` | The query definition that produced this result |
| `total_by_aggregate` | The TOTAL row (aggregate across all groups) |
| `other_by_aggregate` | The OTHER row (groups beyond the query limit) |
| `total_by_aggregate_series` | Time series for the TOTAL row |

### `results[].data`

Aggregate values keyed by calculation name. Keys match the VISUALIZE expressions:
- `"COUNT"` — event count
- `"P99(duration_ms)"` — 99th percentile of duration_ms
- `"HEATMAP(duration_ms)"` — heatmap bucket structure (see below)
- Group-by field names appear as keys too (e.g., `"name"`, `"service.name"`)

### `series[].data`

Same keys as `results[].data` but per time bucket. Each entry includes a `time` field
in ISO 8601 format representing the start of that bucket.

### HEATMAP Bucket Structure

```json
{
  "counts": [12, 45, 89, 120, 67, 23, 5, 1],
  "min_value": 0,
  "max_value": 2000,
  "step_size": 250
}
```

- `counts` — array of event counts per bucket, from `min_value` to `max_value`
- `min_value` / `max_value` — range of the heatmap
- `step_size` — width of each bucket in the field's unit

### `header[]`

Column metadata for each result column:
- `alias` — display name for the column
- `key_name` — internal key used in `results[].data`
- `type` — data type (`string`, `float`, `integer`, `boolean`)
- `derived` — whether this is a calculated/derived column

### `info`

Query execution metadata:
- `granularity_seconds` — time bucket size used for time series
- `rows_examined` — total rows scanned to produce the result
- `mean_sample_rate` — average sample rate across matched events

## Reading the Formatted Output

### Markdown Tables

Aggregate results are rendered as markdown tables. Special rows:
- **TOTAL** — aggregate across all groups (matches `total_by_aggregate` in raw JSON)
- **OTHER** — groups beyond the query limit (matches `other_by_aggregate` in raw JSON)

If the OTHER row has large values, increase the query limit to capture more groups.

### ASCII Time Series

Time series charts show values over time:
- Y-axis range appears in brackets after the series name
- X-axis shows time progression
- Each series gets its own line

### ASCII Heatmap

Block characters `▁▂▃▄▅▆▇█` represent event density from low to high:
- Y-axis is the value range (e.g., duration in ms)
- X-axis is time
- Legend at bottom shows the count mapping for each block character
- Two distinct horizontal bands indicate two populations (bimodal distribution)

### Samples Table

Raw events with all columns. Key fields to look for:
- `trace.trace_id` — feed these to `get_trace` for full trace analysis
- `duration_ms` — span duration
- `error` — whether the span errored
- `name` — span/operation name; legacy span-event names also appear here
- `event.name` — logical event name for Logs API records (including correlated exception events)
- `body` — log body, often a duplicate/fallback event label for Logs API records
- `meta.signal_type` — distinguish `trace` span events from `log` records when present
- `meta.annotation_type` — `span_event` can describe both legacy span events and correlated Logs API events
- `trace.parent_id` — the active containing span ID on a trace-correlated log event

## Statistical Interpretation Heuristics

### Latency Distribution Signals

| Pattern | Meaning |
|---------|---------|
| P99/P50 ratio > 10x | Bimodal distribution likely; run HEATMAP to confirm |
| P99/P50 ratio 2-5x | Normal long-tail, likely healthy |
| P99/P50 ratio < 2x | Very uniform distribution |

### Heatmap Patterns

| Pattern | Meaning |
|---------|---------|
| Two distinct horizontal bands | Two populations (e.g., cached vs uncached, fast path vs slow path) |
| Single band shifting up over time | Gradual degradation |
| Band widening over time | Increasing variance, possible resource contention |
| Dense lower band + sparse upper band | Mostly healthy with occasional outliers |

### Time Series Patterns

| Pattern | Meaning |
|---------|---------|
| COUNT dropping to 0 | Service outage or instrumentation gap |
| Sawtooth (regular spikes) | Periodic batch jobs or cron tasks |
| Flat-then-spike | Sudden event: deployment, traffic burst, dependency failure |
| Gradual ramp up | Organic traffic growth or memory/connection leak |
| Step function (sudden level change) | Config change, deployment, or dependency behavior change |

## BubbleUp Result Interpretation

BubbleUp compares an outlier selection against a baseline to find differentiating dimensions.

### Signal Strength

| Delta | Interpretation |
|-------|---------------|
| >50% between baseline and selection | Strong signal, likely causal |
| 10-50% delta | Moderate signal, investigate further |
| <10% delta | Weak signal or noise |

### Edge Cases

- **Many dimensions flag (>10)** — selection is too broad; narrow your time range or value range
- **No dimensions flag** — expand time range or try different query grouping
- **Measure histogram shift** — correlated metric, not necessarily causal; verify with targeted query

## Result-to-Action Decision Tree

Use metadata fields to chain investigation steps:

1. **After aggregate query** — if anomaly visible, use `query_run_pk` from metadata to feed `run_bubbleup`
2. **After BubbleUp** — add top differentiators as WHERE filters in a follow-up `run_query`
3. **After filtered query with samples** — extract `trace.trace_id` values to feed `get_trace`
4. **After trace analysis** — identify bottleneck span, query its `name` with P99 to check if systemic
5. **Share findings** — `query_url` links to the query in Honeycomb UI; `trace_link` links to the trace

## Common Patterns and What They Mean

| Observation | Likely Cause |
|-------------|-------------|
| Bimodal heatmap | Two distinct request populations (e.g., fast cache hits vs slow DB queries) |
| Error count correlating with latency spike | Cascading failure — errors cause retries, retries add latency |
| Single endpoint dominating COUNT | Hot path or bot traffic |
| `rows_examined` much larger than result count | Heavy filtering; consider narrowing time range |
| `granularity` very coarse (>3600s) | Time range is large; spikes may be smoothed out — zoom in for detail |
| TOTAL row much larger than sum of visible groups | Large OTHER row; many unlisted groups — increase query limit |
