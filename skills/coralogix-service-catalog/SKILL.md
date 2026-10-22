---
name: coralogix-service-catalog
description: The fast, authoritative path for APM/RED data — error rate, latency percentiles (p50-p99), throughput, health status, resource saturation (CPU/memory/OOMKilled for k8s-pod, heap/thread/GC for jvm), and dependency latency — across services, databases, operations, k8s pods, and JVMs. Load this FIRST for any question about service errors, slowness, latency, health, or saturation, including broad ones like "is any service erroring or slow right now?", before reaching for raw spans or PromQL. Also covers inventory questions such as listing services or available entity types.
metadata:
  author: coralogix
  version: 1.0.0
---

# Service Catalog Skill

Use this skill to discover and query **Service Catalog entities** — a column-oriented view over RED
metrics (latency, throughput, error rate), health (policy evaluation status), resource saturation
(CPU/memory/OOMKilled for `k8s-pod`; heap/thread/GC for `jvm`), and dependencies, for whichever
entity type the account has data for. There is no separate metrics/health/dependencies endpoint —
one request/response shape carries all of it.

## Tools

| Tool                                    | Purpose                                                        | Key parameters                                                                                                  |
|------------------------------------------|-----------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| `list_service_catalog_entity_types`      | List entity types the account has data for (service, jvm, ...)  | -                                                                                                                  |
| `get_service_catalog_entity_type_schema` | Discover columns/labels for one entity type                     | `entity_type`                                                                                                     |
| `list_service_catalog_entities`          | List known entities of one type (e.g. service names)             | `entity_type`                                                                                                      |
| `get_service_catalog_entities_data`      | Fetch column data, across all entities or one (`entity_id`) drilldown | `entity_type`, `start`, `end`, `columns` (required); `entity_id`, `group_by`, `filters`, `data_aggregation_type`, `limit`, `sort_column`, `sort_order` |

All tools are **read-only**.

- **Entity types, columns, and labels are dynamic per account and per entity type — never guess
  them.** `service` and `k8s-pod` differ in what they expose (e.g. `service` has
  `dependencyLatencyPerRequest`; `k8s-pod` has `oomKilled`); always confirm via
  `get_service_catalog_entity_type_schema` before building a `get_service_catalog_entities_data`
  call.
- **Exception — `health`, `slo`, and `signals` are queryable but are not listed in the schema's
  `columns`.** They appear only in `default_columns`. Request them by name anyway; they resolve
  normally. Do not conclude from their absence in `columns` that health data is unavailable.
- `get_service_catalog_entities_data` is a single tool for both the many-entities and one-entity
  cases — do not look for a separate "single entity" tool. Omit `entity_id` to query across every
  entity of the type; set it (using a `name` from `list_service_catalog_entities`) to drill down
  into exactly one entity. Both return the same `rows`/`series` envelope.
- `limit`, `sort_column`, and `sort_order` only apply to `data_aggregation_type="table"` queries
  across many entities — they are rejected outright when `entity_id` is set (a single entity has at
  most one row/series per group) and silently meaningless for `"timeseries"`, so the tool rejects
  them there too.
- `filters` is a list of `{label_name, label_values, metric_label_name?}`; multiple filters combine
  with **AND**, `label_values` combine with **OR**. An unrecognized *key* in a filter object (e.g.
  `metric_label` instead of `metric_label_name`) fails the call rather than being silently dropped.
  `filterable_labels` from the schema is a discovery hint for which labels are known to be
  meaningful to filter on for this entity type — it is **not** an enforced allow-list: filtering by
  a `label_name` outside that list is accepted, not rejected, and simply won't match anything if the
  label doesn't apply. Prefer `filterable_labels` when choosing a filter, but don't assume an
  unlisted label will error out.

## Discovery Workflow

Four steps, and only because each one supplies an input the next one requires:

1. **Discover entity types** — dynamic per account, so never guess:

   ```python
   list_service_catalog_entity_types()
   ```

2. **Get the schema** for the entity type you care about — this gives you the valid `columns`,
   `groupable_labels`, `filterable_labels`, and any `required_filters`:

   ```python
   get_service_catalog_entity_type_schema(entity_type="service")
   ```

3. **List entities** of that type, if you need to drill into one specific entity by name:

   ```python
   list_service_catalog_entities(entity_type="service")
   ```

4. **Query data** — aggregated across all entities, or scoped to one:

   ```python
   get_service_catalog_entities_data(
       entity_type="service", start=..., end=...,
       columns=["errorRate", "totalRequests"],
   )

   get_service_catalog_entities_data(
       entity_type="service", entity_id="checkout", start=..., end=...,
       columns=["errorRate"],
   )
   ```

## Examples

### Top 5 services by p99 latency in the last hour

Latency column ids on `service` are `p50`/`p75`/`p90`/`p95`/`p99` (plus `avgLatency`) — there is no
`latencyP99`.

```python
get_service_catalog_entities_data(
    entity_type="service", start=start, end=end,
    columns=["p99"], data_aggregation_type="table",
    sort_column="p99", sort_order="desc", limit=5,
)
```

### Health of services — the answer to any "is X healthy?" question

`health` is the authoritative health signal. Answer health questions from this column rather than
inferring health from `errorRate`/`p99` or from logs, spans, or alert history.

```python
# health across all services
get_service_catalog_entities_data(
    entity_type="service", start=start, end=end, columns=["health"],
)

# health of one named service
get_service_catalog_entities_data(
    entity_type="service", entity_id="checkout", start=start, end=end,
    columns=["health", "errorRate", "p99"],
)
```

Each row's `health` value carries an overall status plus the per-policy breakdown behind it:

```json
{
  "worst": "EVALUATION_STATUS_OK",
  "policyBreakdown": [
    {
      "policyId": "9918790e-...", "policyType": "POLICY_TYPE_LOG_ERRORS",
      "status": "EVALUATION_STATUS_OK", "currentValue": "0.00",
      "groupResults": [{"group": {"deploymentEnvironmentName": "prod"}, "status": "EVALUATION_STATUS_OK", "currentValue": "0.00"}]
    }
  ]
}
```

Report `worst` as the service's health, then name which policies are not OK and their
`currentValue` — that is what makes the verdict actionable. `groupResults` breaks the same policy
down per environment, so a service can be healthy in one environment and not another.

If the row carries a caveat, that same object arrives wrapped as
`{"value": {"worst": ..., "policyBreakdown": [...]}, "warning": {...}}`. Read `worst` from inside
`value` and state the warning alongside the verdict — a wrapped result still contains a real health
status, so do not treat it as unavailable.

When the query returns no rows, or `health` comes back as `{"error": ...}` instead of a status,
health is genuinely unavailable — no health policies are configured for that entity, or the entity
has no data in the requested window. Say so, and name the entity, time range, or account limitation
responsible, instead of substituting another signal for the verdict. `errorRate`/`p99` may be
offered as supporting evidence alongside that statement, labelled as such and never as the health
status itself.

### Filter to one environment

```python
get_service_catalog_entities_data(
    entity_type="service", start=start, end=end,
    columns=["p99", "errorRate"],
    filters=[{"label_name": "deployment_environment_name", "label_values": ["prod"]}],
)
```

### Kubernetes pod resource saturation

```python
get_service_catalog_entity_type_schema(entity_type="k8s-pod")  # discover column ids first
get_service_catalog_entities_data(
    entity_type="k8s-pod", start=start, end=end,
    columns=["cpuUtilizationProm", "k8sPodMemoryWorkingSet", "oomKilled"],
)
```

### Latency over time for one service

```python
get_service_catalog_entities_data(
    entity_type="service", entity_id="checkout", start=start, end=end,
    columns=["p99"], data_aggregation_type="timeseries",
)
```

## Key Principles

- **Discover before querying** — entity types, columns, and labels are all dynamic; always resolve
  them through `list_service_catalog_entity_types` / `get_service_catalog_entity_type_schema` first.
- **One data tool, two shapes of the same query** — `entity_id` is what distinguishes a
  many-entities query from a single-entity drilldown; the response envelope (`rows` for `table`,
  `series` for `timeseries`) is identical either way.
- **`table` vs `timeseries`** — `table` gives one row per group for the whole window (use with
  `limit`/`sort_column`/`sort_order` to find top/bottom offenders); `timeseries` gives one series
  per group/column with datapoints over the window.
- **A `{"error": ...}` value for one column is not a query failure** — the response can mix
  successfully resolved columns with per-column errors (e.g. a cardinality limit) in the same row;
  only report the specific column as unavailable, don't discard the whole row.
- **In `table` rows, a column that resolved with a caveat is wrapped as
  `{"value": ..., "warning": ...}`** — the real value moves one level down under `value`, whatever
  the column's type. So `errorRate` may arrive as either `0.42` or
  `{"value": 0.42, "warning": {...}}`, and `health` as either `{"worst": ...}` or
  `{"value": {"worst": ...}, "warning": {...}}`. Before reading a row's column, check for a
  `warning` key and unwrap `value` if present. A warning means the value is usable but qualified —
  report it with the caveat, not as missing data. The warning object can be empty (`{}`) when the
  server flagged a caveat without detail; that is still a caveat worth mentioning.
- **`timeseries` responses use a different shape — no `value`/`warning` wrapper** — each entry in
  `series` keeps its own structure: `columnId`, `labels`, `datapoints` (a list of
  `{"timestampSeconds": ..., "value": ...}`, where `timestampSeconds` is a JSON string), and an
  optional series-level `error`. A series carrying `error` is the timeseries equivalent of a
  per-column failure: report that series as unavailable and keep reading the others.

## Related Skills

- Use the metrics tools (`query_promql_instant` / `query_promql_range`) for ad-hoc PromQL beyond the
  fixed Service Catalog columns.
- Use the logs/spans tools to correlate a Service Catalog health or error-rate signal with the
  underlying logs/spans for one service.

## MCP tools

### `get_service_catalog_entities_data`

- **`start`** / **`end`**: unix seconds (`end` must be > `start`).
- **`entity_id`** (optional): exactly one named entity, as returned by
  `list_service_catalog_entities`. When set, `limit`/`sort_column`/`sort_order` are rejected.
- **`group_by`** (optional): labels to group rows by, capped at the schema's `group_by_limit`.
- **`filters`** (optional): list of `{label_name, label_values, metric_label_name?}` objects.
- **`data_aggregation_type`**: `"table"` (default) or `"timeseries"`.
- **`widget_name`** (optional): free-form label attached to the query for server-side
  telemetry/attribution.
