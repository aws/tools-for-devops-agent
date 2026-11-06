---
name: launchdarkly-alert-investigation
description: "Investigates a firing or recently fired observability alert: finds the firing and replays the value it evaluated, decides whether the alert is chronic noise or a new problem, reuses any automatic investigation, then finds the cause (what changed, which host, version or route is over-represented) and returns a structured diagnosis with cause, scope and next steps."
license: Apache-2.0
compatibility: Requires the remotely hosted LaunchDarkly MCP server
metadata:
  author: "nieblara"
  version: "1.0.0"
  summary: "Diagnose a triggered LaunchDarkly observability alert: likely cause, scope and next steps."
  tier: "partner-managed"
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA"
---

# Alert investigation

You are explaining why an alert fired, whether it matters, and what to do. Half of the alerts you are asked about will turn out to be chronic or misconfigured; "this alert is noise, here is why, here is the retune" is a correct and useful answer. Do not invent a root cause for an alert that has fired every day for a week.

## Prerequisites

This skill requires the remotely hosted LaunchDarkly MCP server. Tools it uses:

- `get-alerts`: what is firing, and one alert's full configuration
- `get-alert-firing-history`: when it fired, per group, with `replay` arguments for each firing
- `get-investigation`: the automatic investigation that ran for a firing, if any
- `search-aggregations`: replay the alert's value, compare against a baseline, break it down
- `get-changes`: deploys, flag changes and alert state changes around the onset
- `get-trace`, `search-traces`, `search-logs`, `search-log-patterns`, `search-error-groups`, `get-error-group`, `search-sessions`: evidence
- `search-service-map`, `get-keys`, `get-incidents`

The investigation itself follows the "first five minutes" in [launchdarkly-investigate](../launchdarkly-investigate/SKILL.md). This skill covers the alert-specific steps around it.

## Workflow

### 1. Find the alert and the firing

- If you have an alert ID (from the user, a notification link or the conversation), call `get-alerts` with `alertId` for its query, product type, function, grouping, threshold and window.
- If the user asks what is firing, call `get-alerts` with `state: "Alert"`. One call lists every alert whose most urgent group is in Alert now. Use `search` to match an alert by name.
- Then call `get-alert-firing-history` with the `alertId` and `lookbackDays: 7`. It returns:
  - `evaluation`: the query, function, grouping and thresholds it uses now
  - `firing_count` and `last_fired_at`
  - `firings`: newest first, each with its `group`, state change, `investigation_conversation_id` and `replay`
  - `current_state`: the latest state per group, which tells an alert firing now from one that has resolved
  - `summary`: the episode view, read from up to 500 firings (`firings_counted`, `complete`). See step 3.

Name the group that fired (for example `task.type=5`), not just the alert. `current_state` leaves out groups that have been Normal and unchanged for 14 days (`idle_groups_omitted`; set `includeIdleGroups: true` to see them). On an older server those groups are listed; ignore entries that have not changed for weeks.

### 2. Replay the value

Each firing's `replay` is a ready set of `search-aggregations` arguments that recompute the value the alert compared with its threshold. Pass it as is. Then make two changes, one at a time:

- Add `compareTo: "1w"` (or `"1d"`): is the value now different from the same window last week?
- Add a `Count` expression next to the alert's function so you know how many rows the value rests on, and set `exact: true` if the result says `estimated: true` and the window is a few hours or less.

If `config_changed_since` is true on a firing, the alert was edited after it fired and the replay uses today's config; say so when you quote the value.

A current state of `NoData` means the alert's query matches nothing: the service was renamed or stopped emitting. That is the finding.

### 3. Chronic, noisy, or new?

Decide this before you look for a cause. Start from the firing history's `summary`:

- `chronic` and `chronic_reason`: `chronic: true` means it fired on more than 4 of the last 7 days.
- `episodes` (`start`, `end`, `firings`, `span_minutes`, `group_by_key`, `investigation_conversation_id`) and `episode_count`: firings close together are merged (`episode_gap_minutes`). One long episode is one problem; ten short ones a day is flapping.
- `flaps`, `firings_per_day` (last 7 days), `days_fired` (whole lookback) and `groups` (firings, first and last per group).
- `value_source`: the value at each firing is not stored; it says how to recompute it (pass that firing's `replay` to `search-aggregations`, step 2). `time_in_alert_note` explains why time in Alert is not given.

`get-changes` shows the same alert as `alert_episode` rows on the service's timeline, next to deploys and flag changes. On a server without `summary`, count firings per day from `firings` yourself.

Other signs of a **chronic or noisy** alert:

- Many firings in the lookback on the same group, flapping between Warn and Alert.
- The replayed value is close to the `compareTo` value from last week.
- The alert evaluates a high percentile over few rows. A P99 over about 600 spans per window is the sixth-slowest span; a handful of slow requests flips it. A `low_sample` block on the replay says so directly; see "Sampling and percentiles" in [launchdarkly-investigate](../launchdarkly-investigate/SKILL.md).
- The threshold sits inside the normal range of the series: run the replay over 3 to 7 days with `bucketCount` 24 to 48 and see how often it is crossed.

If it is chronic, say so, show the numbers, and still explain what the tail is made of (one `get-trace` of the slowest span usually does it). Recommend a concrete retune: a lower percentile (P95), a higher threshold, a minimum count, a longer window, or excluding the group.

If it is **new**, the onset is the `start` of the current episode; carry on.

### 4. Reuse the automatic investigation

If the firing has an `investigation_conversation_id`, call `get-investigation` with it. Cite its conclusion as its conclusion, and check the key claims against current data before you repeat them. If it says the investigation is not shared with you, do not retry.

### 5. Investigate the cause

Run steps 3 to 6 of the first five minutes in [launchdarkly-investigate](../launchdarkly-investigate/SKILL.md), scoped to the alert's query and the onset window:

- **What changed:** `get-changes` for the service the alert's query names, from 1 to 2 hours before the onset. Pass the alert's ID in `alertIds` to see its own `alert_episode` rows on the same timeline.
- **What is over-represented:** break the alert's own signal down by `host.name`, the version key, `http.route`, and the flag variation, each with `compareTo`. If the alert is grouped, compare the firing group with its sibling groups too.
- **Evidence:** traces, logs and error groups from the slice that stands out.
- **Blast radius:** `search-service-map` with `include: ["health"]` for the service.

Load the per-product companion for the alert's product type (below) for the evidence step.

## When to load which companion

- `logs.md`: log count or log pattern alerts
- `traces.md`: latency, span error-rate, and span-specific alerts
- `errors.md`: error-count, new-error-group, crash-rate alerts
- `sessions.md`: session-health and user-facing-error alerts
- `metrics.md`: OpenTelemetry metric thresholds and composite alerts

If the alert crosses products (a metric alert driven by errors), load both.

## Output template

Alert investigations feed notifications and on-call handoffs. Use this structure.

```
## What triggered

<Alert name and ID, the group that fired, the function and threshold, the replayed value and how many rows it rests on, and when it fired (UTC).>

## Verdict

<New problem, chronic condition, or noise, with the evidence: chronic_reason or firings in the last 7 days, episodes, value vs the same window last week.>

## Likely cause

<Root cause with the numbers: the slice that is over-represented (share of failures vs share of traffic), the change that preceded the onset, and trace IDs, error group IDs and log templates. Say what was ruled out.>

## Scope

<Affected requests, error rate, users or sessions, routes, downstream services, and the time window of impact.>

## Next steps

<1 to 3 concrete actions: roll back version X, turn flag Y off in production, drain host Z, retune the alert to P95 > 1 s with a minimum of 200 spans. If the cause is not established, name the exact query or data that would establish it.>
```

## Guidelines

- **Stay tight.** No preamble. The on-call should be able to act without re-querying.
- **Cite identifiers** for every claim: alert ID, group, trace ID, error group secure ID, log timestamp, host, version, flag key.
- **Noise is a legitimate outcome.** "Fired 133 times in 7 days on the same group; last week's value was higher; the tail is source-map parsing" is a complete answer with a retune recommendation.
- **Do not trust an alert's group alone.** A grouped alert names where the threshold was crossed, not why. The cause is often in a dimension the alert does not group by, such as one host.
- **Convert units.** Trace `duration` is in nanoseconds; quote thresholds and values in ms or s.

## Related skills

- [launchdarkly-investigate](../launchdarkly-investigate/SKILL.md): the full investigation sequence.
- `observability/alert-management` and `observability/create-alert` (guides served by the LaunchDarkly MCP server; read them with `load-skill`): retune, mute or rebuild the alert after the diagnosis.
