---
name: bronto-dataset-discovery
title: Bronto Dataset Discovery
description: Load this skill when investigating an incident or answering a question that needs logs from Bronto and the dataset that holds them is not already known - for example a service, host, function or resource that is failing, slow or throwing errors. It finds which Bronto datasets hold that service's logs, which key identifies the service, and whether there is data in the incident window, before any log search runs.
metadata:
  author: GaryNicholls
  version: "1.0.0"
  summary: Find the Bronto datasets, filter keys and data coverage for an affected service before searching its logs.
  tier: partner-managed
  aws-devops-agent-skills.agent-types: "CHAT, INCIDENT_TRIAGE, INCIDENT_RCA"
  aws-devops-agent-skills.technical-domains: "Observability"
---

# Find the Bronto datasets for an investigation

Use the tools on the connected Bronto MCP server to work out where the affected service's logs live before you search them. A Bronto organization can hold hundreds of datasets with different schemas. A search across all of them returns events from unrelated services, and a field filter that is valid in one dataset silently matches nothing in another, so an empty result can look like evidence when it isn't.

All steps are read-only. Do not create monitors or saved searches as part of this skill.

## 1. Collect identifiers and the time window

From the incident or question, note:

- The service, application or function name, and any likely variants (hyphens or underscores, with or without an environment suffix such as `-prod`).
- The environment (production, staging) and region.
- Hostnames, instance IDs, container or task names, cluster or namespace.
- Request IDs, trace IDs or error strings quoted in the incident.
- The incident window as start and end times in Unix epoch milliseconds. Widen it by 15 minutes on each side.

## 2. Find candidate datasets

Datasets are grouped into collections and carry tags such as `service`, `environment` and `region`. Always pass a selector to `get_datasets`. Without one it returns every dataset in the organization, which can be hundreds of entries. For the same reason, do not call `get_all_datasets_keys`.

Try these in order and stop once you have candidates:

1. **By tag:** `get_datasets` with `from_expr` set to `"service" = '<service>'`. Add `AND "environment" = '<environment>'` when you know the environment.
2. **By name:** `get_datasets` with `from_expr` set to `"dataset" LIKE '%<name>%' OR "collection" LIKE '%<name>%'`. Repeat with each name variant.
3. **By errors in the window:** `get_error_summary` with `from_ts` and `to_ts` set to the window. Its `by_dataset` list names only the datasets that logged errors or warnings, and it does not use search quota.

`get_datasets_by_name` matches the dataset and collection names exactly, so use it only when you already know both.

Set `minimal_output` to true. Pass `minimal_output: false` with `from` set to the candidate `log_id` values when you need a dataset's tags.

## 3. Rank the candidates

- Prefer datasets whose `environment` tag or collection name matches the incident's environment.
- Use `last_heartbeat_at` only to set aside datasets that have been dormant for a long time. It is recorded about once a day, so a dataset that is ingesting normally can show a heartbeat up to 48 hours old. Set a dataset aside only when its `last_heartbeat_at` is more than 2 days before the window start. `active` is false when the heartbeat is more than 14 days old or missing. A missing heartbeat means unknown, not dormant, so keep such a dataset if it is the best match.
- Never conclude that a service stopped logging from `last_heartbeat_at` or `active`. Use the event counts in step 5.
- Collections whose names start with a dot, such as `.metrics` and `.traces`, hold metrics and traces rather than log events. Include them only when the question is about metrics or traces.
- Sibling datasets with suffixes such as `_gc` or `_systemd` hold host and runtime logs. Rank them below the application dataset, but keep them for crashes, restarts and out-of-memory events.

Keep the full ranked list for the report. Only the next step is limited, because `get_keys` responses can list hundreds of keys.

## 4. Confirm the filter key

For each of the top candidates:

1. Call `get_keys` with its `log_id`. Look for keys that identify the service or host, such as `service`, `$service`, `service.name`, `host`, `hostname` or Kubernetes and container keys.
2. Call `get_key_values` for the most likely key to confirm the service appears as a value. The values come from the most frequent keys only, so a missing value is not proof of absence.

Copy key names exactly as `get_keys` returns them. Do not list every value of a key that holds IDs, timestamps or other high-cardinality data.

## 5. Check there is data in the window

For each of the top three candidates, call `timeseries` with `metric_functions: ["COUNT(*)"]`, that dataset's `log_id` in `log_ids`, the window as `timerange_start` and `timerange_end`, the service filter from step 4 as `search_filter`, and `num_of_slices: 6`. Leave `minimal_output` false, because the minimal response leaves out the per-bucket counts. The buckets show whether the service logged before, during and after the incident. A gap that starts at the incident is itself evidence. Make a separate call per dataset, because the filter key can differ between datasets and a combined call adds the counts together.

If a filtered count is zero, check the key spelling with `get_keys` before you report that there are no logs.

## 6. Report the dataset map

Before any log search, report one line per dataset you will use:

- Dataset name, collection and `log_id`.
- Why it matched: tag, name, key value or error summary.
- The filter key and value to use, in `search_filter` syntax, such as `"service.name"='checkout-api'`.
- Whether it has data in the window, and when it last ingested.
- Your confidence: high, medium or low.
- The `webapp_url` from the `timeseries` response, so a person can open the same search in Bronto.

Then give the first query to run: a `get_error_summary` for the window, or a `search_logs` or `timeseries` call scoped to the chosen `log_ids` with the filter above and a small `limit`.

If no dataset matches after every step in section 2, say that the service's logs were not found in Bronto and list the names and tags you tried. Do not search every dataset instead, and do not guess. Bronto only returns datasets the connected user or API key can see, so a missing dataset can also mean missing permissions; say so.

## Limits

- Make at most 15 Bronto tool calls in this skill before reporting.
- Never put event fields in `from_expr`. It selects datasets by collection, dataset name and tags only; event filters belong in `search_filter`.
