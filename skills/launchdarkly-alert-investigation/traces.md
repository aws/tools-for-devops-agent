# Alert investigation — traces

Load this file when investigating a trace-based alert (latency threshold, span-error rate, trace-level anomaly).

## What the alert context carries

Trace alerts carry:
- `alertID`, `alertName`, `alertValue` — the value that crossed threshold
- `group`, `groupValue` — trace dimension the alert watches (e.g. `span_name=checkout`, `service_name=api`)
- `query` — the trace filter
- `thresholdWindow` — duration the condition held
- `tracesLink` — deep link to the traces UI
- `timeRange` — alert window

## Investigation shape

1. **Pull representative slow or failing traces** using the `query-traces` tool with the alert's `query` and `timeRange`. Limit to 5–10 to start; you don't need all of them.
2. **Identify the dominant span.** In a slow trace, which span owns most of the duration? If spans error, which span is the originating failure (lowest in the hierarchy)?
3. **Compare against baseline.** If the alert is a latency regression, pull a trace for the same operation from before the alert window. Apples-to-apples: same `span_name`, same service version.
4. **Look for external signals.** Deploy correlating with the onset? Upstream dependency failure? Traffic shift?

## What goes in the diagnosis

- **What triggered** — quote the `alertName`, threshold, and the `alertValue` (remember to convert nanoseconds to ms/s).
- **Likely cause** — span or service attributed as root; cite the trace ID and the specific span that broke down.
- **Scope** — how many traces hit the threshold, how many services/endpoints, over what fraction of traffic.
- **Next steps** — concrete: "investigate <span_name> in <service>, commit <hash> introduced the regression", "consider increasing the timeout on the <X> client", "roll back flag <key> if the pattern persists".

## Common mistakes

- Reporting raw nanoseconds. Convert.
- Citing a single slow trace as representative without confirming frequency.
- Missing the downstream failure — error spans propagate upward; the true root is often a child span.
- Querying a 24-hour window when the alert fired on a 10-minute spike. Stay inside the alert's window plus a small buffer.
