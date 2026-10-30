# Metrics and Thresholds — Amazon CloudFront Operational Review

The single source for metric names, dimensions, statistics and bands used in Pass 2. Source:
[Types of metrics for CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/programming-cloudwatch-metrics.html).

## Query rules

- Region: **`us-east-1`** for every CloudFront metric.
- Namespace: `AWS/CloudFront`.
- Dimensions: **both** `DistributionId=<id>` **and** `Region=Global`. Omitting `Region=Global`
  returns no data. That is a query error, not a "no traffic" finding.
- Window: 7 days. Period: 3,600 s (168 datapoints per query). Batch up to 500 queries per
  `GetMetricData` call.

## Metric catalog

| Metric | Statistic | Unit | Availability |
|---|---|---|---|
| `Requests` | Sum | count | Default (free) |
| `BytesDownloaded` | Sum | bytes | Default |
| `BytesUploaded` | Sum | bytes | Default |
| `4xxErrorRate` | Average | percent | Default |
| `5xxErrorRate` | Average | percent | Default |
| `TotalErrorRate` | Average | percent | Default |
| `CacheHitRate` | Average | percent | **Additional metrics only** |
| `OriginLatency` | **Percentile** (use `p90`) | milliseconds | **Additional metrics only** |
| `401ErrorRate`, `403ErrorRate`, `404ErrorRate`, `502ErrorRate`, `503ErrorRate`, `504ErrorRate` | Average | percent | **Additional metrics only** |

Each metric supports only the statistic listed. `OriginLatency` takes a percentile
statistic. Do not request Average for it.

Additional metrics exist only when the distribution's monitoring subscription is `Enabled`
(SKILL.md Step 4). When it is not, the dependent checks are "not evaluated — additional
metrics not enabled". Never treat the absence as 0 %.

## Aggregating the window

- **Rates** (`*ErrorRate`, `CacheHitRate`): compute the **request-weighted** window value,
  `Σ(rate_h × Requests_h) ÷ Σ Requests_h`, so idle hours do not dilute busy ones. Also
  report the worst single hour.
- **OriginLatency:** report the median of hourly p90 values, plus the worst hour.
- **Low-traffic floor:** if `Requests` over the window is below 1,000, report rates as INFO
  ("too few requests for a stable rate") rather than applying the bands.
- **No `Requests` datapoints at all:** the distribution served no traffic in the window.
  Report INFO, and skip every rate check.

## Bands

| Check | Metric | Warning | Fail |
|---|---|---|---|
| REL-05 | `5xxErrorRate` (window) | > 0.5 % → MEDIUM | > 1 % → HIGH |
| REL-06 | `4xxErrorRate` (window) | — | > 10 % → MEDIUM |
| PERF-01 (static only) | `CacheHitRate` (window) | < 80 % → MEDIUM | < 60 % → HIGH |
| PERF-04 | `OriginLatency` p90 (median hour) | > 500 ms → MEDIUM | > 2,000 ms → HIGH |

Also check the worst hour. If it crosses a Fail band while the window value does not, add
an INFO note with the timestamp. Do not raise the severity.

## Alarm coverage match (OPS-02)

From `cloudwatch.DescribeAlarms` in us-east-1, an alarm covers the distribution when
`Namespace == AWS/CloudFront`, `MetricName` is `5xxErrorRate` or `TotalErrorRate` (or, for
the INFO note, `CacheHitRate` / `OriginLatency`), and `Dimensions` include
`DistributionId=<id>`. Accept metric-math alarms whose `Metrics[]` reference the same. An
alarm in `INSUFFICIENT_DATA` counts as coverage, but note its state.

## Response headers thresholds (SEC-14)

| Header | Field | Threshold |
|---|---|---|
| HSTS | `StrictTransportSecurity.AccessControlMaxAgeSec` | ≥ 31,536,000 s (one year) |

## Cost Explorer query (COST-06)

`ce.GetCostAndUsage`: `TimePeriod` = last 3 full months, `Granularity=MONTHLY`,
`Metrics=["UnblendedCost"]`, `Filter` on `SERVICE = "Amazon CloudFront"`,
`GroupBy=[{"Type":"DIMENSION","Key":"USAGE_TYPE"}]`. Label every figure "from Cost
Explorer, unblended". Cost Explorer reflects the account's billing view and can be empty
from a linked account.
