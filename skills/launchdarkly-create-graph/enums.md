# Exact enum values for create-graph and preview-graph

Load this file when you're about to call `create-graph` or `preview-graph`. Use the other values exactly as written; only `productType` accepts any casing.

## `productType` (required)

One of these; the graph tools accept any casing, and PascalCase is conventional:

- `Logs`
- `Traces`
- `Errors`
- `Sessions`
- `Metrics`
- `PAEvents` (product-analytics events: custom events with `type="track" key="<name>"`, page or screen views with `type="*_view" view_name="<path>"`)
- `Events` (legacy session_events source, filtered with `event="<name>"`)

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

- `productType`: lowercase — `logs`, `traces`, `sessions`, `errors`, `metrics`, `paevents`, `events`
- `startDate` / `endDate`: full ISO with time component — `2026-03-04T00:00:00Z`, not date-only `2026-03-04`

The graph tools take `productType` in any case; `get-keys` needs it lowercase.

## Quick sanity check

Before calling `create-graph`, re-read your arguments:

- `projectKey` present? ✓
- `productType` one of the values above? ✓
- `expressions` is a list of objects each with `aggregator` and `column`? ✓
- `aggregator` is PascalCase (no underscore)? ✓
- `column` present even for `Count`? ✓

If any answer is no, fix it before calling. API errors are expensive round-trips.
