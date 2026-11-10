# Aggregations in depth (`search-aggregations`)

Load this file when you need counts, trends, top-N, ratios or comparisons across logs, traces, errors, sessions or metrics, or before building a graph. For OpenTelemetry metric names, types and units (counters, gauges, histograms), load the `observability/metrics` guide with `load-skill`.

## Core arguments

- `productType` (required): `traces`, `logs`, `errors`, `sessions`, `metrics`, `paevents` or `events`.
- `startDate` (required) and `endDate`: ISO 8601 with a timezone. `compareTo` needs absolute dates.
- `query`: the shared filter grammar; `services` and `environments` restrict to exact values.
- Aggregation: `functionType` with `column`, or `expressions` for several at once. `Count` needs no column; trace `duration` is in nanoseconds; for metrics the column is `value`.
- `bucketCount`: defaults to 10 (a time series). Set `1` for one total per group, the number of hours or days for hourly or daily counts.
- `groupBy`: one key or an array for a composite group; `groupByLimit` up to 100 (default 5); `rankBy` picks the top groups (rank by `Count` when you report a percentile); `minCount` skips tiny groups.

## Compare against a baseline (`compareTo`)

`compareTo: "1d"` (or `"1h"`, `"1w"`) reruns the same query over the window shifted back and returns the earlier values next to each series (`previous_values`) or row (`previous`), with `comparison_window`. Use it for:

- "Is this new?" One total now vs the same window yesterday or last week.
- "Which group changed?" With `groupBy`, each group's value now vs before. A group missing from the earlier top groups has no previous value; raise `groupByLimit` if that hides one.
- Prefer `1d` or `1w` over the previous hour when traffic has a daily shape.

## Break down to find the cause

One call per candidate dimension, `bucketCount: 1`, `groupByLimit` 10 to 20, over the anomaly window, with `compareTo`:

| Dimension | Key to try (confirm with `get-keys`) |
|---|---|
| Host or pod | `host.name`, `k8s.pod.name` |
| Version | the key `get-changes` detected: `service_version`, `tags.version` or `version` |
| Endpoint | `http.route` with `span_kind=Server` |
| Environment or region | `environment`, `cloud.region` |
| Flag variation | `feature_flag.result.value` with `feature_flag.key=<flag>` |

Run each for the failures and for all traffic, and compare shares. A composite `groupBy: ["<versionKey>", "host.name"]` separates "bad version" from "bad host".

## Ratios (`series` and `formulas`)

Up to five `series` (each with an `id` a to e, its own `query` and an aggregator) share the window, `groupBy` and buckets; `formulas` combine them, for example `100 * b / a` for an error percentage. Leave `query`, `functionType`, `column` and `expressions` unset when you use `series`. Each series ranks its own top groups, so a group outside one series' top groups gives a null formula value. `exact` and `populationFunctionType` cannot be combined with `series`.

## Other options

- `rate`: `per_second`, `per_minute` or `per_hour` for `Count` or `Sum`; not with `formulas`.
- `includeOther`: adds an "Other" series so groups add up to the total; `Count`, `Sum`, `Min` and `Max` only.
- `populationFunctionType`: aggregate per group, then across groups (the Max across pods of each pod's Avg).
- First and last seen per group: `expressions` `Min` and `Max` of `timestamp`, `bucketCount: 1`; values are Unix seconds.

## Sampling

Traces and logs are sampled unless `exact` is set. When the result has `estimated: true`, counts are scaled estimates and percentiles come from the rows actually read. Set `exact: true` for short windows, rare events, distinct counts, and any number you quote.

A sampled result with a percentile carries a `low_sample` block when some buckets rest on too few rows: a `warning`, and per expression the `buckets`, `min_sampled_rows` and `threshold` (P99 under 200 rows, P95 under 50, other percentiles under 20); each percentile bucket also gets `sampled_rows`. Treat a flagged percentile as noise: rerun with `exact: true` or fewer, wider buckets. `exact` is not switched on for you. Servers without `low_sample` apply no check, so add a `Count` expression and apply the same thresholds yourself.

## Is the data complete? (`includeIngest`)

`includeIngest: true` adds an `ingest` block: `sampling_rate`, `minute_rate_limit`, `exclusion_query`, `filter_rules`, `quota` (shown near or over the limit) and, when the server can check it, a one-line `completeness_note` naming sampling, rate limiting, dropping filter rules, an exclusion query or an exceeded quota. `get-keys` adds the same block by itself when a non-default setting applies. Check it before you report that data is missing or that a count dropped.

## Keep responses small

Prefer 10 to 50 buckets, a single total (`bucketCount: 1`) when you only need a ranking, and `groupByLimit` no larger than you will read. `maxTokens` caps the response; rows past it are dropped and `truncation_note` says how to get them.

## Common mistakes

- Running two windows by hand instead of using `compareTo`.
- Ranking groups by a percentile, so a group with three slow requests tops the list. Rank by `Count`.
- Guessing a key. A wrong `groupBy` key returns one empty group; a wrong filter key widens the result silently.
- Reading `Max` of a cumulative counter as a level. Load the `observability/metrics` guide with `load-skill` for counters.
- Ignoring a `low_sample` warning and reporting a percentile swing as a regression.
