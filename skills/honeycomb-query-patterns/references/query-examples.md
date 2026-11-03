# Honeycomb Query Examples

Organized by investigation goal. Each example shows the query pattern in both human-readable
form and `run_query` parameter format.

## Performance Analysis

### Slowest endpoints (P99 latency)
```json
{
  "calculations": [{ "op": "P99", "column": "duration_ms" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["http.route"],
  "orders": [{ "op": "P99", "column": "duration_ms", "order": "descending" }],
  "limit": 20,
  "time_range": "2h"
}
```

### Latency distribution (spot bimodal patterns)
```json
{
  "calculations": [{ "op": "HEATMAP", "column": "duration_ms" }],
  "filters": [
    { "column": "is_root", "op": "=", "value": true },
    { "column": "service.name", "op": "=", "value": "api-gateway" }
  ],
  "time_range": "1h"
}
```

### Database query performance
```json
{
  "calculations": [
    { "op": "P90", "column": "duration_ms" },
    { "op": "COUNT" }
  ],
  "filters": [{ "column": "db.system", "op": "exists" }],
  "breakdowns": ["db.statement"],
  "orders": [{ "op": "P90", "column": "duration_ms", "order": "descending" }],
  "time_range": "1h"
}
```

### Latency trend detection
```json
{
  "calculations": [{ "op": "RATE_AVG", "column": "duration_ms" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["name"],
  "time_range": "6h"
}
```

### Concurrent request load
```json
{
  "calculations": [{ "op": "CONCURRENCY" }],
  "filters": [{ "column": "service.name", "op": "=", "value": "api-gateway" }],
  "time_range": "1h"
}
```

## Error Analysis

### Error rate by service
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "error", "op": "=", "value": true }],
  "breakdowns": ["service.name"],
  "time_range": "2h"
}
```

### Exception event breakdown (Logs API)

For new OTel Logs API exception events, query the event row rather than assuming the containing
span has `exception.*`. First discover the actual dataset columns with `get_dataset_columns` or
`find_columns`; then use only fields present in that schema.

Human-readable shape:

```text
COUNT
WHERE event.name = "exception"
  AND exception.type exists
  AND trace.trace_id exists
GROUP BY service.name, exception.type
```

MCP `run_query` shape (add `meta.signal_type = log` when that discovered column exists):

```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [
    { "column": "event.name", "op": "=", "value": "exception" },
    { "column": "exception.type", "op": "exists" },
    { "column": "trace.trace_id", "op": "exists" }
  ],
  "breakdowns": ["service.name", "exception.type"],
  "orders": [{ "op": "COUNT", "order": "descending" }],
  "limit": 20,
  "time_range": "2h"
}
```

Run a second query with `include_samples=true` to obtain `trace.trace_id`, `trace.parent_id`,
`exception.message`, and `exception.stacktrace`; then call `get_trace` for a representative trace.
For legacy span-event exceptions, use `name = "exception"` and `meta.signal_type = "trace"`.
Do not use `name = "exception"` as the only exception query.

### Error rate with total traffic context
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["error", "http.route"],
  "time_range": "2h"
}
```

### Errors affecting specific tenants
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [
    { "column": "error", "op": "=", "value": true },
    { "column": "is_root", "op": "=", "value": true },
    { "column": "app.tenant", "op": "exists" }
  ],
  "breakdowns": ["app.tenant", "name"],
  "time_range": "2h"
}
```

### HTTP status code distribution
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["http.status_code"],
  "time_range": "2h"
}
```

## Traffic Patterns

### Request volume by endpoint
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["http.route"],
  "orders": [{ "op": "COUNT", "order": "descending" }],
  "time_range": "2h"
}
```

### Unique users over time
```json
{
  "calculations": [{ "op": "COUNT_DISTINCT", "column": "user.id" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "time_range": "24h"
}
```

### Traffic by HTTP method
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "breakdowns": ["http.method", "http.route"],
  "time_range": "2h"
}
```

## Instrumentation Health

### Events missing expected fields
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [
    { "column": "service.name", "op": "exists" },
    { "column": "user.id", "op": "does-not-exist" },
    { "column": "is_root", "op": "=", "value": true }
  ],
  "breakdowns": ["http.route"],
  "time_range": "24h"
}
```

### Services sending data
```json
{
  "calculations": [{ "op": "COUNT_DISTINCT", "column": "service.name" }],
  "time_range": "24h"
}
```

### Orphaned spans (no parent, but not root)
```json
{
  "calculations": [{ "op": "COUNT" }],
  "filters": [
    { "column": "trace.parent_id", "op": "does-not-exist" },
    { "column": "is_root", "op": "!=", "value": true }
  ],
  "breakdowns": ["service.name"],
  "time_range": "24h"
}
```

## Cross-Service Investigation

### Traces touching specific services
```json
{
  "calculations": [
    { "op": "COUNT" },
    { "op": "P99", "column": "duration_ms" }
  ],
  "filters": [
    { "column": "any.service.name", "op": "=", "value": "payment-service" },
    { "column": "is_root", "op": "=", "value": true }
  ],
  "breakdowns": ["root.name"],
  "time_range": "2h"
}
```

### Slow downstream dependency
```json
{
  "calculations": [{ "op": "P99", "column": "duration_ms" }],
  "filters": [{ "column": "root.http.route", "op": "=", "value": "/api/checkout" }],
  "breakdowns": ["service.name", "name"],
  "orders": [{ "op": "P99", "column": "duration_ms", "order": "descending" }],
  "time_range": "2h"
}
```

### Service-to-service latency
```json
{
  "calculations": [{ "op": "P99", "column": "duration_ms" }],
  "filters": [{ "column": "parent.service.name", "op": "=", "value": "api-gateway" }],
  "breakdowns": ["service.name"],
  "time_range": "2h"
}
```

## Inline Calculated Fields

### SLI calculation (success rate)
```json
{
  "calculated_fields": [
    { "name": "is_successful", "expression": "LTE($http.status_code, 499)" }
  ],
  "calculations": [
    { "op": "COUNT" },
    { "op": "SUM", "column": "is_successful" }
  ],
  "filters": [{ "column": "is_root", "op": "=", "value": true }],
  "time_range": "24h"
}
```

### Custom error classification
```json
{
  "calculated_fields": [
    { "name": "error_type", "expression": "IF(GTE($http.status_code, 500), \"server_error\", IF(GTE($http.status_code, 400), \"client_error\", \"success\"))" }
  ],
  "calculations": [{ "op": "COUNT" }],
  "breakdowns": ["error_type"],
  "time_range": "2h"
}
```

## Data Organization Notes

- **Environments** separate production, staging, dev data — all trace data for a trace must be in the same environment
- **Service datasets** contain tracing spans; **general datasets** contain logs/metrics
- Use `get_workspace_context` first, then `find_columns` to discover available fields
- Field naming conventions matter — well-named fields improve both manual and AI-driven analysis
- **Dataset Definitions** standardize field names across a dataset — check these for naming conventions
