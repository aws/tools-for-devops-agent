---
name: honeycomb-production-investigation
description: 'Load when an investigation needs Honeycomb telemetry to find a root cause: a latency spike, an error surge, a deployment regression, a failing dependency or an SLO burning budget. Gives the order of Honeycomb MCP tool calls (orient, broad query, BubbleUp, trace drill-down, verification) and how to carry each result into the next step.'
metadata:
  author: "honeycombio/agentic-intelligence"
  version: "1.0.0"
  summary: "Investigate latency, errors, regressions and dependency failures with Honeycomb queries, BubbleUp and traces."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Honeycomb Production Investigation

Structured workflows for debugging production issues. The MCP tools document their
own parameters — this skill focuses on the *sequence* of tool calls and how to
*interpret* results to reach a root cause.

## The Core Analysis Loop

This workflow implements the core analysis loop: **Define → Visualize → Investigate →
Evaluate**. If BubbleUp returns nothing useful, the issue is often an instrumentation gap:
report which attributes are missing so the team can add them.

Requires the Honeycomb connector in the Agent Space, with its read tools enabled. Creating a board, SLO or trigger needs write access: **Read-write** at sign-in, or a key with **Write** under **Model Context Protocol**. If a create tool is missing or returns a permission error, stop and tell the operator that it needs write access. Do not retry.

## Investigation Workflow

### Step 1: Orient
1. `get_workspace_context` → environments and datasets
2. `get_slos` → any SLOs in violation? (frames severity)
3. `get_triggers` → any alerts firing? (narrows scope)
4. `find_queries` → has anyone investigated this before?

### Step 2: Characterize the Problem
Run a broad query to see the shape of the issue:
- **Latency spike**: P99(duration_ms), HEATMAP(duration_ms) grouped by service or route
- **Error surge**: count failed operation spans (`error=true`) by service/route/category, then
  separately count exception event rows using `event.name=exception` and `exception.type exists`;
  use sampled `trace.trace_id` values to drill into representative traces
- **Unknown**: COUNT grouped by service.name to find which service has anomalous volume

Also call `get_service_map` — it shows P95 durations between services and can immediately reveal which dependency is slow.

**Exception data has two query surfaces:** operation failures belong on spans (`error=true`, span
status, low-cardinality `exception.slug`/error category); full exception diagnostics may belong on
trace-correlated Logs API event rows. Do not assume `exception.*` exists on the containing span.
When investigating exceptions, discover the dataset schema first, query `event.name=exception`
with `exception.type exists` and `trace.trace_id exists`, take a sample, then pass its
`trace.trace_id` to `get_trace(show_events=true)`. For legacy span-event exceptions, also check
`name=exception` and `meta.signal_type=trace`; Logs API events use `event.name`/`body` and
`meta.signal_type=log`.

If a service uses an exception-promoting `LogRecordProcessor`, some `exception.*` fields may also
appear on the containing span. Treat that as an explicit client-side compatibility feature, not a
Honeycomb guarantee: the event row remains authoritative for full diagnostics, and absence of
parent-span fields does not mean the exception event is missing.

### Step 3: BubbleUp to Find Differentiators
This is the highest-value step. Once you have a query showing the anomaly:
1. Run `run_bubbleup` on the query result, selecting the outlier region
2. BubbleUp compares outlier vs baseline distributions across *all* columns automatically
3. Look for fields where the distributions differ significantly

**How to interpret BubbleUp results:**
- **Categorical fields** (dimensions): A value overrepresented in outliers points to a cause (e.g., `deployment.version=v2.3.1` is 90% of slow requests but only 20% of baseline)
- **Numeric fields** (measures): A shifted distribution shows correlated metrics (e.g., `db.query_duration` is much higher in outliers)
- **Typical root causes surfaced**: deployment version, region, user cohort, specific endpoint, feature flag

### Step 4: Drill Into Traces
After BubbleUp identifies suspects:
1. Add BubbleUp findings as WHERE filters to narrow results
2. Pick a representative trace ID
3. Call `get_trace` to fetch the full trace

**What to look for in the trace waterfall:**
- Spans with disproportionate duration vs parent (the bottleneck)
- Sequential spans that could be parallelized (N+1 query patterns)
- Error spans — check span events for stack traces
- Gaps between child spans (missing instrumentation or idle wait)
- Service boundaries (where the trace crosses services)

### Step 5: Verify Hypothesis
Form a hypothesis from BubbleUp + trace analysis, then confirm:
- Query WITH the suspected cause filtered in
- Query WITHOUT it (as a control)
- If the metrics diverge, you've found it

### Step 6: Record Findings
Report the root cause with the query run PKs and trace IDs that support it. Only if the
operator asks for a Honeycomb board, show the proposed title, panels and SLOs, and call
`create_board` only after the operator approves. The board holds:
- A text panel summarizing the root cause (Markdown)
- The key query run PKs that identified the problem
- Related SLOs if applicable

## Investigation Patterns

### Latency Spike
HEATMAP first → BubbleUp the slow region → trace a slow request → verify with filtered queries

### Error Surge
Count failed operation spans by service/route/category → count Logs API exception events by
`event.name=exception` and `exception.type` → sample `trace.trace_id` → `get_trace(show_events=true)`
→ verify with filtered queries. Do not use `exception.message` on the parent span as the only
exception search.

### Deployment Regression
P99 grouped by deployment.version → BubbleUp comparing new vs old → trace from new version → verify

### Dependency Failure
`get_service_map` → P99 on the slow dependency → relational query (`any.service.name`) to measure user impact → trace an affected request

## Stay on the Path

If you find yourself reasoning any of these, follow the workflow anyway:
- "The cause is obvious, I can skip BubbleUp" — BubbleUp routinely surfaces causes that seem obvious in hindsight but weren't the first guess. It also catches *secondary* causes you'd miss entirely.
- "I already know it's a deployment issue" — verify with Step 5. Confirmation bias is strongest during incidents. Query with and without the suspected cause.
- "Traces confirmed it, no need to verify" — a single trace is an anecdote. The verification query proves the pattern holds across all traffic, not just one request.
- "This is a simple issue, the full workflow is overkill" — the workflow takes minutes; a wrong diagnosis during an incident costs hours.

## When Results Are Empty or Unclear

- **No results**: Check field names with `find_columns`, expand time range, verify environment/dataset
- **BubbleUp shows no signal**: Try a different time selection, add filters to isolate the anomaly more clearly, or select a different calculation
- **Trace missing spans**: Sampling, instrumentation gaps, or cross-environment trace split

## Additional Resources

### Reference Files
- **`references/investigation-playbooks.md`** — Step-by-step playbooks for latency spikes, error surges, deployment regressions, dependency failures, SLO budget burn, and health checks
- **`references/bubbleup-guide.md`** — Detailed BubbleUp usage: selection types, time specifications, pagination, result interpretation
- **`references/trace-exploration.md`** — Trace structure, get_trace parameters and view modes, waterfall analysis, span events and links

### Cross-References
- For the conceptual foundations of the core analysis loop, see the **honeycomb-observability-fundamentals** skill
- For query construction patterns, see the **honeycomb-query-patterns** skill
- For SLO/trigger context during investigations, see the **honeycomb-slos-and-triggers** skill
