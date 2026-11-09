# Relational Fields Guide

Honeycomb's relational field prefixes enable trace-aware queries that correlate data
across span relationships within a trace. This is one of Honeycomb's most powerful
and distinctive features.

## Prefix Reference

### root.
Match against the root span of the trace.
- **Returns**: The root span itself
- **Use case**: Filter by API entry point while examining child spans
- **Examples**:
  - All spans in checkout traces: `"filters": [{"column": "root.http.route", "op": "=", "value": "/api/checkout"}]`
  - P99 latency by span name for HTTP GET root spans:
    ```json
    { "calculations": [{"op": "P99", "column": "duration_ms"}], "filters": [{"column": "root.name", "op": "=", "value": "HTTP GET"}], "breakdowns": ["name"] }
    ```

### parent.
Match against the direct parent of each span.
- **Returns**: The child span (whose parent matched)
- **Use case**: Find children of specific operations
- **Example**: Find children of database queries by operation:
  ```json
  { "calculations": [{"op": "COUNT"}], "filters": [{"column": "parent.name", "op": "=", "value": "database-query"}], "breakdowns": ["name"] }
  ```

### child.
Match against direct children of each span.
- **Returns**: The parent span (whose child matched)
- **Use case**: Find parents that spawned specific child operations
- **Example**: Count parents with erroring children, grouped by operation:
  ```json
  { "calculations": [{"op": "COUNT"}], "filters": [{"column": "child.error", "op": "=", "value": true}], "breakdowns": ["name"] }
  ```

### any. / any2. / any3.
Match against any span anywhere in the trace. Up to three distinct `any` conditions.
- **Returns**: The span being evaluated
- **Use case**: Cross-service correlation, find traces containing specific patterns
- **Examples**:
  - Traces with payment errors: `"filters": [{"column": "any.service.name", "op": "=", "value": "payment"}, {"column": "any.error", "op": "=", "value": true}]`
  - Traces touching both auth and database services: `"filters": [{"column": "any.service.name", "op": "=", "value": "auth"}, {"column": "any2.service.name", "op": "=", "value": "database"}]`
- **Constraints**: `any` in GROUP BY requires a matching WHERE clause. OR combination not supported with relational fields.

### none.
Exclude traces that contain a matching span.
- **Returns**: Spans from traces that do NOT match
- **Use case**: Find traces missing expected spans, detect instrumentation gaps
- **Examples**:
  - Traces that never hit cache: `"filters": [{"column": "none.service.name", "op": "=", "value": "cache"}]`
  - Traces with no root span (broken traces): `"filters": [{"column": "none.trace.parent_id", "op": "does-not-exist"}]`
- **Constraint**: `none.` not allowed in GROUP BY.

## Common Patterns

### Find what's slow in a specific user flow
```json
{
  "calculations": [{ "op": "P99", "column": "duration_ms" }],
  "filters": [{ "column": "root.http.route", "op": "=", "value": "/api/checkout" }],
  "breakdowns": ["name", "service.name"],
  "orders": [{ "op": "P99", "column": "duration_ms", "order": "descending" }]
}
```

### Cross-service error correlation
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [
    { "column": "error", "op": "=", "value": true },
    { "column": "any.service.name", "op": "=", "value": "payment-service" }
  ],
  "breakdowns": ["service.name", "name"]
}
```

### Detect missing instrumentation
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "none.trace.parent_id", "op": "does-not-exist" }],
  "breakdowns": ["trace.trace_id"],
  "limit": 20
}
```

### Find traces that are slow AND have errors
```json
{
  "calculations": [{ "op": "COUNT" }, { "op": "P99", "column": "duration_ms" }],
  "filters": [
    { "column": "root.duration_ms", "op": ">", "value": 5000 },
    { "column": "any.error", "op": "=", "value": true }
  ],
  "breakdowns": ["root.name"]
}
```

### Compare latency when a specific service is involved
```json
{
  "calculations": [
    { "op": "P50", "column": "duration_ms" },
    { "op": "P99", "column": "duration_ms" }
  ],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["any.service.name"]
}
```

## Important Constraints

- Relational queries are more expensive — use WHERE filters to narrow scope first
- Up to 3 distinct `any` prefixes (`any.`, `any2.`, `any3.`) per query
- `root.` is the most commonly used — start investigations there
- Relational queries require trace data (not applicable to metrics/logs datasets)
- Relational field prefixes are NOT supported in calculations — only in filters and breakdowns
- OR combination not supported with relational fields
