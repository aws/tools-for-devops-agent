# Exact enum values for create-graph and preview-graph

Load this file when you're about to call `create-graph` or `preview-graph`. The API is strict about casing — wrong case means the call is rejected.

## `productType` (PascalCase, required)

Use exactly one of:

- `Logs`
- `Traces`
- `Errors`
- `Sessions`
- `Metrics`
- `Events`

**Do NOT** use `sessions`, `errors`, `logs`, `traces`, `metrics` (lowercase). The API rejects them.

## `expressions` (required, list of objects)

Each expression MUST have both keys:

```json
{
  "aggregator": "Count",
  "column": ""
}
```

### `aggregator` values

- `Count`
- `CountDistinct`
- `CountDistinctKey`
- `Min`
- `Avg`
- `P50`
- `P90`
- `P95`
- `P99`
- `Max`
- `Sum`

**Do NOT** use `count_distinct`, `Count_distinct`, `countdistinct`, or any snake_case variant. It's `CountDistinct` — PascalCase, no underscore.

### `column` is always required

Even for `Count` where no column is needed. Pass an empty string:

```json
{"aggregator": "Count", "column": ""}
```

Omitting `column` crashes the call with an argument-validation error.

## `type` (graph chart type)

- `Line chart`
- `Bar chart`
- `Table`

## `bucketBy`

Default: `Timestamp`. Usually fine to omit or leave as default. For non-time aggregations (e.g., grouping by service across a fixed window), omit `bucketBy` and rely on `groupBy`.

## `get-keys` argument formats

Different from `create-graph` — `get-keys` wants lowercase `productType` and full ISO timestamps:

- `productType`: lowercase — `logs`, `traces`, `sessions`, `errors`, `metrics`, `events`
- `startDate` / `endDate`: full ISO with time component — `2026-03-04T00:00:00Z`, not date-only `2026-03-04`

Yes, `create-graph` wants `Sessions` (PascalCase) and `get-keys` wants `sessions` (lowercase). It's inconsistent. Just remember: `get-keys` is lowercase, the graph tools are PascalCase.

## Quick sanity check

Before calling `create-graph`, re-read your arguments:

- `projectKey` present? ✓
- `productType` PascalCase? ✓
- `expressions` is a list of objects each with `aggregator` and `column`? ✓
- `aggregator` is PascalCase (no underscore)? ✓
- `column` present even for `Count`? ✓

If any answer is no, fix it before calling. API errors are expensive round-trips.
