---
name: bronto-log-search
title: Bronto Log Search
description: Load this skill before writing or running a Bronto log search - counting, grouping, trending or fetching log events with the Bronto MCP tools. It explains which tool answers which question, how to write a search_filter in Bronto's search syntax, and how to read the results without misreporting zero matches.
metadata:
  author: GaryNicholls
  version: "1.0.0"
  summary: Write Bronto search filters and choose between error summaries, aggregates and raw events when searching logs.
  tier: partner-managed
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Run a Bronto log search

Bronto stores logs in datasets, each identified by a `log_id`. Every search runs over a list of `log_ids` and a time window, with an optional `search_filter`. If you don't yet know which datasets hold the logs you need, use the `bronto-dataset-discovery` skill first.

## 1. Pick the tool

Work from summaries to raw events, and only fetch events once you know what to look for.

| Question | Tool |
| --- | --- |
| Where are the errors in this window? | `get_error_summary` - per-dataset error and warning totals; does not use search quota |
| How many, how often, which values, how slow? | `timeseries` - counts and aggregates, optionally grouped and bucketed over time |
| What do the events say? | `search_logs` - raw events, with a small `limit` and only the columns you need |
| Is there a saved search for this already? | `get_saved_searches`, then `run_saved_search` |

A saved search runs over the window it was saved with unless you override it. Pass the incident window to `run_saved_search` as `from_ts` and `to_ts`, or as `time_range`, and set `limit`.

`search_logs` returns events only. It rejects `groups` with aggregate `select` columns; use `timeseries` with `group_by_keys` for any grouped count or aggregate.

## 2. Set the time window

- During an investigation, pass the window as `timerange_start` and `timerange_end` in Unix epoch milliseconds, so every call covers exactly the same period.
- For a quick look, `time_range` accepts relative windows such as `Last 15 minutes`, `Last 1 hour` or `Last 24 hours`.
- Start narrow, around the incident, and widen only if the first results are empty or the cause began earlier.

## 3. Write the search_filter

`search_filter` is the `WHERE` clause of a query: a predicate only. Never put `GROUP BY`, `ORDER BY`, `HAVING` or aggregate functions in it.

**Check field names first.** Call `get_keys` for each dataset you search and copy key names exactly. Schemas differ between datasets, so a key that exists in one dataset silently matches nothing in another. Dataset names, collections and tags are not fields.

**Quoting:**

- String values take single quotes: `log_level = 'ERROR'`. An unquoted word on either side of an operator is read as a field name, so `status = error` compares two fields.
- Numbers and booleans are bare: `status >= 500`, `authenticated = false`. Quoting a number makes it a string comparison.
- Field names that contain any of `= ! ? . , < > - + * / % ^ & |` take double quotes: `"exception.type" IS NOT NULL`, `"request-time" = '500ms'`.
- Escape a quote by doubling it: `'O''Brien'`.

**Free text:** a bare word or quoted string on its own, such as `timeout` or `'connection refused'`, matches anywhere in the raw event, ignoring case. It is shorthand for `@raw ILIKE '%timeout%'`. Use free text first for opaque identifiers such as request IDs and trace IDs. Free text does not search resource attributes whose names start with `$`, such as `$service` or `$hostname`; filter on those by name: `"$service" = 'checkout-api'`.

**Common operators:**

| Need | Example |
| --- | --- |
| Exact value | `log_level = 'ERROR'` |
| One of several values | `status IN (500, 502, 503)` |
| Exclude values | `log_level NOT IN ('DEBUG', 'TRACE')` |
| Field present or missing | `"exception.type" IS NOT NULL` |
| Substring, case-insensitive | `message ILIKE '%timed out%'` |
| Numeric range | `duration_ms >= 1000 AND duration_ms < 5000` |
| Combine | `log_level = 'ERROR' AND (timeout OR 'connection refused')` |

`AND` binds before `OR`; use parentheses. For the full operator list, data type rules and regular expressions, see [references/search-syntax.md](references/search-syntax.md).

## 4. Aggregate with timeseries

- `metric_functions` is required. Use `COUNT(*)` for event counts, and `SUM`, `AVG`, `MIN`, `MAX`, `P50`, `P75`, `P90`, `P95` or `P99` on numeric fields only, for example `P95(duration_ms)`.
- `group_by_keys` groups the result, for example `["path"]` or `["log_level"]`. Set `limit` to the number of groups you need; the response marks `truncated: true` when more groups exist.
- `num_of_slices` sets the number of time buckets. Use it to see when something started or stopped.
- Leave `minimal_output` false when you need per-bucket values or any aggregate other than the count. The minimal response keeps only total counts.
- In each group, `count` is the number of matching events and `value` is the aggregate. Report `value` for sums, averages and percentiles.

To see which kinds of message dominate, group by `$pattern_id`. Bronto assigns a pattern ID to each event as it is ingested, based on the structure of the message, so this groups events like `Connection to db-1 failed` and `Connection to db-2 failed` together. An empty pattern ID means the event matched no pattern.

## 5. Fetch events with search_logs

- Set a small `limit`, such as 10. The API returns 100 events by default, each with every field and `@raw` unless you set `select`.
- Set `most_recent_first: true` to see the latest events; without it, results come oldest first. To find the first occurrence, leave it false, or use a bucketed `timeseries` instead.
- Use `select` to return only the columns you need, such as `["log_level", "message", "exception.type"]`. Without it, each event comes back in full and a few dozen events can fill the context.
- `order_by` sorts, for example `duration_ms DESC` to find the slowest requests.
- `group_by_patterns: true` collapses repeated events into pattern templates with counts, but events that match no pattern still come back in full. Combine it with a narrow filter and a small `limit`. To see the events behind one pattern, search again with `"$pattern_id" = '<pattern_id>'`.
- To page through more results, pass the `pagination_token` from the response's `links`. Stop paging once you have the events you need, and after three pages narrow the filter or use `timeseries` instead.

## 6. Read the results carefully

- **Zero matches is not proof of absence.** Before you report that something didn't happen, check the field name with `get_keys`, check the value's quoting and case, and check the time window and `log_ids`.
- **Compare with a baseline.** A count during the incident means little alone. Run the same `timeseries` for an earlier period, or use more time buckets to see the change.
- **Each response includes a `webapp_url`.** Include it in your findings so a person can open the same search in Bronto.
- **Quote evidence exactly.** When a log line supports a conclusion, quote it with its timestamp and dataset.

## Limits

- Make at most 20 Bronto tool calls in this skill before reporting what you found.
- A query is at most 16,000 characters and 400 expressions.
- All steps are read-only. Do not create monitors or saved searches as part of this skill.
