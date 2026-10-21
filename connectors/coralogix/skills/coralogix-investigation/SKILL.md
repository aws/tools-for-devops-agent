---
name: coralogix-investigation
description: Query Coralogix logs, traces and metrics for evidence during incident triage,
  root cause analysis and troubleshooting chats. Use this skill whenever the Coralogix
  MCP server is connected and the question involves errors or exceptions, latency,
  failing requests or dependencies, traffic changes, resource saturation, or a Coralogix
  alert that opened the investigation. It maps each question to the right Coralogix tool
  (query_dataprime for logs and spans, query_promql_range and query_promql_instant for
  metrics), shows how to write small aggregated DataPrime and PromQL queries, how to find
  field, label and metric names in an unfamiliar account, how to compare the incident
  window with a healthy baseline, and how to avoid pitfalls such as zero results caused
  by a misspelled field name. The skill only reads data and never changes anything in
  Coralogix.
metadata:
  author: coralogix
  version: "1.0.0"
  summary: "Query Coralogix logs, traces and metrics with DataPrime and PromQL to find evidence during incident investigations."
  tier: "partner-managed"
  agent_types: "INCIDENT_TRIAGE, INCIDENT_RCA, CHAT"
  aws-devops-agent-skills.agent-types: "Incident Triage, Incident RCA, Chat tasks"
  aws-devops-agent-skills.technical-domains: "Observability, Operations"
---

# Coralogix Investigation

Use the Coralogix MCP server to collect log, trace and metric evidence for an investigation. Every query in this skill is read-only.

## Which tool answers which question

| Question | Tool |
|---|---|
| What did the service log, and when did the errors start? | `query_dataprime` with `source logs` (DataPrime) |
| Which operation or downstream call failed or slowed down? What happened in one request? | `query_dataprime` with `source spans` (DataPrime) |
| How did request rate, error ratio, latency, CPU or memory change over the window? | `query_promql_range` (PromQL) |
| What was a value at one moment, such as at alert time compared with one day earlier? | `query_promql_instant` (PromQL) |

Use other Coralogix tools only if the customer allowlisted them. If `get_alerts_object` is available, use it to read the definition of the alert that opened the investigation, including its query and threshold. Never call a tool that creates, updates or deletes Coralogix configuration, such as the `manage_*` tools.

## Workflow

### 1. Set the time window

- Anchor on when the problem started: the alert timestamp, or the time the user gives.
- Incident window: from 30 minutes before the anchor until now, or until the problem ended.
- Baseline window: the same length of time one day earlier, or one week earlier for traffic with a weekly pattern. If the problem started after a normal period, the hour before onset also works.
- Pass `start_date` and `end_date` (UTC, `YYYY-MM-DDTHH:MM:SSZ`) on every `query_dataprime` call. Without them the tool searches only the last 15 minutes.

When a Coralogix alert opened the investigation, the incident title is the alert name, and `data.metadata` holds the alert priority, type, status and a link to the alert. The `service` field can hold the alert name instead of a service name, so derive the service from the title and description.

### 2. Find the service's names in Coralogix

Coralogix groups logs by application and subsystem, and these names may differ from the AWS resource name. Find them before you filter on them:

```
source logs
| filter contains(toLowerCase($l.applicationname), 'checkout') || contains(toLowerCase($l.subsystemname), 'checkout')
| groupby $l.applicationname, $l.subsystemname aggregate count() as events
| orderby events desc
| limit 20
```

In spans the service is `$l.serviceName`. In span metrics it is the `service_name` label. String comparisons are case-sensitive, so search with `toLowerCase()` and `contains()`, then filter on the exact value.

### 3. Measure the symptom with aggregates

Start with counts and percentiles. Read raw records later, only to confirm a finding.

Errors per 5-minute bucket show when the problem started:

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| groupby formatTimestamp(roundTime($m.timestamp, 5m)) as bucket aggregate count() as errors
| orderby bucket asc
```

Failing and slow operations come from spans. `$m.duration` is in microseconds:

```
source spans
| filter $l.serviceName == 'checkout'
| groupby $l.operationName aggregate count() as spans, count_if($d.tags.error:string == 'true') as errors, percentile(0.95, $m.duration) / 1000 as p95_ms
| orderby errors desc
| limit 20
```

For error ratio and latency over time from span metrics, use the PromQL patterns in [references/promql-queries.md](references/promql-queries.md).

### 4. Find what changed

Group errors by log template and compare the incident with the baseline. `$m.templateid` identifies messages that share a pattern. For a baseline right before onset, set `start_date` to the start of the baseline and split on the onset time:

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| groupby $m.templateid aggregate count_if($m.timestamp >= @'2026-03-04T14:00:00Z') as incident, count_if($m.timestamp < @'2026-03-04T14:00:00Z') as baseline
| orderby incident desc
| limit 10
```

Keep both windows the same length. A template with no baseline events is a new failure mode. For a baseline one day earlier, run the same aggregate twice with two windows instead of one query that covers both days.

Read one example of each top template:

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| dedupeby $m.templateid keep 1
| limit 10
```

For metrics, compare with `offset 1d`, as shown in [references/promql-queries.md](references/promql-queries.md).

### 5. Read a few raw records

Fields under `$d` differ between accounts, for example `$d.message`, `$d.msg` or `$d.log`. Read one record to learn the structure, then use `choose` to keep only the fields you need:

```
source logs
| filter $l.subsystemname == 'checkout' && $m.severity >= ERROR
| limit 1
```

To search text, use `find 'timeout' in $d.message` for one field, or `wildfind 'timeout'` for every field. Filter by application or subsystem before `wildfind`.

### 6. Follow one request

Take a trace ID from an error span or log and read the whole trace:

```
source spans
| filter $d.traceID == '<trace id>'
| orderby $m.timestamp asc
| limit 100
| choose $m.timestamp, $l.serviceName, $l.operationName, $m.duration / 1000 as duration_ms, $d.tags.error as error_flag
```

The failing span whose child spans all succeeded is usually where the error started. To find the logs for the same request, search for the trace ID in a narrow window around the trace: `source logs | wildfind '<trace id>' | limit 20`.

### 7. Check saturation and dependencies

Use `query_promql_range` for CPU, memory, restarts or queue depth of the affected workload, and span metrics for database and downstream call latency. Metric names depend on how the account collects metrics, so search for them first, as shown in [references/promql-queries.md](references/promql-queries.md).

## Rules and pitfalls

- **Check `dataprime_warnings` on every DataPrime response.** A misspelled or missing field returns a warning such as `keypath does not exist` and zero rows, not an error. Zero rows with that warning means the query is wrong, not that nothing happened. Fix the field name and run the query again.
- **Treat zero results as "no matching data found", not as proof.** Coralogix documents that MCP queries read archive storage, so logs kept only in Frequent Search may not appear. Say what you searched and over which window.
- **Set the tool's `limit` argument** to cover the rows you expect, such as the number of time buckets. The default is 20 rows. For long windows, use larger buckets, such as `1h` for one day.
- A `groupby` timeline has no row for a bucket with no events. A missing bucket means zero events.
- `$m.severity` is ordered: DEBUG, VERBOSE, INFO, WARNING, ERROR, CRITICAL. `$m.severity >= ERROR` matches ERROR and CRITICAL.
- Span tag names that contain dots need brackets, and numeric tags need a cast: `$d.tags['http.status_code']:number >= 500`.
- Not every failed span carries an `error` tag. Also check HTTP and gRPC status codes, as shown in [references/dataprime-queries.md](references/dataprime-queries.md).
- In PromQL, attribute dots become underscores: `service.name` is the `service_name` label.
- An instant PromQL query without a range function reads only the last sample. Use `rate()` or `increase()` on counters and `max_over_time()` or `avg_over_time()` on gauges.
- For `query_promql_range`, pick a `step` that gives about 20 points per series (`3m` for one hour, `1h` for one day), and reduce the number of series with `sum by` or `topk`.
- Keep results small. Aggregate first, then read a few raw records with `limit` and `choose`.

## Report findings

For each finding, include:

- the tool, the query and the exact time window,
- the incident value, the baseline value and when the change started,
- one or two example log messages, spans or trace IDs as evidence.

State what you could not check: services with no logs, spans or metrics in Coralogix, queries that returned warnings, and data you did not query. Do not name a root cause without the Coralogix evidence that supports it.

## References

- [DataPrime query patterns](references/dataprime-queries.md): syntax, keypaths and recipes for logs and spans.
- [PromQL query patterns](references/promql-queries.md): span metrics, error ratio, latency percentiles, baselines and metric discovery.
