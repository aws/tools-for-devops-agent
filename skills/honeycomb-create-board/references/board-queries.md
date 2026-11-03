# Board Query Guidance

## When to use each aggregation

- `COUNT` — Request volume, error counts
- `AVG` — Error rates, business averages
- `HEATMAP` — Overall latency distribution; the most useful single latency view
- `P50/P95/P99` — Latency SLIs (P95 most common). Make great stat panels; for graphing prefer heatmap.
- `COUNT_DISTINCT` — Unique users, sessions, products
- `SUM` — Revenue, transaction totals
- `MAX/MIN` — Finding extremes (less common)

## RED metrics

Every service board should cover Rate, Errors, Duration:

- **Rate** — `COUNT` of requests over time
- **Errors** — error rate % (see below) and/or error count
- **Duration** — `HEATMAP(duration_ms)` plus `P95(duration_ms)` as a stat panel

## Counting requests

Top-level and downstream services need different span filters.

**Root spans (top-level service)**:
```javascript
filters: [
  { column: "trace.parent_id", op: "does-not-exist" },
  { column: "meta.signal_type", op: "=", value: "trace" },
]
```

**Server spans (downstream service)**:
```javascript
filters: [{ column: "span.kind", op: "=", value: "server" }]
```

Query the dataset to see which applies before building the board.

## Latency as a heatmap

Use the same filter as for counting requests — root span latency is the service latency.

Graph `HEATMAP(duration_ms)`. When there's a GROUP BY, use `P95(duration_ms)` instead — heatmap doesn't combine well with breakdowns.

## Error rate

Use the error rate calculated field pattern from the **honeycomb-query-patterns** skill (see the
Calculated Fields section). Include error rate as two panels: a stat panel for the
current number, and a line graph for trends over time. To work around Honeycomb's
"no duplicate queries" restriction, add `service.name exists` as a filter on one of them.

For operation-level error panels, group by low-cardinality fields such as `exception.slug`,
`error.type`, service, or route. If the board needs full exception diagnostics from Logs API events,
add a separate event-row query filtered by `event.name="exception"` and `exception.type exists`;
do not assume `exception.message` is present on the containing span.

## Business metrics

Business metrics are the highest-value measurements. If there are custom fields for revenue, cart totals, conversions, or engagement — include them. These tell a richer story than infrastructure metrics alone.

`SUM` is often the right aggregation: how much revenue was in flight? How much was involved in errors? `COUNT_DISTINCT(user_id)` or `COUNT_DISTINCT(session_id)` make excellent stat panels.

## Service dependencies

To find what services a service depends on, run an environment-wide query:

```
WHERE parent.span.kind = client AND parent.service.name = <service>
GROUP BY service.name
```

The resulting `service.name` values are its dependencies. Graph their latency and error rates alongside the main service.

## Infrastructure metrics

If a `Metrics` dataset exists, it may contain infrastructure data (CPU, memory, network). To find the right filters:

1. Query resource attributes in traces (`k8s.deployment.name`, `host.name`) to find how the service is identified
2. Look for those same attributes in the Metrics dataset
3. Explore the available metric names

## Categorizing fields with calculated fields

Turn continuous values into useful categories for pie charts or categorical bar charts:

```javascript
// Error type by status code
error_type = IF(
  GTE($http.status_code, 500), "5xx_server_error",
  IF(GTE($http.status_code, 400), "4xx_client_error", "success")
)

// High-value transaction flag
is_high_value = GTE($app.cart_total, 1000)

// Route category
route_category = IF(
  CONTAINS($http.route, "/product/"), "product_page",
  IF(CONTAINS($http.route, "/cart"), "cart_flow", "other")
)
```

After looking at some values, you can often find natural categories worth graphing. Is the app better or worse for paid accounts? How much of the work is serving free users?
