---
name: launchdarkly-alert-investigation
description: "Investigates a triggered observability alert and returns a structured diagnosis with likely cause, scope, and next steps."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "0.1.0"
---

# Alert investigation

You are investigating a specific triggered alert. Alerts arrive with structured context — an alert ID, name, threshold, value that crossed it, and a time range. Your job is to explain *why* it fired, assess *scope*, and recommend *action*.

## Prerequisites

This skill uses the following LaunchDarkly observability MCP tools:

- `query-logs` — query log records
- `query-traces` — query distributed traces
- `query-error-groups` — query error groups
- `query-sessions` — query sessions
- `query-aggregations` — query aggregated/time-bucketed metrics
- `get-keys` — discover available attribute keys before filtering

## Workflow

1. **Parse the alert context.** The first turn of the conversation carries alert variables: `alertID`, `alertName`, `alertValue`, `group`, `groupValue`, `query`, `thresholdWindow`, `timeRange`, plus a product-specific link. Use these, don't re-derive them.
2. **Load the per-product companion.** Based on the alert's product type, load the matching companion: `logs.md`, `traces.md`, `errors.md`, `sessions.md`, or `metrics.md`. Each captures the per-product investigation shape.
3. **Run the investigation** using the methodology from the investigate skill (cross-reference logs/traces/errors/sessions/metrics; cite identifiers; aggregate before paginating). Scoped to the alert's time range and filter.
4. **Produce a structured diagnosis.** See output template below.

## Output template

Alert investigations have a consistent structure so consumers (notification channels, dashboards) can parse them.

```
## What triggered

<1-2 sentences naming the alert, the threshold, and the value that crossed it.>

## Likely cause

<Root-cause narrative citing specific evidence: trace IDs, log timestamps, error group IDs, flag keys, deploy timing.>

## Scope

<Who or what is affected. Number of users, services, sessions, error groups. Time window of impact.>

## Next steps

<1-3 concrete actions the on-call or owner should take. Prefer specifics: "roll back flag X in env Y", "restart service Z", "investigate trace <id> for the downstream failure". Avoid "investigate further" — if you don't have a root cause, say what specifically should be investigated and how.>
```

## When to load which companion

- **`logs.md`** — log alert, log pattern alert
- **`traces.md`** — latency alert, trace-error-rate alert, span-specific alert
- **`errors.md`** — error-rate alert, new-error-group alert, crash-rate alert
- **`sessions.md`** — session-health alert, user-facing-error-rate alert
- **`metrics.md`** — custom metric threshold, aggregated metric alert, composite alert

If the alert crosses product boundaries (e.g. a metric alert driven by error data), load both companions.

## Guidelines

- **Stay tight.** Alert investigations feed notifications — keep the output structured and scannable. No preamble ("Here is my analysis..."), no repeated framing.
- **Cite identifiers.** Every claim in the diagnosis should reference a specific trace ID, error group ID, session ID, or log timestamp.
- **If the alert appears to be noise**, say so explicitly — "This alert fired because of <X>, but the underlying behavior is within normal variance because <Y>". Noise is a legitimate outcome; don't invent root causes.
- **Don't redo the investigation you just did.** The diagnosis output should let the on-call act without re-querying.
