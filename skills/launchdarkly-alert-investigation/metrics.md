# Alert investigation: metrics

Load this file for an OpenTelemetry metric alert (a threshold on `metric_name` values, a composite or formula alert). Load the `observability/metrics` guide too (with `load-skill`) for the metric's type and unit.

## Before you look for a cause

- **Replay the firing** with the `replay` arguments from `get-alert-firing-history`. Confirm you see the value that crossed the threshold, then add `compareTo: "1w"`.
- **Check the aggregator suits the metric.** `Max` of a cumulative counter only ever grows, so it fires on uptime, not on a problem. `Avg` of `system.cpu.utilization` across its `state` and `cpu` attributes is meaningless; group by `state`. A `Sum` of a gauge across hosts grows with the host count. An alert built on the wrong aggregator is a finding: recommend the right one.
- **Look at the onset.** Replay from two or three alert windows before the first firing with `bucketCount` 24 to 48: a sharp step, a slow drift, or a daily cycle that crosses the threshold every day?

## Investigation shape

1. **Which series moved:** group the replay by the metric's attributes (`host.name`, `service_name`, `k8s.pod.name`; list them with `get-keys`) with `bucketCount: 1` and `compareTo`. One host or pod off its peers is the usual cause.
2. **What else that host or service reports:** `search-aggregations` with `productType: "metrics"`, the slice filter and `groupBy: "metric_name"` lists its metrics, such as pool sizes, memory and queue depth.
3. **Tie it to requests:** traces and error logs for the same service and host in the window (see `launchdarkly-investigate`).
4. **What changed:** `get-changes` for the service.

## What goes in the diagnosis

- **What triggered:** metric name, aggregator, threshold, the replayed value with its unit, and the group.
- **Verdict:** new, chronic or misconfigured.
- **Likely cause:** the series that moved and the records behind it (trace IDs, log templates).
- **Next steps:** the fix, or the alert retune.

## Common mistakes

- Reporting the metric value without record-level evidence.
- Reading a counter's `Max` as a level.
- Quoting a value without its unit.
