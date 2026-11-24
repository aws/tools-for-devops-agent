# Query construction reference

Load this when building a non-trivial query — anything beyond a keyword filter with a
limit — or when a query returns no rows and you need to widen it.

## Shape

`source → filter → aggregate → format`

```
# Aggregate query (bounded output)
_sourceCategory=prod/api/* error
| where status_code >= 400
| count by service_name
| sort _count desc | limit 20

# Raw query (limit first, so scanning terminates early)
_sourceCategory=prod/api/* "TimeoutException" | limit 10
| json "service" as service_name nodrop
| json "endpoint" as endpoint nodrop
| fields _messagetime, service_name, endpoint, _raw
```

## Operators worth knowing about

Standard SQL-ish operators (`where`, `count by`, `sum`/`avg`/`min`/`max`, `if`, `matches`,
`sort`, `fields`) behave as expected. The Sumo-specific ones:

| Operator | Purpose | Note |
|----------|---------|------|
| `timeslice` | Time-bucket for trend analysis | `timeslice 5m` then `count by _timeslice, field` |
| `parse regex` | Extract fields from unstructured logs | Add `nodrop` if the pattern may not match |
| `json` | Parse JSON logs | Add `nodrop` — see Gotchas in SKILL.md |
| `outlier` | Flag anomalous values in a series | Needs a `timeslice`d aggregate upstream |
| `transaction` | Group related events into sessions | Expensive; scope tightly |
| `logreduce` | Cluster similar messages into patterns | Best first move on an unfamiliar noisy source |
| `pct` | Percentiles (`pct(latency_ms, 95)`) | Use instead of `avg` for latency |

## Worked example — "what errors are hitting the API gateway in the last hour?"

```
1. DISCOVER  listPartitions + listCustomFields + listExtractionRules (parallel)
             → partition routingExpression `_sourceCategory=prod/api/*` matches "API gateway"

2. SAMPLE    _sourceCategory=prod/api/gateway | limit 5
             (5-minute window) → reveals fields: level, error_type, endpoint, _collector=api-col-3

3. TARGET    _sourceCategory=prod/api/gateway AND _collector=api-col-3
             | where level = "ERROR"
             | count by error_type, endpoint
             | sort _count desc | limit 20
             (1-hour window)
```

Note what step 2 bought: the real field name is `level`, not `severity`; `error_type` exists
as an extracted field, so no `parse` is needed; and a single collector serves this category,
which narrows the step-3 scan.

## Picking a `_sourceCategory`

From `listPartitions`, each partition carries a `routingExpression` such as
`_sourceCategory=glass/*` or `_sourceCategory=stream`. Match the service in the user's
question against those expressions and use the winner directly.

Do **not** try candidate categories one at a time. If 2-3 look plausible, run a single
disambiguating query instead of N searches:

```
_sourceCategory=(cat1 OR cat2 OR cat3) <keyword> | count by _sourceCategory | sort _count desc
```

## Per-domain approach

| Goal | Approach |
|------|----------|
| Errors | Sample to learn the error shape → filter → `count by error_type, service` |
| Performance | Find the latency field in the sample → `timeslice` + `pct(field, 95)` → locate slow buckets |
| Trends | `timeslice` aggregate; split the range if it exceeds 2 days, then compare periods |
| Resource / capacity | Metrics questions go to Mobot, since this skill has no direct metrics tool; from logs, look for resource signals such as OOM, throttling or saturation messages |
| Alert triage | `alertsSearch` → `alertsReadById` → re-run the monitor's own query pattern against logs |
| Unfamiliar source | `logreduce` first to learn the message families before filtering |

## When a query returns nothing

Widen in this order, one change at a time:

1. Drop the field filters, keep `_sourceCategory` and the time range — confirms the source has data at all
2. Widen the time range
3. Relax `_sourceCategory` one path segment (`prod/api/gateway` → `prod/api/*`)
4. Drop the keyword and inspect `_raw` on 5 rows — the field names may differ from what you assumed

If step 1 returns nothing, the source is wrong; go back to `listPartitions` rather than
mutating the query further.
