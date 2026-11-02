# VISUALIZE Operations Reference

Complete reference for all Honeycomb VISUALIZE operations. In `run_query`, these map to the
`calculations` array with `op` and optional `column` fields.

## Count Operations

### COUNT
Count the number of matching events.
- **`run_query`**: `{ "op": "COUNT" }` (no column) or `{ "op": "COUNT", "column": "field" }` (non-null count)
- **Use case**: Request volume, error counts, event frequency
- **Example**: Count errors grouped by service
  ```json
  { "calculations": [{"op": "COUNT"}], "filters": [{"column": "error", "op": "=", "value": true}], "breakdowns": ["service.name"] }
  ```
- **Notes**: Without a column, counts all events. With a column, counts events where that field is non-null.

### COUNT_DISTINCT(field)
Count unique values of a field (HyperLogLog approximation).
- **`run_query`**: `{ "op": "COUNT_DISTINCT", "column": "user.id" }`
- **Use case**: Unique users, unique trace IDs, unique error messages
- **Example**: Count unique users across root spans
  ```json
  { "calculations": [{"op": "COUNT_DISTINCT", "column": "user.id"}], "filters": [{"column": "is_root", "op": "=", "value": true}] }
  ```
- **Notes**: Approximate for large cardinalities. Exact for small sets.

## Numeric Aggregations

### SUM(numeric_field)
Sum of field values.
- **`run_query`**: `{ "op": "SUM", "column": "http.response_content_length" }`
- **Use case**: Total bytes transferred, total cost, items processed
- **Example**: Total response bytes by service
  ```json
  { "calculations": [{"op": "SUM", "column": "http.response_content_length"}], "breakdowns": ["service.name"] }
  ```

### AVG(numeric_field)
Average of field values.
- **`run_query`**: `{ "op": "AVG", "column": "http.response_content_length" }`
- **Use case**: Average payload size, average queue depth
- **Notes**: For latency, **always prefer percentiles** (P50, P90, P99) over AVG. Averages hide tail latency.

### MAX(numeric_field) / MIN(numeric_field)
Maximum or minimum field value.
- **`run_query`**: `{ "op": "MAX", "column": "duration_ms" }`
- **Use case**: Worst-case latency, peak memory usage, minimum throughput

## Percentiles

### P001 through P999(numeric_field)
Percentile values using t-digest approximation.
- **`run_query`**: `{ "op": "P99", "column": "duration_ms" }`
- **Common percentiles**: P50 (median), P90, P95, P99, P999
- **Use case**: Latency analysis — P50 for typical experience, P99 for tail latency
- **Example**: P50 and P99 latency for root spans by operation
  ```json
  { "calculations": [{"op": "P50", "column": "duration_ms"}, {"op": "P99", "column": "duration_ms"}], "filters": [{"column": "is_root", "op": "=", "value": true}], "breakdowns": ["name"] }
  ```
- **Notes**: Always use percentiles instead of AVG for latency. P99 reveals problems AVG hides. Available: P001, P01, P05, P10, P20, P25, P50, P75, P80, P90, P95, P99, P999.

## Distribution

### HEATMAP(numeric_field)
Visualize the distribution of values as a heatmap.
- **`run_query`**: `{ "op": "HEATMAP", "column": "duration_ms" }`
- **Use case**: Latency distribution, bimodal pattern detection, duration spread
- **Example**: Latency distribution heatmap for root spans
  ```json
  { "calculations": [{"op": "HEATMAP", "column": "duration_ms"}], "filters": [{"column": "is_root", "op": "=", "value": true}] }
  ```
- **Notes**: Heatmaps reveal multimodal distributions invisible in single-number aggregates. Essential for identifying "slow bucket" vs "fast bucket" patterns. Also required for BubbleUp selection on 2D heatmaps.

## Rate Operations

### RATE_AVG / RATE_SUM / RATE_MAX(numeric_field)
Per-second rate of the average, sum, or maximum over time.
- **`run_query`**: `{ "op": "RATE_AVG", "column": "duration_ms" }`
- **Use case**: Trend detection, acceleration of latency increases, throughput rate
- **Example**: Rate of average latency by operation for root spans
  ```json
  { "calculations": [{"op": "RATE_AVG", "column": "duration_ms"}], "filters": [{"column": "is_root", "op": "=", "value": true}], "breakdowns": ["name"] }
  ```
- **Notes**: Useful for detecting whether things are getting worse, not just whether they're bad. There is no generic `RATE_PER_SEC` operator.

## Concurrency

### CONCURRENCY
Count of concurrent overlapping operations.
- **`run_query`**: `{ "op": "CONCURRENCY" }` (no column allowed)
- **Use case**: Connection pool pressure, concurrent request load
- **Example**: Concurrent operations for the api-gateway service
  ```json
  { "calculations": [{"op": "CONCURRENCY"}], "filters": [{"column": "service.name", "op": "=", "value": "api-gateway"}] }
  ```
- **Notes**: Requires spans with duration. Shows how many operations overlap in time.

## Combining Operations

Multiple calculations can be combined in a single query:

```json
{
  "calculations": [
    { "op": "COUNT" },
    { "op": "P99", "column": "duration_ms" },
    { "op": "HEATMAP", "column": "duration_ms" }
  ]
}
```

This produces multiple time-series and a heatmap in the same result. Combining reduces
the number of API calls needed and stays within rate limits.
