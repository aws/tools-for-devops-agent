---
name: coralogix-case-analytics
description: Fleet/aggregate analytics across many cases via the `system/labs.cases.state_updates` DataPrime dataset. Load when the user asks counts, trends, distributions or rates across cases — e.g. "MTTR last week", "how many P1 cases today", "active case count per team", "list active cases", "how long until activation on average". Do NOT load for one specific case ID — use alert tools for single-case investigation. Load the `coralogix-dataprime` skill alongside this skill.
metadata:
  summary: "Analyze case counts, trends, distributions, and lifecycle metrics across a Coralogix case fleet."
  author: "coralogix"
  version: "1.0.0"
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "CHAT,INCIDENT_TRIAGE,INCIDENT_RCA,INCIDENT_MITIGATION,INCIDENT_UI"
---

# Case Analytics Skill — Fleet-level DataPrime queries over cases

## Pair with the `coralogix-dataprime` skill

This skill covers two things and only two things: (1) the schema of `system/labs.cases.state_updates`, and (2) the case-counting conventions (1h minimum window, dedupe per `caseId`).
Use the schema in this skill to know **what fields exist and what they mean**, and use `coralogix-dataprime` to know **how to shape the query around them**.

## Dataset: `system/labs.cases.state_updates`

See [the dataset schema and field reference](references/schema.md) before writing a query.

## Hard rules (ALWAYS apply)

These three rules are non-negotiable for every query you write against `system/labs.cases.state_updates`. They exist because the dataset emits a heartbeat for active cases, so the **same caseId appears many times** within any window. Counting raw events double-counts cases.

### Rule 1 — Always provide a time range, minimum 1 hour

Every query MUST be executed with an explicit time range via **`start_date`** and **`end_date`** on `query_dataprime` (or resolved with `get_datetime`). **Never query the dataset without a time range.** There is no "ever" / "all of time" semantics here: the dataset has a TTL, the scan is unbounded if you omit the window, and the result will silently reflect whatever the engine happened to load — misleading at best, wrong at worst.

The minimum window is `1h`. If the user asks for a shorter window, expand it to `1h` and tell them that the dataset is built for minimum 1h time ranges. If the user asks an open-ended "ever" / "in total" question, pick a sensible default window (`last 7d` is the default starting point for most case-state questions — active listings, current counts, recent resolutions; `last 30d` for resolution-style questions when more history is needed) and tell the user the window you assumed so they can override.

### Rule 2 — Always collapse to one row per `caseId`

Before counting, listing, or aggregating, you MUST reduce the stream to one row per case so each case is counted at most once. Use one of these two equivalent patterns:

**Pattern A — `groupby` keeping the latest event per case:**

```dataprime
| groupby caseId aggregate
    max_by($m.timestamp, $d) as latest
```

After this, the latest event payload is in `latest` (e.g. `latest.status`, `latest.priority`, `latest.createdAt`). Use this when you need the *latest known state* and want to read several fields off it.

**Pattern B — `dedupeby` keeping the most recent row:**

```dataprime
| dedupeby caseId orderby $m.timestamp desc
```

After this, the full row stays at top level (`status`, `priority`, `createdAt`, …). Use this when downstream commands read top-level fields directly.

The two patterns are interchangeable; pick whichever keeps the rest of the pipeline shortest.

### Rule 3 — When asking about a one-time lifecycle event, filter on `metadata.trigger`

Most questions about a single lifecycle moment (activation, resolution, closure, …) read better as a trigger filter than as dedup-then-filter. The trigger filter naturally excludes heartbeats *and* keeps the query simple:

```dataprime
| filter metadata.trigger == 'caseResolved'
```

This works because most lifecycle triggers fire **once per case** in the normal flow. Pick the right pattern from the table below.

| Trigger | Cardinality | Query |
|---|---|---|
| `caseCreated`, `caseActivated`, `caseResolved`, `caseClosed`, `caseArchived` | At most once | Filter alone is sufficient. |
| `caseAcknowledged` | **Can repeat** (re-acknowledge) | Filter fine for most; add `\| distinct caseId` to count cases, not events. |
| `caseAssigned` | **Can repeat** (reassignments) | Same — add `\| distinct caseId` to count cases, not events. |
| Heartbeat | Periodic | **Never** use as a lifecycle event; filter out or use Rule 2 dedup. |

**When in doubt, ask:** am I counting **events of a kind** or **cases in a state**? Events of a kind → Rule 3 (trigger filter). Cases in a state → Rule 2 (dedup to latest row).

### Dedup comes first

**Always dedup before you do anything else** (bucket, explode, aggregate). Because heartbeats repeat the full event payload — including nested arrays like `kpiBreaches.breachedKpis` and `indicators.alerts` — any operation on raw events inflates row counts by the number of heartbeats per case. This causes double-counting and can OOM on large windows.

The only exception is a trigger-filtered query (Rule 3), where `filter metadata.trigger == '...'` already excludes heartbeats.

Do not be clever or try to do it in one pass: the first command after `source` is the per-case dedup keyed on `caseId` alone, then add buckets, explodes, filters, and a separate final `groupby`.

- Don't fold a bucket into the dedup key: `| groupby day, caseId aggregate ...`. Dedup on `caseId` alone first, then bucket off `latest`/`last_seen`.
- Don't rely on `caseId` inside an aggregate without dedup: `| groupby kpiType, breachStatus aggregate distinct_count(caseId)` still scans heartbeats; dedup first.

## Query examples

### Time to activate

How long, on average, between case creation and activation (default window `last 7d` — adjust to the user's intent):

```dataprime
source system/labs.cases.state_updates
  | filter metadata.trigger == 'caseActivated'
  | create activation_lag from (activatedAt:timestamp - createdAt:timestamp).toTimeUnit('s')
  | aggregate avg(activation_lag) as avg_lag,
              percentile(0.5, activation_lag) as median_lag,
              max(activation_lag) as max_lag,
              count() as total_count
```

> `caseActivated` is emitted once per case, so no per-case dedup is needed here. If the user asks "ever" or "in total", expand the window deliberately (`last 30d`, `last 90d`) and tell them the window you picked — never omit it.

### Verifying resolutions

Number of distinct cases resolved in the last 30 days (counts each case at most once via `distinct`; pick an explicit window — never query "ever"):

```dataprime
source system/labs.cases.state_updates
  | filter metadata.trigger == 'caseResolved'
  | distinct caseId
  | count
```

Number of cases **currently** in `RESOLVED` (dedup by latest event per case):

```dataprime
source system/labs.cases.state_updates
  | groupby caseId aggregate
      max_by($m.timestamp, status) as currentStatus
  | filter currentStatus == 'RESOLVED'
  | count
```

### Case listing — last known state for every case

Default window `last 7d`, If the user is asking about long-running cases that may have been quiet for longer than that, widen explicitly (`last 14d`, `last 30d`) and tell them the window you used:

```dataprime
source system/labs.cases.state_updates
  | dedupeby caseId keep 1 orderby $m.timestamp desc
```

### Time-to-X bucketed over time (MTTR / MTTA)

Mean / median / p95 of a lifecycle duration, bucketed over time. Same shape for MTTR (resolve) and MTTA (acknowledge) — swap the trigger and timestamps.

```dataprime
source system/labs.cases.state_updates
  | filter metadata.trigger == 'caseResolved'
  | create ttr from (resolvedAt:timestamp - createdAt:timestamp).toTimeUnit('m')
  | create time_bucket from roundTime(resolvedAt:timestamp, 1d)
  | groupby time_bucket aggregate
      avg(ttr) as mttr,
      percentile(0.5, ttr) as median_ttr,
      percentile(0.95, ttr) as p95_ttr,
      count() as total_count
  | orderby time_bucket asc
```

> For MTTA, swap `metadata.trigger == 'caseAcknowledged'` and use `acknowledgedAt` in place of `resolvedAt`. For weekly buckets use `resolvedAt:timestamp / 7d` instead of `roundTime(...)`.

### MTBI daily

Mean time **between** incidents (i.e. between case creations), bucketed by day:

```dataprime
source system/labs.cases.state_updates
  | filter metadata.trigger == 'caseCreated'
  | create time_bucket from createdAt:timestamp / 1d
  | groupby time_bucket aggregate
      (max(createdAt:timestamp) - min(createdAt:timestamp)).toTimeUnit('m') as span_minutes,
      count() as total_count
  | create mtbi_minutes from span_minutes / (total_count - 1)
  | orderby time_bucket asc
```

> **Why this is exact, not an approximation.** The sum of consecutive gaps between events is a telescoping series: `(t2-t1) + (t3-t2) + … + (tn-t(n-1)) = tn - t1 = max - min`. So `avg gap = (max - min) / (count - 1)` matches what you'd get from averaging every individual gap. Edge case: `count == 1` yields zero gaps; guard with `if(total_count > 1, …, null)` if needed.

### Currently active cases

Count of cases currently in `ACTIVE`. Default window `last 7d`, widen if the user wants to include long-quiet cases:

```dataprime
source system/labs.cases.state_updates
  | groupby caseId aggregate
      max_by($m.timestamp, status) as currentStatus
  | filter currentStatus == 'ACTIVE'
  | count
```

List of currently active cases (one row per case via Pattern A):

```dataprime
source system/labs.cases.state_updates
  | groupby caseId aggregate
      max_by($m.timestamp, $d) as latest
  | filter latest.status == 'ACTIVE'
  | choose
      latest.caseId as caseId,
      latest.title as title,
      latest.priority as priority,
      latest.assignee as assignee,
      latest.createdAt as createdAt,
      latest.activatedAt as activatedAt
  | orderby createdAt desc
  | limit 1000
```

### Week-over-week comparison

Compare case or alert volume between two periods. Dedup per `caseId` across the full window first, then assign the period bucket from `last_seen` (see Rule 2).

```dataprime
source system/labs.cases.state_updates
  | groupby caseId aggregate
      max_by($m.timestamp, $d) as latest,
      max($m.timestamp) as last_seen
  | create period from if(last_seen >= now() - 7d, 'this_week', 'last_week')
  | explode latest.indicators.alerts into alert original preserve
  | filter alert.state == 'TRIGGERED'
  | groupby period aggregate distinct_count(caseId) as triggering_cases
```

Notes:
- `max($m.timestamp) as last_seen` captures when the case was last seen in the window; this drives period assignment.
- For open-case counts instead of triggered alerts, replace the `explode` + `filter alert.state` lines with `| filter latest.status == 'ACTIVE' | groupby period aggregate count() as active_cases`.
- Adjust the split offset (`7d`) to match the user's intent — e.g. `30d` for month-over-month.

### MTTR / MTTA / MTBI per team

Per-team KPIs, dedup-then-explode pattern. The `labels['routing.team']` label drives team attribution; missing values bucket as `unassigned`. Default window `last 14d` — adjust to the user's intent:

```dataprime
source system/labs.cases.state_updates
  | dedupeby caseId orderby $m.timestamp desc
  | explode labels['routing.team'] into team original preserve
  | create team from if(team != null, team, 'unassigned')
  | create tta from (acknowledgedAt:timestamp - createdAt:timestamp).toTimeUnit('m')
  | create ttr from if(status == 'RESOLVED' || status == 'CLOSED',
      (resolvedAt:timestamp - createdAt:timestamp).toTimeUnit('m'),
      null)
  | create ts from createdAt:timestamp
  | groupby team aggregate
      avg(tta) as mtta,
      avg(ttr) as mttr,
      (max(ts) - min(ts)).toTimeUnit('m') as span_minutes,
      count() as total_count,
      count(if(status == 'RESOLVED' || status == 'CLOSED', 1, null)) as resolved_count,
      count(if(acknowledgedAt != null, 1, null)) as acknowledged_count
  | create mtbi from if(total_count > 1, span_minutes / (total_count - 1), null)
  | orderby mttr desc
```

### Alert discovery

List of alert definitions that opened cases recently. Explode the alerts array first, then dedup on the alert definition id:

```dataprime
source system/labs.cases.state_updates
  | dedupeby caseId orderby $m.timestamp desc
  | explode indicators.alerts into alert
  | choose alert.alertDefinitionId as id, alert.title as title
  | dedupeby id
```

### Filtering / aggregating by permutations

#### 1. Discover permutation keys and their values

```dataprime
source system/labs.cases.state_updates
| dedupeby $d.caseId orderby $m.timestamp desc
| explode permutations into perm original preserve
| explode perm into kv original preserve
| filter kv.key != null
| create k from kv.key
| create v from kv.value
| groupby k, v aggregate count() as pair_count
| groupby k aggregate collect(v) as values, count() as distinct_value_count
| orderby distinct_value_count desc
```

Then filter cases by the matching key/value using the patterns below. Some keys (e.g. geo/city) have hundreds of values — add `| filter k ~ '<key-substr>'` before the final `groupby` to scope discovery to one dimension.

#### 2. Filter by a single key/value pair

```dataprime
source system/labs.cases.state_updates
| dedupeby $d.caseId orderby $m.timestamp desc
| explode permutations into perm original preserve
| explode perm into kv original preserve
| filter kv.key ~ 'subsystemName' && kv.value == 'incident-helper'
| dedupeby $d.caseId
```

#### 3. Filter by multiple key/value pairs that must co-occur in the same permutation

Dataprime can't express "N conditions in the same exploded group" in one pass. Workaround: group on `permutationIndex` and use `count_if` per condition.

**Recommended — `inArray` subquery** (keeps full `$d` access on the outer query; no per-field `any_value` re-export needed; avoids OOM from re-exporting the whole `$d`):

```dataprime
source system/labs.cases.state_updates
| filter $d.caseId.inArray((|
  source system/labs.cases.state_updates
  | dedupeby $d.caseId orderby $m.timestamp desc
  | explode permutations into perm original preserve
  | explode perm into kv original preserve
  | groupby $d.caseId, kv.permutationIndex aggregate
    count_if(kv.key ~ 'applicationName' && kv.value == 'cx10') as application_name_hit,
    count_if(kv.key ~ 'subsystemName' && kv.value == 'incident-helper') as subsystem_name_hit
  | filter application_name_hit > 0 && subsystem_name_hit > 0
  | distinct $d.caseId
|))
| dedupeby $d.caseId
```

**Fallback — `groupby` + `any_value`** (use when you need only a few specific fields in the output; re-export each field you need via `any_value(...)`; do not re-export the whole `$d` — that OOMs):

```dataprime
source system/labs.cases.state_updates
| dedupeby $d.caseId orderby $m.timestamp desc
| explode permutations into perm original preserve
| explode perm into kv original preserve
| groupby $d.caseId, kv.permutationIndex aggregate
    count_if(kv.key ~ 'applicationName' && kv.value == 'cx10') as application_name_hit,
    count_if(kv.key ~ 'subsystemName' && kv.value == 'incident-helper') as subsystem_name_hit,
    any_value($d.caseId)     as case_id,
    any_value($d.caseNumber) as case_number,
    any_value($d.title)      as title,
    any_value($d.status)     as status,
    any_value($d.caseUrl)    as case_url,
    any_value($m.timestamp)  as timestamp
    // any_value(...) needed for every field you want to re-export/show
| filter application_name_hit > 0 && subsystem_name_hit > 0
| dedupeby case_id
```

## Best Practices
- See the query examples for default queries to base off for user questions.
- When building a query, **ALWAYS** follow the **Hard Rules**
  1. Time window ≥ `1h`.
  2. Dedup per `caseId` (Pattern A or Pattern B) before any `count` / `aggregate` that's meant to be "cases", not "events".
- Query planning:
  1. Source the dataset: `source system/labs.cases.state_updates` with a time
  2. Filter to the events you care about (e.g. `filter metadata.trigger == 'caseResolved'` for resolution analytics, or no trigger filter when you want the latest state of every case).
  3. Dedup per `caseId` if you're answering a "cases" question (Pattern A or B).
  4. Explode any array you need to fan out over (`indicators.alerts`, `kpiBreaches.breachedKpis`, `labels['routing.<key>']`, `impactedEntities`, or double-explode `permutations` → `perm` → `kv`).
  5. Aggregate / project / order / limit.
- A user's term (a service, country, application, etc.) may be a permutation key or value. When a user asks about such a term, *always* first check if it's a group by key or value using the "Discover permutation keys and their values" example.
- Hard rules: Dedup always precedes bucketing, period assignment, and derived field creation. Any `create`, `groupby`, or `explode` on raw events before dedup operates on heartbeat-inflated rows and produces wrong results. For example, in a week-over-week comparison: dedup across the full window first and derive `last_seen` from the dedup step, then assign the period bucket from `last_seen` — never use `create period from if($m.timestamp ...)` on raw events, and never use `$m.timestamp` directly for period assignment.

## MCP tools

Load **`coralogix-dataprime`** alongside this skill for DataPrime syntax.

### `query_dataprime`

Run every query in this skill against `source system/labs.cases.state_updates`.

- **`query`**: full DataPrime query (must start with `source system/labs.cases.state_updates`)
- **`start_date`** / **`end_date`**: ISO 8601 UTC range — **minimum 1 hour** (see Rule 1)
- **`limit`**: max rows to return

Use **`get_datetime`** to resolve natural-language windows (e.g. "last 7 days") into `start_date` / `end_date`.

Violations of the hard rules above are appended to **`dataprime_warnings`** in the tool response.

### Single-case investigation

For one specific case by ID (e.g. CASE-123), use **alert tools** — not this skill. Do not page through case listings when the user named a single case.
