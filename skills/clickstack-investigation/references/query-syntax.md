# Writing ClickStack filters

Most ClickStack query tools take a `where` filter and a `whereLanguage` of `lucene` (the default) or `sql`. The syntax in `where` must match `whereLanguage`.

## Column names

- Call `clickstack_describe_source` first. Column names come from the source, not from OpenTelemetry conventions.
- Top-level columns are PascalCase, such as `ServiceName`, `SpanName`, `Duration`, `StatusCode`, `SeverityText` and `Body`.
- Attributes live in map columns, such as `SpanAttributes`, `ResourceAttributes` and `LogAttributes`.

## Lucene

| Need | Example |
|---|---|
| Column contains a value | `ServiceName:checkout` |
| Exact value | `ServiceName:"checkout"` |
| Map attribute | `SpanAttributes.http.method:GET` |
| Comparison | `Duration:>1000000000` |
| Range | `StatusCode:[500 TO 599]` |
| Text in the log body | `timeout` or `"connection refused"` |
| Combine | `ServiceName:"checkout" AND SeverityText:error` |

Pitfalls:

- `Column:value` is a substring match, not equality. `SpanKind:Server` also matches `ServerStreaming`. Quote the value for an exact, case-sensitive match: `SpanKind:"Server"`.
- Lucene uses dots for map attributes. `SpanAttributes['http.method']:GET` doesn't parse.
- A bare term searches the source's default text column (usually the log body). With a text index it matches whole tokens, so `timeout` doesn't match `ConnectionTimeoutException`.

## SQL

Use `whereLanguage: "sql"` for `IN (...)` lists, functions, substring matches inside words, and comparisons with literal timestamps.

| Need | Example |
|---|---|
| Exact value | `ServiceName = 'checkout'` |
| Map attribute | `SpanAttributes['http.method'] = 'POST'` |
| List | `ServiceName IN ('checkout', 'payment')` |
| Substring inside a word | `Body ILIKE '%timeout%'` |
| Cast an attribute | `toFloat64OrZero(SpanAttributes['http.response.size']) > 1e6` |

Common mistake: writing `Column:value` while `whereLanguage` is `sql`.

## Durations and units

- Trace `Duration` is usually in nanoseconds. Divide by `1e6` for milliseconds in a `valueExpression`, and use nanoseconds in filters: 1 second is `1000000000`.
- Check the source description: some sources store duration in other units.

## Required source filters

Some sources declare `requiredSourceFilters`, such as an environment or tenant column. Every query against them must pass `sourceFilters`:

```json
{ "Environment": ["production"] }
```

Get the valid values from `clickstack_get_source_filter_values`. When a trace query also returns linked logs, one `sourceFilters` map covers both sources, matched by column name.
