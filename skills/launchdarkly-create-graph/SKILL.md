---
name: launchdarkly-create-graph
description: "Creates observability dashboards and graphs from logs, traces, errors, sessions, metrics, and events data by previewing charts inline and saving them to a dashboard."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Create graphs and dashboards

## Prerequisites

This skill uses the following LaunchDarkly MCP tools:

- `preview-graph` — render a chart preview inline without saving it
- `create-graph` — add a chart to an existing dashboard
- `create-dashboard` — create a new empty dashboard
- `list-dashboards` — list existing dashboards
- `get-dashboard` — get the full config of a dashboard, including its graphs
- `get-keys` — discover available metrics, attributes, and keys for a product type

All of these tools require a `projectKey` (e.g. `"default"`).

## Overview

You are building observability graphs. Your tools are precise — get the enum values wrong and the API rejects the call. Always use `get-keys` before building a query to confirm the dimension names are real.

## Capabilities

- `list-dashboards` — list existing dashboards to check for duplicates or find a target
- `get-dashboard` — get the full config of an existing dashboard, including its graphs
- `create-dashboard` — create a new dashboard
- `preview-graph` — render a chart preview inline
- `create-graph` — add a chart to a dashboard
- `get-keys` — discover available metrics, attributes, and keys for a product type

When the user's request is purely about visualizing data, stay on task — don't reach for unrelated tools.

## Workflow

1. **Identify the target dashboard.** If the user already has a specific dashboard in mind (by ID or name), add graphs to it directly. Otherwise, call `list-dashboards` and offer to target an existing one or create a new one with `create-dashboard`.
2. **Discover the data shape.** Call `get-keys` for the relevant product type before building a query. Attribute names vary across services — `service_name` vs `service.name` vs `serviceName`. Guessing wastes tool calls.
3. **For ambiguous requests, ask a brief clarifying question** as regular text. Example: "I found several latency-related keys. Would you like P50 or P95 latency, and should I group by service name?" Keep clarifications short — one or two questions max. For minor ambiguity (chart type preference), make a reasonable default and note your assumption.
4. **Preview before committing.** Call `preview-graph` first, show the user an inline preview, and confirm before calling `create-graph`. For multiple graphs, preview and confirm each one individually.
5. **Create the graph** with `create-graph`. Use exact enum casing from `enums.md`.
6. **Confirm what was created** — provide the dashboard URL and a one-line description of what the graph shows.

## Duplicating existing graphs

When asked to duplicate or copy a graph, call `get-dashboard` to retrieve the full configuration (expressions, product type, query, groupBy, display settings), then replicate those values in `create-graph`. Do not guess from the graph title alone — titles drift from the underlying config.

## Guidelines

- **Be concise — don't narrate intermediate tool calls.** Skip prefaces like "First, let me discover the keys" or "Now I'll build the chart." One short sentence at the start of the reply is enough if needed (e.g. "Building a chart of recent logs by level."); after that, just call the tools.
- **Prefer multiple focused graphs over one complex graph.** A dashboard with 3 clean graphs beats one graph with 5 overlapping expressions.
- **Always call `get-keys` before building a query.** Prevents silent empty results from wrong field names.

## Chart-type picks

- **`Line chart`** — time-series trends. Error rates over time, latency percentiles, request volume.
- **`Bar chart`** (or histogram) — comparisons across a dimension. Errors by service, requests by endpoint.
- **`Table`** — detailed breakdowns with multiple dimensions where a chart wouldn't convey the detail.

## Aggregators

- `Count` — total events (most common). Requires `column=""` (empty string).
- `CountDistinct` — unique values. Users, sessions, flag keys.
- `Avg`, `P50`, `P90`, `P95`, `P99` — latency distributions.
- `Sum` — numeric totals (payload size, revenue).

## Common mistakes

- Using lowercase `sessions` for `productType`. It's `Sessions` — PascalCase. See `enums.md`.
- Omitting `column` on a `Count` expression. The API requires it; pass empty string `""`.
- Using `count_distinct` or `Count_distinct`. It's `CountDistinct` — PascalCase, no underscore.
- Building a query without `get-keys` first and getting empty results because the attribute name was wrong.
- Using date-only format (`2026-03-04`) for `get-keys`. Needs full ISO with time: `2026-03-04T00:00:00Z`.
