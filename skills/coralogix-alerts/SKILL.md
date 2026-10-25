---
name: coralogix-alerts
description: Alert and case terminology, alert definitions, alert events, cases, IDs, alert types, and skill routing. Load whenever working with alerts or cases to understand shared terminology.
metadata:
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
aws-devops-agent-skills:
  agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION,INCIDENT_UI"
---

# Alerts & Cases Guidance

## Coralogix Alert Terminology

### Object Types
- **Alert Definition** — The general specification of an alert. Example: "Check that there are no new logs in the last 5 minutes."
- **Alert Event** — An event created when an alert definition's condition occurs (e.g., There are no new logs for 5 minutes).
- **Case** — The lifecycle wrapper around one or more triggered alert events created from a single alert definition, with user-controlled fields (e.g., `status = acknowledged`).

### Different IDs
- **Alert Definition Version ID** - Identifier for an alert definition. This represents an immutable Alert Definition, when an Alert Definition is edited, a new Version ID is created. Prefer to use this over the Alert Definition ID.
- **Alert Definition ID** — A wrapper ID that always points to the latest Alert Definition Version ID.
- **Case ID** — Identifier for a case.
- **readable_id** — An additional human-readable identifier for cases that have become Active, e.g. "CASE-123". Query full case info with the `get_alerts_object` tool. This does not replace the Case Name, it is just an additional id.
Note: These naming conventions are confusing, be explicit about the naming and don't rephrase them.

**Important**: DO NOT rephrase the Object type names, use the exact names as they are. Unless the user requests it, do not explain Alert Definition ID and Alert Definition Version ID.

### Group By

An Alert Definition can define `group_by_keys`: one or more dimension names (e.g. `service`, `region`, `subsystem`) that control how the alert segments alert events into cases. There are two modes:

- **Split/Combination** — each unique combination of key values that hits the threshold gets its own separate case. Example: a "High CPU" alert with `group_by_keys: [service, region]` creates distinct cases for `(payment-api, us-west-2)`, `(order-api, eu-west-1)`, etc.
- **Aggregated/Composite** — all matching permutations are merged into one combined case.

When a user references an entity — a country, region, service, application, subsystem, etc. (e.g. "cases from Israel", "alerts for checkoutservice") — it might be a **permutation** key or value. See `Permutation Keys` in `coralogix-case-analytics` skill.

### Coralogix Alert Types & Use Cases

1. **Logs - Standard Alerts (Count Alerts)**
   Count logs matching a lucene query within a timeframe and trigger based on threshold conditions.
   **Conditions:** `more_than`, `less_than` *(deadman)*, `more_than_usual` *(baseline anomaly)*, `new_value`.

2. **Logs - Ratio Alerts**
   Calculate the ratio between two lucene logs queries and trigger when the ratio crosses a threshold.

3. **Logs - Unique Count Alerts**
   Count unique values of a field from logs matching a lucene query and trigger if the count exceeds a threshold.

4. **Logs - Relative Time Alerts**
   Compare current period results to a previous period (hour/day granularity) for a lucene logs query to detect changes.

5. **Metrics - Metric Alerts**
   Trigger when metrics exceed or fall below thresholds.

6. **Traces - Tracing-based Alerts**
   Filter and alert on tracing span data, tag values, and latency thresholds.

### Alert Priority Levels

Alert priorities are from highest to lowest:
P1: Critical
P2: High
P3: Medium
P4: Low
P5: Info

### Miscellaneous
- Phantom mode: An Alert Definition that is a building block and won't create events or cases.
- Alerts use lucene queries, not dataprime queries.
- Case activation: when a Coralogix case moves from Pending Activation to Active, meaning the issue's impact has been confirmed and responders should start working it.
- KPI (Key Performance Indicator): User-configured SLAs on case lifecycle steps (e.g. time-to-acknowledge, time-to-resolve). A breach record is emitted when a case misses one.

---

## Alert Investigation

### Mission

- Investigate alert definitions and alert events using the available tools.
- Analyze alert configurations, event data, and related cases.
- Explain *why* an alert triggered (queries, thresholds, conditions, time windows).
- Propose concrete next steps for investigation and resolution.

### Alert definitions and events (alerts without a case yet)

Note: This section is for tooling Alert Definitions and Alert Events.
For Cases see the following skills.

#### Available Tools For Alerts (Read-Only Investigation)

**is_verbose mode**: All tools have the `is_verbose` parameter, which is used to return verbose information.
Start with `is_verbose=False` and only pass `True` if the required information is not available in the non-verbose mode or if the user asks for extended information.
**Empty fields**: For `is_verbose=False`, empty sub results will be removed. E.g. `assignee= None` will be removed.
For `is_verbose=True`, empty sub results will be kept. E.g. you'll get `assignee=None` in the response, and can know for sure that this field is empty.
**Case verbose-only fields**: When fetching a case via `get_alerts_object`, `kpi_breaches` and `impacted_entities` are only included with `is_verbose=True`.

Use these tools exactly as described:

- **`get_alerts_object`**
  Retrieve detailed information for a specific object by its ID. Use this for any alert-related ID before using the ID for other tools.
    Returns any of the following:
        - Alert Definition: Detailed information about the alert definition + related cases.
        - Case: Detailed information about the case + related alert indicators. `object_id` may be a GUID or a readable id (e.g. "CASE-123").
        - Alert Event: Detailed information about the alert event.
    Args:
        object_id: MUST BE A VALID GUID: the ID of the object to retrieve data for. For cases, it can also be a readable id (e.g. "CASE-123").
        object_type_hint: Optional. If provided this will be initially used to guess the type of object. BEWARE THE FINAL RESULT MAY DIFFER FROM THE INITIAL GUESS!
        get_watch_data: If True, fetch watch data for the object. Watch data is comprehensive alert-event context for root cause analysis: the actual logs and the **DataPrime** query that triggered the alert.
    When `get_watch_data` is True:
    - Alert Event: on success, the tool returns the watch data which includes the event.
    - Case or Alert Definition: output includes `watch_data` from the most recent related event.
- **`search_alert_definitions`**
  Search and return alert definitions in the team with flexible filters.
  This tool only returns alert definitions, not any triggered alert events or cases.
      Optional Args:
        order_bys: List of order by fields to sort the results by
        name: List of alert names to filter by
        name_matcher: How to match names (e.g. if `name_matcher` is `CONTAINS`, strings in `name` should be contained in the found alert name)
        alert_types: List of alert types to filter by
        alert_type_matcher: How to match alert types (e.g. types in `alert_types` should be equal to the found alert type)
        priorities: List of alert priorities to filter by
        priority_matcher: How to match priorities (e.g. priorities in `priorities` should not be equal to the found alert priority)
        enabled: Filter by enabled status (True for enabled alerts, False for disabled alerts)
        modified_start_time: Start time for modification date filter
        modified_end_time: End time for modification date filter
        last_triggered_start_time: Start time for last triggered date filter
        last_triggered_end_time: End time for last triggered date filter

**General Tooling Rules**
- NEVER guess or generate IDs!
- When the user provides an alert name, filter alerts by name rather than id to catch all alert versions.
- Prefer explicit IDs provided by the user or discovered via search.
- Include the **timeframe** and note UTC in your reasoning and responses.
- If data is missing or unavailable, say so clearly; do not fabricate.
- Always prefer to use the tools with filters. If you don't have enough information, ask the user for more information. If that doesn't work, try to use the tools without filters.

---

### Alert Investigation Guidelines

- **Timeline Analysis:** Always examine timing and frequency of alert events within cases.
- **Quantify:** Prefer numbers, rates, and ratios over vague descriptions.
- **Be Explicit:** Include evaluation windows and conditions (e.g., "`more_than` 500 in 10m").
- **Stay Grounded:** Only use information returned by the tools. Do not speculate beyond the evidence.
- **Further details**: Results from cases will contain related alert event ids. For triggering logs and the DataPrime query, call `get_alerts_object` with `get_watch_data=True` (use the alert event ID, or a case/definition ID to resolve the most recent event).

### Filtering Rules
- If the user asks an aggregation question, use the correct tool to search for all results and use the returned `search_results_metadata` field. Also suggest to the user to answer the question using cases for better results, and only if so load the `coralogix-case-analytics` skill.
- When the user asks about a specific Alert Definition grouped by a specific key, get it from the `group_by_keys` field of the Alert Definition.

### Dataset Source: `system/alerts.history`
- Alerts can also be analyzed as a dataset with DataPrime using `source system/alerts.history`.
- If it fails, the user may not have permission to access this alerts dataset, so use other tools.

---

## Skill routing

### When to use case-analytics vs single-case

| Question shape | Skill to load | Examples |
|---|---|---|
| One specific case (lifecycle, comments, KPI breaches, notifications, resolution) | `coralogix-single-case` | "summarize CASE-123", "who was notified for this case", "walk the lifecycle of CASE-456" |
| Fleet / aggregate (counts, trends, MTTR/MTTA/MTBI, listings, label/alert enumeration, historical analytics, bulk operations) | `coralogix-case-analytics` | "how many P1 cases this week", "show me all active cases", "list resolved cases in the last 24h", "MTTR per team", "which environments are routed to", "which alerts opened cases last 7d", "most frequent alert this month", "is this assignee overloaded" |
| Alert definitions or alert events (queries, thresholds, conditions, time windows, permutations, event payloads) | Use tools in this skill | "why did this alert trigger", "fetch alert definition by ID", "show triggering evidence", "what type of alert is this", "investigate permutation combinations" |

> For all fleet-level questions, always drive DataPrime queries via `coralogix-case-analytics` — do not page through `get_alerts_object` one case at a time; the per-case APIs are scoped to a single case ID and the answer will be wrong.
> If the user pivots from "this case" to fleet questions (counts, trends, MTTR/MTTA/MTBI, listings, label/alert enumeration), switch to `coralogix-case-analytics`. Generic "look at our cases" asks — clarify which specific case before loading `coralogix-single-case`.

### Dataset vs cases API — freshness and point-in-time semantics

The dataset and the cases API (used by `coralogix-single-case`) are **not interchangeable**. They have different freshness guarantees and fundamentally different time semantics. Internalize this before answering any single-case question.

**1. The dataset has a processing lag.** State changes in the Cases service flow through an event pipeline before they're queryable here. The lag is normally seconds-to-minutes but can spike. The cases API, by contrast, reads the live store. **For "what's the current status of case X" style questions about a single case, the cases API via `coralogix-single-case` is fresher and authoritative** — even though the dataset *could* answer, its answer may be a few minutes behind.

**2. The dataset returns state as of the query window, not state as of now.** This is the bigger and less obvious distinction:

| Query shape | What you get |
|---|---|
| A relative window ending at now (e.g. last 1h / last 7d) | The case's **latest known state as of now**, assuming it had any event (state change or heartbeat) inside that window. This is what you want for "active / resolved / by-team right now" style analytics. |
| An explicit window in the past (e.g. 2026-02-01T00:00 to 2026-02-15T00:00) | The case's **state as it was during that window** — its status, priority, assignee at the time, not today. The case may since have been resolved, reassigned, escalated; the dataset will not show that because those later events fall outside the requested window. |

**The cases API always returns the latest known state, regardless of any time range.** It is incapable of "time travel" — it has no notion of "what was the status on Feb 10". The dataset is the only source for that.

**3. Implications for query design**

- **Current-state fleet analytics** ("currently active cases", "open P1 right now", "MTTR over the last 7d") → use a window that **ends at now** (`last <duration>`).
- **Historical / point-in-time questions** ("how many P1 cases were open on March 5", "what was this case's status last Tuesday") → use an explicit past window. The dataset is the only place this works. Tell the user the answer reflects the state at that time, not today's state.
- **Single-case "right now" questions** ("what's the status of CASE-123 today") → this skill is the wrong tool. Route to `coralogix-single-case`, which hits the API and is always fresh + always latest.
- **Single-case "what did it look like back then" questions** → fine to answer here with a past window, but disclose that you're reading historical state and that the live state may have moved on.
