# CloudFront CloudWatch Metrics Thresholds Reference

All metrics retrieved via a single `cloudwatch.GetMetricData` call per distribution over a
7-day window with `Period=21600` (6h), in **`us-east-1`** (CloudFront metrics are global and
live in us-east-1). Severity reflects sustained values, not single spikes.

## Default Metrics (Namespace `AWS/CloudFront`, dimensions `DistributionId` + `Region=Global`)

Always available for every distribution at no additional charge.

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| Requests | Sum | traffic baseline | — | ≈ 0 on an enabled dist | Idle distribution — candidate to disable/delete |
| BytesDownloaded | Sum | traffic baseline | — | — | Data-transfer cost driver; compare to cache hit ratio |
| BytesUploaded | Sum | traffic baseline | — | — | Upload-heavy patterns; validate methods allowed |
| 4xxErrorRate | Average | < 1% | > 2% | > 10% | Client errors — check auth, signed URLs, 403/404 causes |
| 5xxErrorRate | Average | < 0.5% | > 1% | > 5% | Origin/edge failures — investigate origin health & failover |
| TotalErrorRate | Average | < 1% | > 3% | > 10% | Overall error budget breach |

## Additional Metrics (require a monitoring subscription; dimensions `DistributionId` + `Region=Global`)

Only populated when `cloudfront.GetMonitoringSubscription` shows additional metrics enabled
(these incur CloudWatch charges). If disabled, record that as an Operational Excellence
finding, skip every row below, and approximate cache hit ratio from logs (see Notes).

`OriginLatency` supports only percentile statistics — request `p95` in `GetMetricData`
(`ExtendedStatistics` in `GetMetricStatistics`) and label the value "p95". The thresholds
below are calibrated to p95, are heuristic starting points, and should be tuned to the
origin's expected latency (for example, a dynamic API origin versus a static S3 origin).

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| CacheHitRate | Average | > 95% | < 90% | < 80% | Low cache efficiency — review cache policy TTLs & cache key |
| OriginLatency | p95 (percentile only) | < 250 ms | > 500 ms | > 1500 ms | Slow origin at the tail — check origin scaling, Origin Shield, origin region |
| 401ErrorRate | Average | ≈ 0 | > 1% | > 5% | Auth failures at viewer |
| 403ErrorRate | Average | < 1% | > 2% | > 10% | Access denied — OAC/OAI, signed URL, WAF blocks, S3 perms |
| 404ErrorRate | Average | < 2% | > 5% | > 15% | Missing objects — default root object, routing, cache key |
| 502ErrorRate | Average | ≈ 0 | > 0.5% | > 2% | Bad gateway — origin TLS/protocol mismatch |
| 503ErrorRate | Average | ≈ 0 | > 0.5% | > 2% | Origin overloaded / capacity exceeded |
| 504ErrorRate | Average | ≈ 0 | > 0.5% | > 2% | Origin timeout / connection failure (NonS3OriginCommError) |

## 504 / Origin-Connection Failure Triage (map metric spikes to root cause)

| Symptom | Likely root cause | Where to confirm |
|---|---|---|
| 504 + high OriginLatency | Origin slower than `OriginReadTimeout` | Origin app latency, raise timeout or scale origin |
| 504 + connection refused/closed in logs | Origin down or security group blocks CloudFront | Origin health, SG ingress, VPC origin backing target |
| 502 + TLS/handshake errors | Origin cert expired or `OriginSslProtocols` mismatch | Origin cert, `OriginProtocolPolicy`, SSL protocols |
| 503 sustained | Origin capacity exceeded | Origin autoscaling, Origin Shield to absorb load |

## Standard Access Log Signals (7-day scan)

| Field / value | Severity if prevalent | Action |
|---|---|---|
| `x-edge-result-type = Error` | HIGH | Correlate with 5xx metric and origin logs |
| `x-edge-result-type = Miss` (high ratio) | MEDIUM | Improve cacheability (TTL, cache key) |
| `sc-status` 502/503/504 | HIGH | Origin failover / timeout / capacity review |
| `x-edge-result-type = OriginShieldHit` present | INFO | Origin Shield working as intended |
| `ssl-protocol = TLSv1 / TLSv1.1` | MEDIUM | Deprecated viewer TLS — raise `MinimumProtocolVersion` |

## Alarm Coverage Expectations

Collect alarms with `cloudwatch.DescribeAlarms` in `us-east-1` (`AlarmTypes` =
`MetricAlarm`, `CompositeAlarm`; paginate). A metric counts as covered for a distribution when
any of these references namespace `AWS/CloudFront` with that `DistributionId`:

- a metric alarm's `MetricName` + `Dimensions`;
- any `Metrics[].MetricStat.Metric` inside a metric-math alarm;
- a composite alarm whose `AlarmRule` names one of the alarms above.

`DescribeAlarmsForMetric` returns only standard single-metric alarms and omits metric-math and
composite alarms, so an empty result from it does not prove a gap. If you could only use
`DescribeAlarmsForMetric`, label the finding "limited to direct single-metric alarms".

Flag a missing alarm as **MEDIUM**:

| Metric | Threshold (suggested) | Applies when |
|---|---|---|
| 5xxErrorRate | > 1% for 5 minutes | always |
| TotalErrorRate | > 3% for 5 minutes | always |
| OriginLatency (p95) | > 1500 ms for 5 minutes | additional metrics enabled |
| CacheHitRate | < 80% for 15 minutes | additional metrics enabled |

When additional metrics are disabled, do not flag or recommend OriginLatency or CacheHitRate
alarms; recommend enabling additional metrics first if the workload needs them.

## Notes

- Log-derived cache hit ratio approximates `CacheHitRate`, which counts only cacheable
  requests (POST, PUT, and errors are excluded). Filter first: keep rows whose `cs-method` is
  GET, HEAD, or OPTIONS and whose `x-edge-result-type` is not `Error`. Then compute
  `(Hit + RefreshHit) / (Hit + RefreshHit + Miss)`. Label the result "log-derived (approx.)";
  it is not directly comparable to the CloudWatch metric.
- Error-rate metrics are percentages of total requests, already averaged by CloudFront — use
  `Average` stat, not `Sum`.
- Zero-traffic windows can make error-rate `Average` misleading; always read error rates
  alongside `Requests`.
