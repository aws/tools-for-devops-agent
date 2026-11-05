# Unpacking Vague Time-Series Requests

Users will often ask vague questions such as:

- "Show me data usage over the last 5 months"
- "Give me weekly usage by pillar and priority"
- "Are there anomalies in usage?"
- "Break down data usage over time by feature"

The mission of the LLM is to unpack these into a concrete analysis plan before answering.

### Default unpacking checklist

For any request of the form "data usage over X time, aggregated by Y, anomalies", the LLM should make these choices explicit:

- which usage concept is being analyzed
- which metric maps to that concept
- which time bucket is being used
- whether partial periods are excluded
- which grouping labels are used
- whether deltas are absolute, percentage, or both
- how anomalies are being judged

### Metric choice by concept

Use the [default concept-to-metric mapping](metrics.md#default-concept-to-metric-mapping).

If the user does not specify the concept clearly, the LLM should not silently change between units and bytes. It should either:

- state the assumption it is using
- or ask a clarification question if the distinction materially changes the answer

### Time-bucket rule

When the user asks for aggregation by:

- day -> use completed UTC days
- week -> build weekly totals from completed UTC days
- month -> build monthly totals from completed UTC days
- hour -> treat this as partial-day / intraday analysis and warn accordingly

Important:

- weekly and monthly answers should not be derived directly from raw day-cumulative series
- the LLM should first derive completed daily totals, then roll those daily totals up into weeks or months

### Partial-period rule

Unless the user explicitly asks for a partial period:

- exclude the current UTC day
- exclude the current week if the requested output is weekly
- exclude the current month if the requested output is monthly
- say this clearly in the response and explain that partial periods distort completed-period comparisons

### Delta rule

When the user asks for "deltas", the LLM should default to:

- absolute delta for the requested bucket
- percentage delta for the requested bucket

If only one is shown, the LLM should say which one it chose.

### Analysis-plan phrasing

For vague requests, the LLM should translate the ask into wording like:

- "I will use `cx_data_usage_units`, derive completed daily UTC totals, roll them into completed UTC weeks, group by `pillar` and `priority`, and compute week-over-week deltas."

This removes ambiguity before presenting findings.

