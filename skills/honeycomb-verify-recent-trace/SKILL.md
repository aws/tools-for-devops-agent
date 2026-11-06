---
name: honeycomb-verify-recent-trace
description: 'Load when the operator asks to verify a recent test or deployment in Honeycomb, find the most recent trace, or show the trace a test produced. Finds the traces created since the test started and summarizes the most recent one.'
metadata:
  author: "honeycombio/agentic-intelligence"
  version: "1.0.0"
  summary: "Find and summarize the Honeycomb traces a recent test or deployment produced."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "RELEASE_TESTING, CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Honeycomb Verify Recent Trace

Requires the Honeycomb connector in the Agent Space, with its read tools enabled.

## Purpose

Query Honeycomb to find the traces that were created by a recent test.

## When to Use

- The operator asks to "show me a trace in Honeycomb"
- A test or release step needs observability verification

## Verification Output

Report query results as:
Queried [VIZ] where [FILTERS] by [GROUP_BY] over [TIME_RANGE]
Results: [link to Honeycomb query]

## Query Patterns

- **Time Range**: 1200 seconds (20 minutes) - adjustable based on when the test started

### Pattern 1: Get a particular trace

What service are you testing? This determines the dataset.
Do you know the name of the span you expect to see?

```
Query for:
- dataset: [dataset]
- filter: name = [expected span name]
- time_range: [calculated time range]
- calculation: COUNT
- include_samples: true
```

Now take the most recent sample, and use get_trace to get the full trace.
Output:

Queried [CALCULATION] where [FILTERS] over [TIME_RANGE]
Found [count] results
Results: [link to the query]

Most recent trace: [link to the trace]
Root span: [root span name]
Total spans: [count of spans]
Services: [list of services]

### Pattern 2: Find all traces since the test started

```
Query for:
- all datasets
- filter: trace.parent_id does-not-exist
- time_range: [calculated time range]
- calculation: COUNT
- breakdowns: name
- include_samples: true
```

Output:
Queried [CALCULATION] where [FILTERS] by [BREAKDOWNS] over [TIME_RANGE]
Found [count] results
Results: [link to the query]

For each sample, print:

- Trace ID
- Span name
- A link to the trace, from the query results or the `get_trace` output

### Pattern 3: Find the most recent trace, precisely

```
Query for:
  calculated_fields: event_time=EVENT_TIMESTAMP()
  calculation: COUNT
  breakdowns: event_time, trace.trace_id
  order: event_time DESC
  limit: 1
  include_samples: false
```

Print the summary of the trace, as in Pattern 1.

Take the output trace_id and use get_trace to get the full trace.

### Pattern 4: When you don't see any traces, get the time range right

Find out when the test or deployment started: from the operator, or from the release
or test record you are working from.

Set the time range to the seconds since that start time, plus 20 seconds.

Include that in the query you're using to find traces.
