# Alert investigation: traces

Load this file for a trace alert: latency (a percentile or average of `duration`), span error rate, or span count.

## Before you look for a cause

- **Replay the firing** with the `replay` arguments from `get-alert-firing-history`, then again with `compareTo: "1w"`. Latency alerts are the most common source of noise; a value that matches last week's is a standing condition.
- **Count the rows.** Check the replay for a `low_sample` block, and add a `Count` expression. A P99 over about 600 spans per window is the sixth-slowest span, and over sampled data the rows read are far fewer than the spans. Set `exact: true` for the alert window. If the alert's percentile rests on a few dozen rows, the alert is fragile; recommend P95, a longer window or a minimum count.
- **Compare the firing group with its siblings.** For an alert grouped by `task.type` or `http.route`, replay with the alert's `groupBy` and `bucketCount: 1`: is only the firing group slow, and was it already slow last week?

## Investigation shape

1. **Slowest or failing spans in the window:** `search-traces` with the alert's query, `sortColumn: "duration"`, `sortDirection: "DESC"`, `limit` 5; or `has_errors=true` for error-rate alerts.
2. **Read the slowest trace** with `get-trace` (pass `timestamp`). `top_self_time` and `critical_path` name the span that owns the time (`self_ms`, `share_of_root`); without them, subtract the children's durations from the parent's. For errors, find the lowest error span.
3. **Is that span the pattern?** Aggregate `Sum` and `P95` of `duration` for the parent and its child span names with `exact: true` and `compareTo: "1w"`. "Child X is 65 % of the operation's time, as it was last week" is a cause and a verdict at once.
4. **What is over-represented:** break the alert's signal down by `host.name`, the version key and `http.route` with `compareTo` (step 4 of the first five minutes in `launchdarkly-investigate`).
5. **What changed:** `get-changes` for the service from 1 to 2 hours before the onset.

## What goes in the diagnosis

- **What triggered:** alert name and ID, group, function and threshold, the replayed value in ms or s, and the row count behind it.
- **Verdict:** new, chronic or noise, with firings in 7 days and last week's value.
- **Likely cause:** the span that owns the time or the failure, with a trace ID and its share of total time.
- **Next steps:** the code or dependency to fix, or a concrete alert retune.

## Common mistakes

- Reporting raw nanoseconds.
- Treating one slow trace as the pattern without an aggregate.
- Blaming the longest child span when the parent's own time is larger.
- Quoting a sampled P99 over a few dozen rows.
