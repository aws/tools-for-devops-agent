# Lambda CloudWatch Metrics Thresholds Reference

All metrics retrieved via `cloudwatch.GetMetricData` over a 14-day window with
`Period=3600` (1h), Namespace `AWS/Lambda`, Dimension `FunctionName`. Severity
reflects sustained values over the window, not single spikes.

> **Rate math:** error rate = `Errors / Invocations`; throttle rate =
> `Throttles / (Invocations + Throttles)`. Compute over the same period.

## Core Function Metrics

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| Errors | Sum → rate | < 0.1% | > 1% | > 5% | Elevated errors — investigate logs |
| Throttles | Sum | 0 | > 0 sustained | > 1% of invokes | Concurrency limit hit — raise reserved/account concurrency |
| Duration | p95 | < 60% of timeout | > 80% of timeout | ~ timeout | Approaching timeout — optimize or raise timeout |
| Duration | Average | stable | rising trend | — | Regression — correlate with a deploy |
| InitDuration | p95 | low / rare | high & frequent | dominates latency | Cold-start pain — provisioned concurrency / SnapStart / lighter init |
| ConcurrentExecutions | Maximum | < 70% limit | > 80% limit | > 95% limit | Concurrency saturation — quota increase |
| DeadLetterErrors | Sum | 0 | > 0 | growing | Async failures not reaching DLQ |
| DestinationDeliveryFailures | Sum | 0 | > 0 | growing | On-failure/on-success destination delivery failing |
| IteratorAge (Kinesis/DDB streams) | Maximum | < 60s | > 60s | > 300s | Consumer falling behind — scale or optimize |
| OversizedRecordCount / FilteredOutRecordCount | Sum | context | > 0 | — | Event filtering / record-size issues |

## Provisioned Concurrency Metrics

| Metric | Stat | Warning | Critical | Finding |
|---|---|---|---|---|
| ProvisionedConcurrencyUtilization | Average | < 30% | < 10% sustained | Idle warm capacity — reduce provisioned concurrency |
| ProvisionedConcurrencySpilloverInvocations | Sum | > 0 | sustained | Spilling to on-demand (cold starts) — raise provisioned level |
| ProvisionedConcurrencyInvocations vs Invocations | ratio | low | — | Most traffic bypasses warm pool — re-check need |

## Account-Level (Namespace `AWS/Lambda`, no dimension / `GetAccountSettings`)

| Signal | Warning | Critical | Finding |
|---|---|---|---|
| `AccountUsage.FunctionCount` vs limits | approaching | at limit | Request quota increase |
| `ConcurrentExecutions` (account) vs `AccountLimit.ConcurrentExecutions` | > 80% | > 95% | Regional concurrency near limit — request increase |
| UnreservedConcurrentExecutions | < 100 | near 0 | Reserved concurrency consuming the pool; unreserved functions may throttle |

## Alarm Coverage Expectations

Flag as **MEDIUM** when missing (`cloudwatch.DescribeAlarmsForMetric` returns
nothing for the function + metric):

| Metric | Threshold (suggested) |
|---|---|
| Errors | error rate > 1% for 5 minutes |
| Throttles | Throttles >= 1 for 2 datapoints |
| Duration | p95 > 80% of configured timeout |
| DeadLetterErrors | >= 1 |
| ConcurrentExecutions | > 80% of the applicable limit |
| IteratorAge (stream sources) | > 60000 ms |

## Right-Sizing Heuristic (memory vs duration)

`Duration` (and cost = memory-GB × duration-seconds × price) as memory is varied
typically forms a curve: below a point the function is CPU-starved and slow;
above the "knee" duration flattens while cost keeps rising.

| Observation | Recommendation |
|---|---|
| Duration high and flat at low memory; CPU-bound work | Increase memory — often lowers duration enough to be cost-neutral or cheaper |
| Duration flat above a memory level; `MaxMemoryUsed` well below allocated | Lower memory toward the knee |
| Bursty latency-sensitive path with frequent `InitDuration` | Provisioned concurrency or SnapStart, then re-measure |

> For a rigorous sweep, recommend the operator run AWS Lambda Power Tuning in a
> non-production environment. This skill estimates from observed metrics only and
> never invokes the function.
