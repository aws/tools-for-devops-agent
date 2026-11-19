---
name: clickstack-investigation
title: ClickHouse Observability investigations
description: Investigate incidents with the customer's logs, traces and metrics in ClickHouse Observability, the managed ClickStack service in ClickHouse Cloud, through the ClickStack MCP server. Covers finding data sources, checking service health, explaining error spikes, latency regressions and post-deploy changes, drilling into traces, querying OpenTelemetry metrics, and confirming every write with the operator. Use when an investigation or a chat question needs telemetry stored in ClickHouse Observability, ClickStack or ClickHouse, when the customer asks to search their ClickHouse Observability logs or traces, or when checking its alerts and dashboards.
metadata:
  author: "brandon-pereira"
  version: "1.0.0"
  tier: "partner-managed"
  summary: "Investigate incidents with ClickHouse Observability logs, traces and metrics through the ClickStack MCP server."
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# ClickHouse Observability investigations

The ClickHouse Observability connector reaches the customer's ClickHouse Observability service in ClickHouse Cloud through the hosted ClickStack MCP server. ClickStack is the open-source observability stack; ClickHouse Observability is the managed service built on it. The hosted server adds a few tools and arguments to the open-source one, such as required source filters. The connector acts as the person who connected it, so it sees only the data sources their role allows.

ClickStack stores OpenTelemetry logs, traces and metrics in ClickHouse. Each kind of data is a **source**: a table plus the column mappings ClickStack needs to query it. Every query tool takes a `sourceId`.

## Choosing tools

The server's instructions and each tool's description are kept current with the server. Read them before the first query; they give exact parameters and filter syntax. This skill gives the investigation order.

Prefer the purpose-built query tools. They return structured, ranked results and handle sampling, time bucketing and source mappings for you:

| Question | Tool |
|---|---|
| Which services are unhealthy right now, and compared with yesterday? | `clickstack_service_health` |
| What kinds of log messages or errors exist? | `clickstack_event_patterns` |
| What is new, or has stopped, since a baseline window? | `clickstack_emerging_signals` |
| What is different about the failing or slow rows? | `clickstack_event_deltas` |
| When did it start, and how did it trend? | `clickstack_timeseries` |
| Top-N, counts, breakdowns, single values | `clickstack_table` |
| Show me the raw rows | `clickstack_search` |
| Where does the time go in a slow operation? | `clickstack_trace_top_time_consuming_operations` |
| Show one example trace | `clickstack_trace_waterfall` |

`clickstack_sql` runs raw ClickHouse SQL. It is a last resort, for queries the tools above can't express: JOINs, sub-queries, window functions, or tables not registered as sources. A single-source aggregation, top-N, time series or row browse always uses a query tool.

If a tool you expect isn't available, the feature may not be enabled on the service. Say so in your findings rather than guessing.

## Step 1: Find the data

1. Call `clickstack_list_sources`. Note each source's `id`, its kind (log, trace, metric, session) and any `requiredSourceFilters`.
2. Call `clickstack_describe_source` on each source you'll query, before writing any filter. It returns the real column names and sample values. Never guess a column name.
3. If a source lists `requiredSourceFilters`, call `clickstack_get_source_filter_values` and pass `sourceFilters` on every query against it. Queries without them are rejected.
4. Map the incident's service to ClickStack's `ServiceName` values. Names often differ from AWS resource names: check the sampled values rather than assuming.

If no source holds the affected service's data, say so and stop querying ClickHouse Observability for it.

## Step 2: Set the time window

- Always pass `startTime` and `endTime` (ISO 8601). Several tools default to the last 15 minutes, which misses most incidents.
- Start from the incident or alarm time: from about 30 minutes before it to now, or to its end.
- If a query returns nothing, widen the window once (for example to 24 hours) before concluding the data doesn't exist.

## Step 3: Triage

1. If there is a trace source, call `clickstack_service_health` for the window. It ranks services worst first against the same window yesterday, with error groups and likely rollouts.
2. Branch on what it reports:
   - **A service is critical or degraded on errors**: go to "Error spike".
   - **A service is critical or degraded on latency**: go to "Latency regression".
   - **New operations or new error groups are flagged**: go to "Something changed".
   - **Everything is healthy**: that is a valid answer. Check logs with `clickstack_emerging_signals` for the window, then report that ClickHouse Observability shows no anomaly, rather than inventing one.
3. If there is no trace source, start with `clickstack_event_patterns` on the log source, filtered to the service and to error severity.

Before blaming a dependency, check the flagged service's own runtime metrics (memory, CPU, garbage collection, restarts) on the metric source.

## Error spike

1. `clickstack_timeseries` of error count for the service, by minute, to find when it started.
2. `clickstack_event_patterns` on the logs for the service and window, filtered to errors, to see which messages dominate. Each pattern has a `whereSnippet`: pass it as `where` to `clickstack_search` to read example rows.
3. `clickstack_event_deltas` with failing rows as the target and successful rows (or the window before the spike) as the baseline. Read the top five properties, not only the first: they are often independent causes, such as one version, one host, one endpoint or one customer.
4. If the errors are on spans, open one failing trace with `clickstack_trace_waterfall` (auto-pick mode with a filter on the error) to see which hop failed first.

## Latency regression

1. `clickstack_timeseries` of p95 or p99 `Duration` for the service, by minute, to find when it started.
2. `clickstack_table` grouped by `SpanName` for the service, to find which operations got slower.
3. For each slow operation, call `clickstack_trace_top_time_consuming_operations` once, with that service and operation as the parent filter and `minParentDurationMs` set to the slow threshold. Don't merge operations into one call. A child shared by several slow operations points to a shared cause.
4. `clickstack_event_deltas` on the dominant slow child, with slow rows (`Duration` above the threshold) as the target and fast rows as the baseline. Scope both to the same operation.
5. `clickstack_trace_waterfall` on one slow trace to confirm the finding with a concrete example.

## Something changed

Use this for "what changed", post-deploy checks, and new or disappearing behavior.

1. `clickstack_emerging_signals` with the current window and an earlier baseline of the same length, where the baseline ends when the current window starts. It returns patterns that emerged and patterns that disappeared.
2. For each emerging pattern, read example rows with `clickstack_search`.
3. Look for a version or deployment attribute (such as `service.version` in resource attributes) with `clickstack_table`, and compare before and after.

An empty emerging list means nothing novel. Report that rather than stretching small changes into findings.

## Metrics

Metric sources need more care than logs and traces. See [references/metrics.md](references/metrics.md) before querying one.

## Alerts and dashboards

- `clickstack_get_alert` with `state: "ALERT"` lists the alerts that are firing now. Check it at the start of an investigation for related alerts.
- `clickstack_search_dashboards` and `clickstack_get_dashboard` find dashboards the team already uses for a service. `clickstack_query_tile` runs a dashboard tile's query for your window.

## Writing filters

Most query tools take `where` and `whereLanguage`. See [references/query-syntax.md](references/query-syntax.md) for the syntax and its pitfalls, such as Lucene matching substrings rather than exact values.

## Keeping results small

- Prefer `clickstack_event_patterns`, `clickstack_table` and `clickstack_service_health` over raw rows. They summarize thousands of rows into a ranked list.
- With `clickstack_search`, filter tightly, set `columns` to the fields you need and keep `maxResults` small. Set `denoise: true` to hide high-frequency repetitive rows and surface the unusual ones.
- Scope every query to the affected service and window before widening.

## Reporting findings

- For each finding, give the tool, source, filter and time window that support it, so an operator can rerun it in ClickHouse Observability.
- Give numbers from the results, such as error rate before and after, p99 before and after, or the share of failing rows on one host. Don't round a shift into a conclusion the data doesn't support.
- State what you checked and found nothing in, as well as what you found.

## Rules for writes

A write is any call that creates, changes or deletes something in ClickHouse Observability: tools whose names start with `clickstack_save_`, `clickstack_patch_` or `clickstack_delete_`, and any tool whose description says it changes or shares content.

1. Make a write only when an operator explicitly asked for it. During triage and root-cause analysis, propose changes, such as a new alert or dashboard, as recommended actions instead.
2. Before each write, show the operator exactly what you'll do: the tool, the target and the full change.
3. Ask for confirmation immediately before the call, and make the call only after the operator confirms.
4. If the operator declines, or DevOps Agent's approval is denied, don't retry the write and don't try another tool to the same effect. Report that it wasn't made.
5. Never delete a source, dashboard, alert or webhook as part of an investigation.
