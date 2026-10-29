# Alert investigation — metrics

Load this file when investigating a metric-based alert (aggregated metric threshold, custom metric anomaly, composite alert).

## What the alert context carries

Metric alerts carry:
- `alertID`, `alertName`, `alertValue` — threshold and value
- `group`, `groupValue` — the dimension (if grouped)
- `query` — the metric query
- `thresholdWindow` — hold duration
- `metricsLink` — deep link
- `timeRange` — alert window

## Investigation shape

1. **Replay the alert's metric query** using the `query-aggregations` tool, same `product_type`, `query`, and time window as the alert. Confirm you see the same value that breached.
2. **Expand the time window just enough** to see onset — if the threshold was crossed at T, pull `query-aggregations` from `T - 2 * thresholdWindow` to `T` to see the rise.
3. **Drill into the underlying records.** A metric alert on `errors` points to specific error groups; on `sessions` to specific sessions; on `traces` to specific traces. Pull the relevant record-level data for the top contributing dimension.
4. **Check external triggers.** Deploy correlation, flag flip, traffic surge, dependency issue.

## What goes in the diagnosis

- **What triggered** — alert name, threshold, alertValue, and (if grouped) which dimension value crossed it.
- **Likely cause** — specific underlying records (error group IDs, trace IDs, session IDs) that drove the metric up. Quote one or two.
- **Scope** — affected count, time-window pattern, whether this is a sharp spike or a drift.
- **Next steps** — concrete actions per the root cause found; if the metric reflects underlying behavior that needs fixing, point to the record-level remediation.

## Common mistakes

- Only reporting the metric value without drilling into record-level evidence. The metric is a summary; the cause lives in the records.
- Mis-attributing a spike to a specific cause without correlating with a deploy/flag/dependency timeline.
- Querying too-wide a time range and washing out the signal. Stay near the alert window.
