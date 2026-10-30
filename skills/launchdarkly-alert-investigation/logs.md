# Alert investigation — logs

Load this file when investigating a log alert (log-pattern threshold, log-volume spike, log-level anomaly).

## What the alert context carries

Log alerts arrive with at minimum:
- `alertID`, `alertName`, `alertValue` — identity and the numeric value that crossed threshold
- `group`, `groupValue` — the dimension the alert groups on (e.g. `service_name=auth`, `level=error`)
- `query` — the log filter the alert uses
- `thresholdWindow` — how long the condition held before firing
- `logsLink` — deep-link to the logs UI showing the triggering data
- `timeRange` — the window during which the threshold was breached

## Investigation shape

1. **Reconstruct the matching logs.** Use the `query-logs` tool with the alert's `query` and `timeRange`. Start with a small `limit` (10–20) to sample.
2. **Identify the pattern.** Are these repeated occurrences of the same error, or heterogeneous failures that share an attribute (service, endpoint)?
3. **Correlate with traces.** If the logs carry trace IDs, pull those traces — the span hierarchy often reveals which downstream dependency failed.
4. **Correlate with errors.** If the log messages match a specific exception, check `query-error-groups` for onset timestamps.
5. **Check for an external trigger.** Did a deploy happen in the thresholdWindow? A flag flip? A traffic surge?

## What goes in the diagnosis

- **What triggered** — cite the `alertName`, threshold, and value.
- **Likely cause** — the log pattern with a specific example log line quoted verbatim, plus the suspected trigger (deploy, flag, dependency).
- **Scope** — number of affected services, users, or sessions within the window.
- **Next steps** — specific: "roll back the N+1 deploy of <service>", "disable flag <key> in <env>", "restart <service> if the errors continue past <time>".

## Common mistakes

- Querying a time window wider than the alert's. Stick to the alert's window unless the investigation explicitly needs pre/post comparison.
- Paraphrasing log lines. Quote verbatim — that's the evidence.
- Skipping `get-keys` before filtering on an attribute you haven't used before. Wrong name returns empty silently.
