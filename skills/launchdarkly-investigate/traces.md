# Investigating with traces

Load this file when the investigation concerns request flow, latency, or span-level behavior across service boundaries.

## When to reach for traces

- The user reports a slow or failed request and you have a trace ID
- You need to understand which service in a chain is the bottleneck
- An error has a trace ID in its context — follow the trace to find where the request went sideways
- You're comparing "healthy" vs. "unhealthy" requests for the same operation

Traces are high-volume and unbounded queries are rarely useful. Always anchor to a trace ID, a narrow time window, or a specific service+operation.

## Tool guidance (`query-traces`)

The `query-traces` tool returns paginated trace entries with timestamp, span details, and attributes.

- `start_date` is required; ISO format.
- `end_date` defaults to now. **Never query more than 24 hours of traces.** If you need a wider window, use `query-aggregations` to aggregate first.
- `query` filters by span attributes — e.g. `span_name="getUserData" AND service_name=auth`.
- `limit` defaults to 20, max 50.
- `direction` is `ASC` or `DESC`. Defaults to `DESC`.

**Duration is in nanoseconds.** Convert before reporting — a latency of `2500000000` is 2.5 seconds.

**Session-scoped traces.** Use `query="secure_session_id=<id>"` with `start_date` = session `created_at`, `end_date` = +3 hours.

## Typical patterns

1. **Latency investigation** — find the slow operation via `query-aggregations` with `product_type="traces"` and `group_by="span_name"`, then drill in with `query-traces` for specific slow instances.
2. **Critical-path analysis** — pull one representative slow trace, identify the span that dominates total duration, then check if it's consistently slow across many traces (`query-traces` + query filter) or a one-off.
3. **Cross-service failure** — when a trace shows an error span, look at the parent and child spans. The failure often cascades; the true root is usually a downstream service.
4. **Compare healthy vs. unhealthy** — pull one trace of each for the same operation. Apples-to-apples — same span_name, same service version.

## Interpreting results

- **Span hierarchy matters.** Read the trace as a tree. A 5-second top-level span made up of a 4.9-second DB call tells a different story than ten 500ms calls.
- **If spans are missing or sampled out**, say so. Don't infer timing from gaps.
- **Cite the trace ID and service name** when making claims. "The auth service is slow" with no trace ID isn't actionable.

## Common mistakes

- Querying traces across 7-day windows. Max 24 hours; use `query-aggregations` for longer ranges.
- Reporting duration in raw nanoseconds. Always convert to ms or s.
- Treating a single slow trace as a systemic problem. Check frequency before recommending a fix.
