# DataPrime query patterns

Use these patterns with the `query_dataprime` tool. Set `start_date` and `end_date` on every call, and replace `checkout`, the operation names and the timestamps with values from the investigation.

## Syntax

- A query starts with `source logs` or `source spans`, followed by commands separated by `|`. A query can span several lines.
- Keypath prefixes: `$m` is metadata, `$l` is labels and `$d` is the event body. A name without a prefix refers to `$d`.
- Strings use single quotes. Timestamps look like `@'2026-03-04T14:00:00Z'`. Intervals look like `5m` or `1h`.
- Combine conditions with `&&`, `||` and parentheses. Test for a missing field with `== null`.
- Cast a value with `:number` or `:string`, for example `$d.tags['http.status_code']:number`.

### Keypaths

| Keypath | Logs | Spans |
|---|---|---|
| `$m.timestamp` | Event time | Span start time |
| `$m.severity` | DEBUG, VERBOSE, INFO, WARNING, ERROR or CRITICAL | Not present |
| `$m.templateid` | ID shared by messages with the same pattern | Not present |
| `$m.duration` | Not present | Span duration in microseconds |
| `$l.applicationname` | Application | Application |
| `$l.subsystemname` | Subsystem | Subsystem |
| `$l.serviceName` | Not present | Service name |
| `$l.operationName` | Not present | Operation name |
| `$d.traceID` | Not standard, log fields vary | Trace ID |
| `$d.tags` | Not present | Span attributes, such as `$d.tags['http.status_code']` |

Other `$d` fields depend on what each account sends. Read one record with `limit 1` to see them.

### Commands

| Command | What it does |
|---|---|
| `filter <condition>` | Keeps events that match |
| `groupby <keys> aggregate <functions>` | Aggregates per group |
| `countby <expression>` | Counts events per value |
| `distinct <keys>` | Lists distinct values |
| `orderby <expression> desc` | Sorts, `asc` or `desc` |
| `limit <n>` | Caps the number of rows |
| `choose <keypaths>` | Keeps only the listed fields; `as` renames one |
| `create <name> from <expression>` | Adds a computed field |
| `dedupeby <expression> keep 1` | Keeps one event per value |
| `find '<text>' in <keypath>` | Searches for text in one field |
| `wildfind '<text>'` | Searches for text in every field |

### Functions

- Aggregation: `count()`, `count_if(<condition>)`, `distinct_count(<x>)`, `avg(<x>)`, `max(<x>)` and `percentile(0.95, <x>)`, where the first argument is between 0 and 1.
- Time: `roundTime($m.timestamp, 5m)` puts a timestamp in a bucket, and `formatTimestamp(<timestamp>)` makes it readable.
- Strings: `contains(<string>, '<text>')` and `toLowerCase(<string>)`.
- Numbers: `round(<x>, 2)`.

## Logs

### Applications and subsystems with errors

```
source logs
| filter $m.severity >= ERROR
| groupby $l.applicationname, $l.subsystemname aggregate count() as errors
| orderby errors desc
| limit 20
```

### Error percentage per subsystem

```
source logs
| filter $l.applicationname == 'shop'
| groupby $l.subsystemname aggregate count() as events, count_if($m.severity >= ERROR) as errors
| create error_pct from round(100 * errors / events, 2)
| orderby error_pct desc
| limit 20
```

### Error timeline

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| groupby formatTimestamp(roundTime($m.timestamp, 5m)) as bucket aggregate count() as errors
| orderby bucket asc
```

Set the tool's `limit` to at least the number of buckets in the window.

### New error templates

Set `start_date` to the start of the baseline and use the onset time as the split:

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| groupby $m.templateid aggregate count_if($m.timestamp >= @'2026-03-04T14:00:00Z') as incident, count_if($m.timestamp < @'2026-03-04T14:00:00Z') as baseline
| orderby incident desc
| limit 10
```

### One example per template

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| dedupeby $m.templateid keep 1
| limit 10
```

### Text search

```
source logs
| filter $l.subsystemname == 'checkout'
| find 'timeout' in $d.message
| limit 20
```

If the message field has another name, `find` returns zero rows with a `keypath does not exist` warning. Use `wildfind 'timeout'` to search every field.

### Logs for one trace

Use a window of a few minutes around the start of the trace:

```
source logs
| wildfind '<trace id>'
| limit 20
```

## Spans

### Services and operations with errors

```
source spans
| filter $d.tags.error:string == 'true'
| groupby $l.serviceName, $l.operationName aggregate count() as errors
| orderby errors desc
| limit 20
```

### Failed calls without an error tag

Not every failed call sets the `error` tag. This query finds HTTP 5xx responses and non-zero gRPC status codes on spans without it:

```
source spans
| filter $l.serviceName == 'checkout'
| filter $d.tags.error == null && ($d.tags['http.status_code']:number >= 500 || $d.tags['http.response.status_code']:number >= 500 || $d.tags['rpc.grpc.status_code']:number > 0)
| groupby $l.operationName aggregate count() as failed
| orderby failed desc
| limit 20
```

Older OpenTelemetry instrumentation writes `http.status_code`, and newer instrumentation writes `http.response.status_code`.

### Latency percentiles per operation

```
source spans
| filter $l.serviceName == 'checkout'
| groupby $l.operationName aggregate count() as spans, percentile(0.5, $m.duration) / 1000 as p50_ms, percentile(0.95, $m.duration) / 1000 as p95_ms, percentile(0.99, $m.duration) / 1000 as p99_ms
| orderby p95_ms desc
| limit 20
```

### Latency timeline for one operation

```
source spans
| filter $l.serviceName == 'checkout' && $l.operationName == 'POST /orders'
| groupby formatTimestamp(roundTime($m.timestamp, 5m)) as bucket aggregate count() as spans, percentile(0.95, $m.duration) / 1000 as p95_ms
| orderby bucket asc
```

### Slowest spans

```
source spans
| filter $l.serviceName == 'checkout'
| orderby $m.duration desc
| limit 10
| choose $m.timestamp, $l.operationName, $m.duration / 1000 as duration_ms, $d.traceID
```

### One trace

```
source spans
| filter $d.traceID == '<trace id>'
| orderby $m.timestamp asc
| limit 100
| choose $m.timestamp, $l.serviceName, $l.operationName, $m.duration / 1000 as duration_ms, $d.tags.error as error_flag
```

If this returns zero rows with a `keypath does not exist` warning, read one span with `limit 1` to find the trace ID field.

## Real User Monitoring

If the problem is in a browser or mobile app and the account uses Coralogix Real User Monitoring (RUM), the events are in `source rum.events`. Read one record with `limit 1` before you filter. A `source does not exist` error means the account has no RUM data.
