# BubbleUp Guide

BubbleUp compares a selected subset of data against the baseline to identify
what makes outliers different. It is the fastest path from "something is wrong"
to "here's what's different about the broken traffic."

## How BubbleUp Works

1. **Selection**: A subset of events (e.g., slow requests in a heatmap region)
2. **Baseline**: Everything else in the query results
3. **Comparison**: For each field, BubbleUp shows how the distribution differs
4. **Ranking**: Fields are ranked by how much they differentiate selection from baseline

## Using run_bubbleup via MCP

### Starting a New Analysis
Requires `query_pk` (from a previous `run_query` result) and a `selection`:

**2D Heatmap Selection** (for heatmap queries):
```json
{
  "query_pk": "QR-abc123",
  "selection": {
    "type": "2d",
    "column": "duration_ms",
    "time_start": "80%",
    "time_end": "95%",
    "min_value": 500,
    "max_value": 5000
  }
}
```

**Group Selection** (for grouped queries):
```json
{
  "query_pk": "QR-abc123",
  "selection": {
    "type": "group",
    "group": { "http.route": "/api/checkout" }
  }
}
```

### Flexible Time Specifications
The `time_start` and `time_end` fields support multiple formats:
- **Percentages**: `"80%"`, `"95%"` — Position within the query time range
- **Time labels**: `"01:48"`, `"13:30"` — Clock time references
- **Relative offsets**: `"-5m"`, `"+2h"` — Relative to query bounds
- **Keywords**: `"start"`, `"middle"`, `"end"` — Named positions

### Targeting Specific Calculations
Use `clause_name` to run BubbleUp against a specific calculation or formula
from the source query.

### Pagination
BubbleUp returns columns in pages (default 20 per page, max 50).
- Use `bubbleup_result_id` with `page` parameter to paginate existing results
- Use `max_columns` to control total columns returned (default 20, max 100)

## Accessing BubbleUp via UI (3 methods)

1. **Heatmap selection**: Draw a box around outlier region -> "BubbleUp Outliers"
2. **Line chart selection**: Click a spike -> "BubbleUp Outliers" (requires 2+ groups)
3. **Results table**: Hover a row -> "BubbleUp: Compare value to all other events"

## Reading BubbleUp Results

### Dimension Charts (Categorical Fields)
- Bar charts comparing selection (highlighted) vs baseline
- Two donuts show population ratio
- **What to look for**: Fields where the selection has a very different value distribution
- **Example**: If selection is 95% `region=us-east-1` but baseline is 33%, that's a strong signal

### Measure Charts (Numeric Fields)
- Histogram overlays comparing selection vs baseline distributions
- **What to look for**: Shifted distributions, bimodal patterns
- **Example**: If selection has `queue_depth` centered around 500 but baseline is around 50

## Best Practices

- **Select clearly separated data** — The cleaner the separation between outliers and baseline, the better BubbleUp works
- **Use smaller time ranges** — Reduces noise and improves contrast
- **Add BubbleUp findings as WHERE filters** — Iteratively narrow the investigation
- **Check multiple fields** — Root cause is often a combination of factors
- **Don't stop at the first signal** — Confirm by adding the filter and re-querying
- **Paginate results** — The most differentiating columns appear first, but check additional pages for secondary signals

## What Good Results Look Like

- **Strong signal**: 2-3 fields with clear differentiation between selection and baseline
- **Weak signal** (too broad): >10 fields flagged — selection may be too broad, try narrowing
- **No signal**: No clear differentiators — expand time range or try different query groupings

## Common Findings

- Deployment version (new deploy caused regression)
- Region/availability zone (infrastructure issue)
- Customer/tenant (specific user triggering edge case)
- Endpoint/route (specific API path affected)
- Upstream dependency (specific service in the call chain)
- Feature flag (new feature causing issues)
