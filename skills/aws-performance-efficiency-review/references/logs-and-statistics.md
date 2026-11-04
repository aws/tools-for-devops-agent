# Logs and statistics

CloudWatch Logs Insights fills the gaps metrics leave: per-request duration when no latency metric exists (common for queue consumers and batch jobs), when an error was first seen, and how work splits across hosts or tasks. Use `logs:StartQuery` then `logs:GetQueryResults`. Keep the window and the log group the same as the rest of the investigation, and give timestamps in UTC.

These are patterns, not final queries. Replace field names (`duration_ms`, `level`, `host`) with the fields the workload actually logs, and confirm the log format before trusting a parse.

## Query patterns

### Duration percentiles from structured logs

For logs that carry a numeric duration field:

```
fields @timestamp, duration_ms
| filter ispresent(duration_ms)
| stats count(*) as n,
        pct(duration_ms, 50) as p50,
        pct(duration_ms, 90) as p90,
        pct(duration_ms, 99) as p99,
        max(duration_ms) as max
```

If duration is not a field, extract it first with `parse @message "...took * ms..." as duration_ms`.

### Slow lines over time (trend, not a single number)

```
fields @timestamp, duration_ms
| filter ispresent(duration_ms)
| stats pct(duration_ms, 99) as p99, count(*) as n by bin(5m)
```

Pick the `bin` so the window yields enough buckets to see the shape (for example `bin(1m)` for an hour, `bin(5m)` for a few hours, `bin(1h)` for a day).

### Error counts split before and after a timestamp

To test whether a deployment or change at a known time moved the error rate:

```
fields @timestamp
| filter level = "ERROR"
| stats count(*) as errors
    by (toMillis(@timestamp) < 1700000000000) as before_change
```

Replace the epoch-millis value with the change time. `before_change = 1` is the pre-change count, `0` the post-change count. Compare like with like: equal-length windows either side.

### Per-host or per-task breakdown

To find a single degraded fleet member when several share the work:

```
fields @timestamp, duration_ms
| filter ispresent(duration_ms)
| stats count(*) as n, pct(duration_ms, 99) as p99, avg(duration_ms) as avg
    by @logStream
| sort p99 desc
```

`@logStream` is one stream per instance, task or container in most setups; substitute a `host` or `task_id` field if the workload logs one. An outlier stream with a high p99 or a low count is the degraded member the aggregate hides.

### First-seen time of an error

To tell a new error from long-standing noise:

```
fields @timestamp, @message
| filter @message like /ConnectionTimeout/
| stats min(@timestamp) as first_seen, max(@timestamp) as last_seen, count(*) as n
```

If `first_seen` predates the incident window or the last deployment, the error is historical context, not a new defect.

## Statistics

### Percentiles, not averages

An average hides the tail users feel. Report p50, p90 and p99, and compare the same percentile across windows (p99 against p99, never a baseline p50 against an incident p99). A rising p99 at a flat p50 points to tail effects (cold starts, garbage collection, lock contention, a slow subset of keys), not a uniform slowdown. Never alarm on an average alone.

### Distribution shape and bimodal latency

Summary statistics hide the shape of the distribution. Latency is often bimodal: two populations with different behaviour, for example a fast warm path and a slow cold start, two request shapes of different size, or the hit and miss paths of a cache that exists in configuration or code. An average lands between the two modes and describes neither. Name a mode only from evidence: a log field whose name suggests a cache or a hit does not prove a cache exists (see `diagnosis-rules.md`, Caches and field names). Reveal it with a histogram of latency, or by reading several percentiles together (a large gap between p50 and p90, or p90 and p99, is a sign of a second mode). When two modes exist, report each and its share rather than one blended number.

### Trimmed mean as a complement to percentiles

A trimmed mean drops a fraction of the highest (and sometimes lowest) values before averaging, so a few extreme outliers do not drag it the way they drag a plain mean, while it still uses more of the data than a single percentile. Use it alongside percentiles, not instead of them. CloudWatch supports trimmed-mean statistics (`TM`, `TC`, `TS` and related); the exact definitions and syntax are to verify against the CloudWatch statistics definitions documentation page.

### Finding the outlier member (IQR and MAD)

To decide whether one member of a fleet is genuinely abnormal rather than just the worst of a normal spread, compare it with its peers using a robust rule, not a fixed threshold:

- **IQR.** Compute the first and third quartiles (Q1, Q3) of the per-member values; the interquartile range is `IQR = Q3 - Q1`. A member above `Q3 + 1.5 x IQR` (or below `Q1 - 1.5 x IQR`) is an outlier.
- **MAD.** Compute the median, then the median of the absolute deviations from it (MAD). A member whose deviation from the median is more than about 3 x MAD is an outlier.
- **Error share.** For errors, the top contributor's share of total errors shows when one member, caller or key dominates.

Both IQR and MAD use the median, so one bad member does not distort the baseline the way a mean would.

### Contributor Insights top-N

CloudWatch Contributor Insights ranks the top contributors to a log or metric dimension (the hottest key, the noisiest caller, the slowest host). Read a rule's report with `cloudwatch:GetInsightRuleReport`. A single contributor holding a large share of errors or requests is the degraded slice the aggregate hides.

### Metrics Insights GROUP BY example

CloudWatch Metrics Insights runs a SQL-like query over metrics; a `GROUP BY` returns one series per member so peers can be compared in a single call. For example, to compare 5xx counts per instance:

```
SELECT SUM("HTTPCode_Target_5XX_Count")
FROM "AWS/ApplicationELB"
GROUP BY "AvailabilityZone"
ORDER BY SUM() DESC
```

Substitute the namespace, metric and dimension for the breakdown you need (by `Operation`, by `InstanceId`, by `AvailabilityZone`). Confirm metric and dimension names against the service's CloudWatch documentation.

### Picking the period

Choose a period that gives roughly 100 to 1,440 points across the window: 60 s for a few hours, 300 s for a day, 3,600 s for 14 days. Too coarse a period smears a short spike into the baseline; too fine a period buries the trend in noise and costs more data points. The period must be the same on both sides of any before-and-after comparison.

### Compare like with like

Same statistic, same period, same log group or metric dimension, and matched request or arrival rate. Do not call traffic flat unless the rates being compared actually match; a lower-rate window will show lower latency for reasons that have nothing to do with the fault.

### Little's law and flow

Little's law links concurrency, rate and latency:

```
in-flight = arrival rate x average time in system
```

Use it two ways:

- **Request path.** A connection pool, thread pool or concurrency limit sitting at its maximum is often just `rate x latency` for a slow dependency, i.e. a consequence of the slow dependency, not an independent cause, unless it saturates before the dependency slows.
- **Queues and batch.** Backlog change rate = arrival rate - completion rate. A growing backlog means completion is below arrival; the gap, times the window, equals the backlog built up. Use this for the magnitude check: the throughput shortfall a cause predicts must match the measured backlog growth. If a capacity drop of ratio r should cut completion by r, the backlog should grow at `arrival - (1 - r) x prior_completion`; compare that with the observed slope.

## Windows and baselines

- **Investigation window.** From 1 hour before onset to now, plus the same window 7 days earlier as a baseline. **Review window.** The last 14 days.
- Keep the incident and baseline windows distinct and report their values separately; never report one average across both.
- A baseline is a stable period with real traffic before the fault. If the resource is too new for a 7-days-earlier baseline, use the quietest stable in-window period with real traffic before onset and say so; if none exists, say so.
- If the rate, the request shape or the configuration changed inside the history, split it into regimes and re-baseline on the current one (see `diagnosis-rules.md`, Baselines and regime changes).
- **Time-of-day complaints.** Compare the same hours across at least two days, and quiet hours against busy hours on the same day. State the rate, the request shape and the same percentiles for each period. A diurnal pattern that tracks load is a capacity or scaling finding, not a regression.
- Label one-minute spikes that coincide with a deployment, a scaling event or a configuration change as transients and report the sustained in-window peak instead.
- **Baseline record.** Workload profile and rate, p50, p90 and p99, error rate, utilization, and the environment (instance types, sizes, memory, key configuration), so a later change can be measured against it.

## Targets, SLOs and error budgets

An SLI is the measured number (p99 latency, error rate); an SLO is the internal target for it; an SLA is the external promise. Keep the SLO tighter than any SLA. Where an objective exists, derive the error budget (100% minus the SLO target) and the burn rate (how fast the budget is being spent); a rising burn rate is the signal to act. If an Application Signals SLO exists, report its attainment and burn rate. When an end-to-end target exists, give each hop a latency budget share so an over-budget hop stands out. Without a target, use the baseline and say that no objective was defined.

## Reading the four signals together

Latency percentiles, throughput, error rate and utilization are four views of one system; read them on the same window. Throughput up at flat latency means the tier scaled; throughput and latency both up means it is saturated; error rate often moves minutes before latency. Use RED to find the slow hop and USE to find why.

## RED for async and batch workloads

- **Rate (arrival).** SQS `NumberOfMessagesSent`, stream `IncomingRecords`, or the producer's own count.
- **Rate (completion).** SQS `NumberOfMessagesDeleted`, or a custom processed count.
- **Backlog and lag.** `ApproximateNumberOfMessagesVisible` and `ApproximateAgeOfOldestMessage` for queues; `GetRecords.IteratorAge` or Lambda `IteratorAge` for streams.
- **Duration.** Per-message or per-job time from logs (patterns above) or a custom metric.
- **Per-consumer breakdown.** When several consumers share one queue, break throughput and duration down per member; one slow member can grow the backlog while the fleet looks busy.
- **Recovery.** Catch-up rate = completion rate - arrival rate; time to drain = backlog / catch-up rate.
