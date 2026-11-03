---
name: honeycomb-observability-fundamentals
description: 'Load when the operator asks a conceptual question about observability or Honeycomb: what observability is, why wide events, what high cardinality or dimensionality means, events vs metrics vs logs, observability vs monitoring, or the core analysis loop. Grounds recommendations in first principles. Not for running queries or investigating a live issue.'
metadata:
  author: "honeycombio/agentic-intelligence"
  version: "1.0.0"
  summary: "Explain the first principles behind Honeycomb: wide events, high cardinality and the core analysis loop."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Honeycomb Observability Fundamentals

First principles behind Honeycomb's approach to observability. Use this to ground
recommendations and answer conceptual questions — for query guidance, see the
**honeycomb-query-patterns** skill.

## Definitions

**Observability**: The ability to understand and explain any state your system can
get into, no matter how novel or complex — by examining what the system produces,
without deploying new code for each new question.

**Wide event**: A flat key-value record capturing the full context of a unit of work —
who made the request, which endpoint, cache hit/miss, build version, duration, error
status, and any business context relevant to the operation. In OpenTelemetry, a **span**
is a wide event.

**High cardinality**: The number of unique values a field can have. `user.id` with
millions of values is high cardinality. `http.method` with a handful is low cardinality.

**High dimensionality**: The number of distinct fields on your events. A span with
50 attributes has high dimensionality.

| Concept | Observability | Traditional Monitoring |
|---|---|---|
| Questions | Arbitrary, unknown ahead of time | Pre-defined (dashboards, alerts) |
| Data shape | Decided at query time | Decided at instrumentation time |
| Cardinality | High cardinality is valuable | High cardinality is expensive |
| Investigation | Explore → narrow → confirm | Check dashboard → escalate |

## Why Wide Events

The shape of the data you collect constrains the questions you can ask later. Metrics
pre-aggregate context away at instrumentation time. Wide events preserve context and
let you decide the shape of your analysis at query time.

Every attribute on a span is a queryable dimension. Adding `user.id`, `deployment.version`,
and `cache.hit` to the same span lets you correlate them in a single query — "slow
requests are from tenant X on version 2.3.1 with cache misses." Separate metrics can't
do this because each dimension combination creates a new time series.

Honeycomb's storage engine handles high cardinality and dimensionality without the
cost explosion that affects metrics systems. Adding a high-cardinality field like
`user.id` doesn't create millions of time series — it's another column on each event,
aggregated at query time.

## Events vs Metrics vs Logs

| | Structured Events (Spans) | Metrics | Logs |
|---|---|---|---|
| **Captures** | Full request context (all attributes) | Pre-aggregated numbers with low-cardinality tags | Text or structured fields per line |
| **Discards** | Nothing — raw events retained | Individual requests, high-cardinality dimensions | Correlation across lines (without trace context) |
| **Query power** | GROUP BY, filter, BubbleUp on any dimension | Fast aggregates on pre-defined dimensions | Text search, structured field queries |
| **Cost scaling** | Linear with event volume | Exponential with dimension count (cardinality) | Linear with volume, query cost varies |
| **Best for** | Investigation, root cause analysis | Cheap alerting, long-term trends | Audit trails, rare events |

The same instrumentation effort that produces a metric or log line can produce a wide
event — and the event gives you all three capabilities: count it (metric), read it (log),
analyze it across dimensions (observability).

For code examples showing the same operation instrumented three ways, see
`references/events-vs-metrics-vs-logs.md`.

## The Core Analysis Loop

Debugging in Honeycomb follows a loop: **Define → Visualize → Investigate → Evaluate**.

1. **Define** — Frame the question. Start from an alert, SLO budget burn, or user report.
2. **Visualize** — Run a query to see the shape of the problem (HEATMAP, COUNT, P99).
3. **Investigate** — Narrow down with BubbleUp (automated outlier-vs-baseline comparison
   across all dimensions) and trace analysis.
4. **Evaluate** — Confirm the hypothesis by querying with and without the suspected cause.

Then loop — each answer raises new questions. BubbleUp automates steps 2-3 by comparing
distributions across every column, but it only works if events have enough dimensions
to diff on.

For the structured workflow that implements this loop with Honeycomb's tools, see the
**honeycomb-production-investigation** skill.

## Instrumentation Connects to Investigation

Every attribute on a span is a dimension BubbleUp can use to find root causes. The
attributes that matter most during incidents answer three questions:

- **Who is affected?** — user, tenant, account tier, region
- **What changed?** — deployment version, feature flag, config version
- **Where is the bottleneck?** — business operation spans, timing breakdowns, cache state

Instrument for the questions you'll ask at 3am, not for completeness. If BubbleUp
returns nothing useful during an investigation, the issue is usually an instrumentation
gap — add the missing dimensions and try again.

## Instrumentation as a Development Practice

Instrumentation is not a one-time setup task. The engineers who write the code are best
positioned to know which operations are critical, which paths are error-prone, and what
context helps during debugging. Treat instrumentation like testing: plan telemetry when
planning features, review it in code reviews, and add missing dimensions as post-incident
follow-ups.

## Additional Resources

### Reference Files
- **`references/events-vs-metrics-vs-logs.md`** — Code examples: same operation as event, metric, and log

### Cross-References
- For query construction patterns: **honeycomb-query-patterns** skill
- For the investigation workflow implementing the core analysis loop: **honeycomb-production-investigation** skill
