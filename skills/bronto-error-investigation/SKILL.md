---
name: bronto-error-investigation
title: Bronto Error Investigation
description: Load this skill when an investigation needs to explain errors in logs held in Bronto - an error surge, a failing service, a specific error event or a Bronto monitor alert. It isolates the error, finds when it started, breaks it down by version, host, customer, endpoint, client and region to find what it is concentrated on, verifies the suspect against a control query, and reports the scope, a hypothesis and next steps with links to the supporting searches.
metadata:
  author: GaryNicholls
  version: "1.0.0"
  summary: Find when an error started and what it is concentrated on - version, host, customer, endpoint or region - from Bronto logs.
  tier: partner-managed
  aws-devops-agent-skills.agent-types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Investigate an error with Bronto logs

Most error investigations end with the same question: what do the failing events have in common that the healthy ones don't? This skill answers it from the error's distribution rather than from reading log lines one by one. It defines the error precisely, finds when it started, splits it by the dimensions that usually explain errors, and confirms the strongest suspect with a control query.

This skill covers the investigation method. For Bronto's search syntax, quoting rules and which tool returns what, use the `bronto-log-search` skill. To find the datasets that hold a service's logs, use the `bronto-dataset-discovery` skill.

All steps are read-only. Do not create monitors or saved searches as part of this skill.

## 1. Start from what you were given

- **A Bronto monitor alert.** The incident description carries the monitor's `Query`, `Group`, `Value`, `Window` and a monitor link. Use `Query` as the starting error filter in step 2, and take the alert time as the end of the window. If `Group` names a value, such as one host or path, note it: it is already a suspect to check in step 5.
- **A specific error event** (a log line, a request ID or a timestamp). Find the event with `search_logs` using free text and a small `limit`, and note its dataset and timestamp.
- **A service and a symptom** ("checkout-api is throwing 500s"). Use `bronto-dataset-discovery` to find the datasets and the key that identifies the service.

If the datasets are still unknown, call `get_error_summary` for the window. Its `by_dataset` list names only the datasets with errors and warnings, and it does not use search quota.

Pass every time window as `timerange_start` and `timerange_end` in Unix epoch milliseconds, so that each query covers exactly the same period and the results can be compared.

## 2. Define the error filter

Every count in this investigation depends on the error filter matching this error and nothing else.

1. Call `get_keys` for each dataset. Find the level key, such as `log_level`, `level` or `severity`, and any status or exception keys. Copy names exactly.
2. Find which errors dominate: `timeseries` with `metric_functions: ["COUNT(*)"]`, the level filter (for example `log_level IN ('ERROR', 'FATAL')`), `group_by_keys: ["$pattern_id"]` and `limit: 10`.
3. Read the top patterns: `search_logs` with `"$pattern_id" = '<id>'`, `limit: 3` and `most_recent_first: true`. Quote one representative line with its timestamp and dataset.
4. Use `"$pattern_id" = '<id>'` as the error filter. A pattern ID matches one log statement exactly, which a filter on the message text often fails to do. When several top patterns are the same failure with different wording, combine them with `"$pattern_id" IN ('<id1>', '<id2>')`. When you start from a monitor's `Query`, keep it, but check that its top pattern is the error you are investigating.

If no pattern ID is set on the events, filter on the exception type or a distinctive phrase from the message, and confirm the filter by reading a few of the events it matches.

## 3. Find when it started

Call `timeseries` with the error filter, `COUNT(*)`, `num_of_slices: 20` and `minimal_output: false`, ending at the alert or event time.

1. Look back **3 hours** first. If the first bucket with errors is bucket 6 or later, the start is inside the window: stop.
2. Otherwise the error was already happening when the window began. Look back **3 days**, then **7 days**, with the same test.
3. If errors are present from the first bucket even over 7 days, the error is long-standing. Report that: the incident is a change in its rate, not a new error. Compare the incident's rate with the 7-day level instead of looking for a start.

The start is the first bucket where the count rises clearly above the buckets before it. Run the same `timeseries` with the level filter only, or with no filter, over the same window. This tells you whether this error grew on its own, or whether every error or all traffic grew with it. Total traffic rising with the errors points at load, not a fault.

The investigation window is from the start to the end of the incident. If the error has stopped, end the window a little after it stopped.

## 4. Choose the breakdown keys

From `get_keys`, pick the keys that identify, in this order:

1. **Version or deployment** - such as `version`, `service.version`, `deployment.version`, `git_sha` or an image tag
2. **Host, pod or instance** - such as `$hostname`, `host`, `k8s.pod.name` or `instance_id`
3. **Endpoint or operation** - such as `path`, `route`, `http.route` or `method`
4. **Customer, tenant or account**
5. **User**
6. **Client IP or source**
7. **Region, zone or location**
8. **Downstream dependency** - such as `peer.service`, `db.name` or an upstream host

[references/breakdown-keys.md](references/breakdown-keys.md) lists more key names per dimension.

Call `get_key_values` for each candidate and skip keys with only one value: a constant cannot explain anything. Skip keys that hold timestamps, request IDs, trace IDs or durations. Take at most 8 keys.

## 5. Break the error down

For each key, call `timeseries` with:

- the error filter as `search_filter`
- `metric_functions: ["COUNT(*)"]`
- `group_by_keys: ["<key>"]` and `limit: 10`
- `num_of_slices: 20` over the investigation window
- `minimal_output: false`

Make a separate call per key. Read each result for:

- **Concentration.** What share of the errors comes from the top value? A share of 80% or more on one value is a strong lead. Errors spread evenly across all values rule that dimension out, which is also worth reporting.
- **Onset.** A value whose errors begin in the start bucket from step 3 while the other values stay flat, such as a new version or a host that joined at that moment.
- **New values.** A value that appears only from the start bucket on, such as a version or route nobody used before.

A concentration means little until you compare it with how traffic is spread. For each key with a lead, run the same grouped `timeseries` **without** the error filter, or with the service filter only. Errors that are 90% on one host are a finding only if that host serves much less than 90% of the traffic. Report each lead as the value's share of errors against its share of all events.

## 6. Verify the lead

A breakdown shows a correlation. Confirm it with two `timeseries` calls over the same window with `num_of_slices: 20`:

- the error filter `AND "<key>" = '<value>'`
- the error filter `AND "<key>" != '<value>'`

If the first series carries the increase and the second stays at its earlier level, the lead explains the error. If both rise, the value is a symptom, and the cause is something they share. Go back to step 5 with the next lead.

When two leads overlap, such as a version deployed only to some hosts, verify the one that comes earlier in the order in step 4. Then check whether the other still matters once the first is filtered out.

## 7. Report

Report in this structure:

- **Primary issue** - one sentence, such as "Payment authorization timeouts on POST /v2/charge".
- **Scope** - the error count and when it started, and the concentration as shares of errors against shares of traffic, such as "96% of the errors come from version 4.12.0, which handles 30% of the requests". Name the dimensions you ruled out.
- **Evidence** - one representative log line, quoted with its timestamp and dataset, and the `webapp_url` of the start query (step 3), the strongest breakdown (step 5) and the verification (step 6), so a person can open each search in Bronto.
- **Hypothesis** - the most probable cause, and how strongly the verification supports it.
- **Next steps** - one or two concrete actions, such as rolling back the version, draining the host, or checking the dependency the errors name.

Give times in UTC, or in the incident's time zone if it states one. Refer to time buckets by their times, not their positions.

## Stay on the path

- "The message says what's wrong, so the breakdown is unnecessary." The message says what failed, not where or since when. The breakdown finds what the failing events share.
- "One value has most of the errors, so that's the cause." Compare it with its share of traffic, then verify it in step 6.
- "The first search returned nothing, so the error has stopped." Check the filter, the key spelling and the window first. See `bronto-log-search`.
- "I'll read a few hundred events and spot the pattern." Count and group with `timeseries`. Raw events are for quoting evidence, with a small `limit`.

## Limits

- Make at most 30 Bronto tool calls before reporting. If you reach the limit, report what you have and the leads you did not verify.
- Use `explain_only: true` to check the volume of a 3-day or 7-day query before running it across many datasets.
- Bronto only returns data the connected user or API key can see.
