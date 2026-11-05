# Trigger Examples

## Error Rate Triggers

### General error spike
Count of errors on root spans.
```json
{
  "calculations": [{"op": "COUNT"}],
  "filters": [
    {"column": "error", "op": "=", "value": true},
    {"column": "is_root", "op": "=", "value": true}
  ],
  "time_range": "5m"
}
```
Threshold: > [baseline * 3] | Frequency: every 2 minutes

### HTTP 5xx errors
Count of root spans with 5xx status codes.
```json
{
  "calculations": [{"op": "COUNT"}],
  "filters": [
    {"column": "http.status_code", "op": ">=", "value": 500},
    {"column": "is_root", "op": "=", "value": true}
  ],
  "time_range": "5m"
}
```
Threshold: > 50 | Frequency: every 2 minutes

### Specific exception type
Count of a specific exception class.
```json
{
  "calculations": [{"op": "COUNT"}],
  "filters": [
    {"column": "exception.type", "op": "=", "value": "DatabaseConnectionException"}
  ],
  "time_range": "10m"
}
```
Threshold: > 5 | Frequency: every 5 minutes

## Latency Triggers

### Slow request count (recommended over P99 for alerting)
Count of root spans exceeding a latency threshold.
```json
{
  "calculations": [{"op": "COUNT"}],
  "filters": [
    {"column": "duration_ms", "op": ">", "value": 2000},
    {"column": "is_root", "op": "=", "value": true}
  ],
  "time_range": "5m"
}
```
Threshold: > 50 | Frequency: every 2 minutes

**Why this over P99**: Counting slow requests is more actionable. "50 slow requests" is clearer than "P99 is 2100ms."

### Overall P99 latency
P99 latency across all root spans.
```json
{
  "calculations": [{"op": "P99", "column": "duration_ms"}],
  "filters": [
    {"column": "is_root", "op": "=", "value": true}
  ],
  "time_range": "10m"
}
```
Threshold: > 3000 | Frequency: every 5 minutes

### Per-endpoint latency
P99 latency for a specific route.
```json
{
  "calculations": [{"op": "P99", "column": "duration_ms"}],
  "filters": [
    {"column": "is_root", "op": "=", "value": true},
    {"column": "http.route", "op": "=", "value": "/api/checkout"}
  ],
  "time_range": "10m"
}
```
Threshold: > 1000 | Frequency: every 5 minutes

## Infrastructure Triggers

### Database connection limits
Max active connections in the database pool.
```json
{
  "calculations": [{"op": "MAX", "column": "db.pool.active_connections"}],
  "time_range": "5m"
}
```
Threshold: > [pool_size * 0.8] | Frequency: every 1 minute

### Lambda/function cost spikes
Total estimated cost across serverless function invocations.
```json
{
  "calculations": [{"op": "SUM", "column": "cost_estimate"}],
  "filters": [
    {"column": "faas.name", "op": "exists"}
  ],
  "time_range": "60m"
}
```
Threshold: > [budget_threshold] | Frequency: every 15 minutes

### Queue depth
Max queue depth.
```json
{
  "calculations": [{"op": "MAX", "column": "queue.depth"}],
  "time_range": "5m"
}
```
Threshold: > 1000 | Frequency: every 2 minutes

## Security Triggers

### Unusual login volume
Count of distinct users with successful logins.
```json
{
  "calculations": [{"op": "COUNT_DISTINCT", "column": "user.id"}],
  "filters": [
    {"column": "http.route", "op": "=", "value": "/login"},
    {"column": "http.status_code", "op": "=", "value": 200}
  ],
  "time_range": "15m"
}
```
Threshold: > [baseline * 5] | Frequency: every 5 minutes

### Failed authentication spike
Count of failed login attempts.
```json
{
  "calculations": [{"op": "COUNT"}],
  "filters": [
    {"column": "http.route", "op": "=", "value": "/login"},
    {"column": "http.status_code", "op": "=", "value": 401}
  ],
  "time_range": "5m"
}
```
Threshold: > 100 | Frequency: every 2 minutes

## Best Practices for All Triggers

- **Duration**: At least 5 minutes to avoid flapping
- **Frequency**: At most duration/2 for responsive alerting
- **Threshold**: Start high, lower based on false positive rate
- **Naming**: "High error rate on checkout API" not "Trigger 1"
- **Description**: Include link to runbook and first-responder steps
- **Filters**: Add WHERE clauses to improve signal quality

## Monitoring Triggers with MCP

Use `get_triggers` to check trigger status:
- List view: Shows all triggers with current status
- Detailed view: Shows trigger configuration, query, thresholds, and notification setup
- Filter by environment or tags: `get_triggers(environment_slug: "production", tags: ["team:platform"])`
