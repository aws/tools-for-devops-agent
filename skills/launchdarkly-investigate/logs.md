# Investigating with logs

Load this file when the investigation touches application logs: error messages, log levels, the logs of one request, host or session.

## When to reach for logs

- The user quotes an error message or names a service and log level
- You need verbatim evidence for a slice you already found (a host, a version, a route)
- You have a trace ID or session ID and want everything it logged
- You want to know when a message first appeared or how its rate changed

Logs are the best verbatim evidence and the worst overview. For "how many" and "which kinds", use `search-log-patterns` and `search-aggregations` first.

## Group before you page (`search-log-patterns`)

`search-log-patterns` clusters the matching logs into templates with ids and numbers masked, each with a count and the newest example. One call replaces paging hundreds of lines.

- `query: "level=error service_name=<svc>"` (the level key is `level`, not `severity`), plus the slice filter (`host.name=<host>`).
- `patternKeys: ["error.message"]` templates an attribute instead of the message; adding `service_name` splits each pattern by service, which shows a failure shared by every service on one host.
- It scans at most the newest 100,000 matching logs; when `truncated` is true, narrow the window or the filter.
- One root error can appear as several templates with different wrapper prefixes. Group them by the innermost cause before you count.
- Pattern first-seen times are clamped to your window. For the real onset, aggregate the template's words with `search-aggregations` over a wider window.

## Count and trend (`search-aggregations`)

- `productType: "logs"`, `query: "level=error ..."`, `groupBy: "service_name"` or `"host.name"`, `compareTo: "1d"` for the baseline.
- Onset of one message: filter on its bare words, `bucketCount` 24 to 48 over a wide window, or `Min` of `timestamp` with `bucketCount: 1`.

## Read lines (`search-logs`)

- `startDate` is required; ISO 8601 with a timezone.
- `query` takes bare words for message text (`connection reset` matches messages with both words, index-assisted) plus attribute filters. `*x*` and quoted phrases scan every message and are slow over long windows.
- `limit` defaults to 20, at most 50 per page; follow `page.next_cursor` for more, but if you need more than a page or two, aggregate instead.
- `fields` keeps only the attributes you need; `fullAttributes: ["code.stacktrace"]` reads a long value whole.
- `services` and `environments` restrict to exact values.

## Typical patterns

1. **Logs of one request:** `query: "trace_id=<id>"`, a window of a few minutes around the span.
2. **Logs of one host during the incident:** `search-log-patterns` with `host.name=<host> level=error`, then `search-logs` for two or three verbatim examples.
3. **Logs of one session:** `query: "secure_session_id=<id>"`, `startDate` at the session's `created_at`, `endDate` three hours later.
4. **Did this start with a deploy?** Aggregate the message by the version key (from `get-changes`) and compare versions' shares.

## Interpreting results

- Quote log lines verbatim with their timestamp, service and host.
- A burst marks an onset; a steady rate is a standing bug. Check with `compareTo`.
- Error logs can far outnumber error spans when code logs failures without marking spans. Count both before quoting an impact number.

## Common mistakes

- Paging `search-logs` to count. Use `search-log-patterns` or `search-aggregations`.
- Filtering on a key you have not checked with `get-keys`. A bad clause is dropped silently and the result gets wider.
- Using `message="*x*"` when bare words would do.
