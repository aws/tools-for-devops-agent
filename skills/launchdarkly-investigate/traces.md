# Investigating with traces

Load this file when the investigation concerns request flow, latency, failed spans, or which service in a chain is at fault.

## When to reach for traces

- A route or operation got slow or started failing
- You have a trace ID (from a log line, an error occurrence or a session) and want the full request
- You need to know which span owns the time, or which downstream call failed first
- You want to know whether a flag variation, version or host is tied to the failures

Size the problem with `search-aggregations` (`productType: "traces"`) or `search-service-map` first; read individual traces once you know which slice is bad.

## Find the slow or failing slice

- **Service and route health:** `search-service-map` with `service` and `include: ["health"]` returns requests, errors, error rate and p50/p95/p99 for the service and per `http.route`. It covers services with server spans; for queue consumers and workers, aggregate the consumer span by `span_name` instead.
- **Endpoints:** HTTP middleware often names server spans only by method (`GET`). Filter `span_kind=Server` and group by `http.route`, not `span_name`.
- **Breakdown against a baseline:** group by `host.name`, the version key, or `http.route` with `compareTo` (see step 4 in `SKILL.md`). For latency, report `P95` of `duration` and rank groups by `Count`.
- **Time per child span:** to see which child operation owns a parent's time, filter `span_name=(childA OR childB OR childC)` and aggregate `Sum` of `duration` grouped by `span_name` with `exact: true`; compare each child's sum with the parent's. Read one trace with `get-trace` first to learn the child span names.
- **Flag variation:** spans carry flag evaluations as `feature_flag.key` and `feature_flag.result.value` (also `feature_flag.result.variationIndex`; check with `get-keys search=feature_flag`). Filter `feature_flag.key=<flag>` and group by `feature_flag.result.value`, with and without `has_errors=true`, to see whether one variation holds the failures. `search-flag-evaluations` with `flagKey` and no `sessionSecureId` counts the flag's evaluations per value across the project.

## Pull traces (`search-traces`)

- `startDate` is required; a raw search covers at most 24 hours.
- **Slowest:** `sortColumn: "duration"`, `sortDirection: "DESC"`, `limit` 5 to 10. It reads a sample; for the true slowest, get `Max` of `duration` with `exact: true` from `search-aggregations`, then search `duration>=<that value>`.
- **Failing:** `has_errors=true` plus the slice filter.
- **One row per trace:** `view: "traces"` (takes only `query`, the window, `limit` and `cursor`).
- `fields` picks attributes and keeps rows small; `fullAttributes` reads long values whole.
- Pages are at most 50 rows; follow `page.next_cursor` (not available with `sortColumn`).
- **Within one trace:** `span(A) THEN span(B)` and `span(A) THEN no_span(B)` match order and absence; `parent_span(...)`, `child_span(...)`, `root_span(...)` and `any_span(...)` match other spans in the same trace. `parent_span_id NOT EXISTS` selects root spans.

## Read one trace (`get-trace`)

Pass `traceId` and, whenever you know a span time, `timestamp` (the span's timestamp from `search-traces` or a log line). The result is a span tree with each span's service, duration and status, plus the trace's error groups.

- For large traces, `onlyServiceEntrySpans: true` keeps one span per service hop and every error span.
- `expandSpanId` returns one span with its full attributes (route, exception details) and its subtree uncollapsed.
- **Find where the time goes.** A span's own time is its duration minus the time covered by its children. A 2.3 s span whose two children take 0.25 s and 0.49 s spent about 1.5 s in its own code; blaming the children would be wrong. `get-trace` computes this for you on the full tree, before `onlyServiceEntrySpans` or `maxTokens` trimming:
  - `self_ms` on each span: its duration minus the union of its children's intervals.
  - `critical_path`: up to 15 spans, walking back from the root to the child that finished last, each with `duration_ms`, `self_ms` and `critical_ms` (the time it held the request up).
  - `top_self_time`: the 5 spans with the most `self_ms`, each with `share_of_root`.
  Name the cause from `top_self_time` and `critical_path`, not from the longest child. On a server without these fields, subtract the children's durations from the parent's by hand.
- **Find where the failure started.** Error spans propagate upward; the lowest error span in the tree, usually in a downstream service, is the origin.
- If the trace is incomplete (a Kafka consumer whose parent is the producer span, or sampled-out spans), say so; do not infer timing from gaps.

## Logs and errors for a trace

- `search-logs` with `query: "trace_id=<id>"` and a window of a few minutes around the span returns every log line of the request.
- The trace's error groups come back from `get-trace`; open one with `get-error-group`.

## Interpreting results

- **Duration is in nanoseconds.** `2500000000` is 2.5 s.
- **One slow trace is an example, not a pattern.** Confirm with an aggregation that the slow span is slow across many traces before recommending a fix.
- **Compare like with like.** For a regression, compare the same `span_name` and route with `compareTo` rather than eyeballing one old trace.
- **Cite the trace ID, service and span name** for each claim.

## Common mistakes

- Searching raw traces over more than 24 hours. Aggregate instead.
- Quoting a sampled P99 over a few dozen rows. See "Sampling and percentiles" in `SKILL.md`.
- Blaming the child span with the longest duration when the parent's own time is larger.
- Guessing the version or status-code key. Take the version key from `get-changes` and check status keys with `get-keys`.
