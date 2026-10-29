---
name: launchdarkly-investigate
description: "Analyzes observability data — logs, traces, errors, sessions, and metrics — to find root cause and actionable evidence. Use when the user reports a bug, an unexpected behavior, or asks about patterns across application data."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: launchdarkly
  version: "1.0.0"
---

# Investigate

You are conducting a cross-product investigation. Real investigations almost always touch more than one product — a log error leads into traces, a slow trace reveals a failing span, a failing span correlates with a specific session. Walk the evidence until you have a concrete root cause.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server to be configured in your environment.

**Required MCP tools:**
- `query-logs` — fetch paginated log entries
- `query-traces` — fetch paginated trace/span entries
- `query-error-groups` — fetch error groups with stack traces and frequency
- `query-sessions` — fetch session replays with user details
- `query-aggregations` — bucketed aggregations across a product type for trends and counts
- `query-timeline-events` — pull the chronological event timeline within a session
- `get-keys` — discover valid attribute/grouping keys for a product type

## Workflow

1. **Plan first.** Before the first tool call, present a concise numbered plan of what you intend to query and why. Then execute it. Skip this only for trivial lookups.
2. **Start narrow.** Pick a focused time window (default 24h if the user didn't specify) and the most-specific identifier you have — trace ID, session ID, error group ID, flag key. Broad queries return noise.
3. **Let each result inform the next.** Do not rely on one tool call. Run multiple invocations of `query-logs`, `query-aggregations`, `query-traces`, `query-error-groups`, and `query-sessions`, using the findings of each to sharpen the next.
4. **Respect the 50-entry limit.** `query-logs`, `query-traces`, `query-error-groups`, and `query-sessions` tools return at most 50 entries per call. For larger datasets, run a `query-aggregations` query first to aggregate, then narrow with targeted fetches.
5. **Cross-reference aggressively.** Trace IDs in logs, session IDs in errors, error messages in session replays — the point where products connect is usually where the root cause sits.
6. **Maintain a running checklist.** Periodically summarize what you've confirmed vs. what you still need to test. Keeps investigations from drifting.
7. **End with actionable output.** Clear insights that answer the original question, direct references the user can click through (log excerpts, trace IDs, session IDs, error group IDs), a severity assessment, and at least one concrete remediation — a config change, a flag flip, a code-level fix with file and line, or a specific diagnostic step with the exact query to run.

## Load companion files when relevant

- `logs.md` — when the investigation touches logs (error messages, level=error filters, service log patterns)
- `traces.md` — when analyzing request flow, latency, or span relationships
- `errors.md` — when looking at error groups, stack traces, exception frequency
- `sessions.md` — when reconstructing user journeys or correlating frontend behavior with backend events
- `metrics.md` — when aggregating across a large dataset or building a chart
- `relationship-search.md` — when a sessions question depends on how events relate: order (`THEN`), absence (`no_span`), co-occurrence (`AND`), or alternatives (`OR`), including spans vs. logs

## Universal guidance

- **Prefer aggregation over pagination.** If you want to list unique users, count distinct values, or summarize, use `query-aggregations` with `group_by` — don't paginate through individual records. Use `get-keys` to discover the right grouping dimension first.
- **Call `get-keys` before attribute filters.** Attribute names vary across product types and services (`spanName` vs `span_name`, `hasErrors` vs `has_errors`). One `get-keys` call upfront prevents wasted queries with wrong field names.
- **Cite specific identifiers.** Every recommendation should reference the exact flag key, service name, session ID, trace ID, or file path you pulled from the data. The user should be able to act on your summary without redoing your investigation.
- **Handle large tool outputs.** When a tool result is persisted to a file (you'll see "Output too large ... Full output saved to: <path>"), do NOT use Read — it has the same token limit. Use Bash with `python3` or `jq` to extract the specific slice you need.
- **Graceful degradation on tool failure.** If a tool call fails (buffer overflow, timeout, server error), don't end silently. Try an alternative tool or approach. If nothing works, deliver what you've found so far plus concrete next steps the user can take manually.
- **Handling vague requests.** "Investigate this" or "what's going on" is an invitation to dig, not to summarize. Iterate tool calls until you have a root cause or have exhausted the available data.

If a tool isn't available in your environment, the corresponding MCP server may not be connected — surface that rather than working around it.
