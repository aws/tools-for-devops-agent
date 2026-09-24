# Amazon Data Firehose CloudWatch Metrics Thresholds Reference

Metrics are retrieved via `cloudwatch.GetMetricData` over the selected window
(default 7 days). All Firehose metrics use the namespace `AWS/Firehose` and the
dimension `DeliveryStreamName`. Firehose publishes metrics at 1-minute granularity.
Severity reflects sustained values, not single spikes. `cloudwatch.GetMetricData`
allows up to 500 metric-data queries per call — batch and paginate for accounts with
many streams.

`<Dest>` is the destination token, one of: `S3`, `Redshift`,
`AmazonOpenSearchService`, `AmazonOpenSearchServerless`, `Splunk`, `HttpEndpoint`,
`Snowflake`. Select the delivery metric set that matches each stream's configured
destination.

## Ingestion Metrics (all streams)

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| IncomingRecords | Sum | baseline | — | — | Volume; denominator for rate calcs (excludes throttled) |
| IncomingBytes | Sum | baseline | — | — | Byte volume; excludes throttled |
| IncomingPutRequests | Sum | baseline | — | — | Direct PUT request volume |
| ThrottledRecords | Sum | 0 | throttle rate > 1% † | throttle rate > 5% † (esp. sustained near limit) | Request quota increase; add producer backoff |
| RecordsPerSecondLimit | Max | headroom | observed P95 > 75% † | observed P95 near 100% | Per-stream record limit — compare to observed rate |
| BytesPerSecondLimit | Max | headroom | observed P95 > 75% † | observed P95 near 100% | Per-stream byte limit |
| PutRequestsPerSecondLimit | Max | headroom | observed P95 > 75% † | observed P95 near 100% | Per-stream PUT-request limit |

**Throttle rate** = `ThrottledRecords / (IncomingRecords + ThrottledRecords)`
(throttled data is excluded from `IncomingRecords`).

> **† Heuristic thresholds, not AWS-published numbers.** AWS
> [recommends alarming](https://docs.aws.amazon.com/firehose/latest/dev/firehose-cloudwatch-metrics-best-practices.html)
> on `ThrottledRecords` and on `IncomingX (Sum per 5 min) / 300` approaching a
> *percentage* of the matching `*PerSecondLimit`, but does not specify the
> percentage. The 1% / 5% / 75% figures here are this skill's calibration for
> prioritization — treat them as tunable defaults, not official AWS thresholds.

> **`*PerSecondLimit` may return no datapoints.** A brand-new stream, or one with no
> traffic in the window, may not emit `RecordsPerSecondLimit` / `BytesPerSecondLimit`
> / `PutRequestsPerSecondLimit`. If a limit metric has no datapoints, do **not** report
> 0% utilization — report "limits could not be retrieved for this window" so an idle or
> new stream isn't mistaken for one with infinite headroom.

## Source-Specific Ingestion Metrics

### Kinesis Data Streams source

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| KinesisMillisBehindLatest | Max | near 0 | rising / minutes behind | large & growing | Firehose falling behind source; check source throttling |
| DataReadFromKinesisStream.Records / .Bytes | Sum | baseline | — | — | Source read volume (includes failover rereads) |
| ThrottledGetRecords | Sum | 0 | any recurring (> 0 in ≥ 25% of 1-min periods) | frequent (> 0 in ≥ 50% of periods, or rising trend) | Source stream throttling reads — reshard or reduce consumers |
| ThrottledGetShardIterator / ThrottledDescribeStream | Sum | 0 | any recurring (> 0 in ≥ 25% of periods) | frequent (≥ 50% of periods, or rising) | Source-side API throttling |

### MSK source

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| KafkaOffsetLag | Max | near 0 | rising | large & growing | Firehose behind the source topic |
| DataReadFromSource.Backpressured | Max | 0 (false) | — | 1 (true) sustained | Per-partition limit hit or delivery slow/stopped |
| DataReadFromSource.Records / .Bytes | Sum | baseline | — | — | Source read volume |
| SourceThrottled.Delay | Average | low | rising | high | Source Kafka delay returning records |

## Delivery Metrics (per destination)

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| DeliveryTo`<Dest>`.Success | Average | ~1.0 | < 1.0 (retries) | well below 1.0 with no S3 backup | Investigate destination errors; enable S3 backup |
| DeliveryTo`<Dest>`.DataFreshness | Max | < buffering interval | > interval + partial retry window | climbing monotonically (stalled) | Delivery lag / stall — top Firehose health signal |
| DeliveryTo`<Dest>`.Records / .Bytes | Sum | baseline | — | — | Delivered volume |
| DeliveryToSplunk.DataAckLatency | Average | stable | rising trend | sustained high | Slow Splunk indexers; scale HEC/indexers |
| DeliveryToSnowflake.DataCommitLatency | Average | low | rising | high | Snowflake commit latency after insert |
| DeliveryToAmazonOpenSearchService`[Serverless]`.AuthFailure | Max | 0 | — | 1 | Auth/authz error to the OpenSearch domain/collection — check cluster policy + role |
| DeliveryToAmazonOpenSearchService`[Serverless]`.DeliveryRejected | Max | 0 | — | 1 | Delivery rejected by OpenSearch — check cluster policy + role |

**Data freshness guidance:** compare `DataFreshness` (Max) against the stream's
configured buffering `IntervalInSeconds` plus its destination `RetryOptions`
duration. Freshness comfortably below the buffering interval is healthy; freshness
above interval + retry window means records are aging and at risk; a monotonically
rising freshness curve means delivery has stalled (CRITICAL).

**OpenSearch Service vs. Serverless:** both destinations emit the **same**
`DeliveryToAmazonOpenSearchService.*` / `DeliveryToAmazonOpenSearchServerless.*`
metric family (`.Bytes`, `.DataFreshness`, `.Records`, `.Success`) plus the
`.AuthFailure` / `.DeliveryRejected` signals above. There are **no OCU- or
capacity-specific metrics in `AWS/Firehose`** — OpenSearch Serverless OCU capacity
and indexing health are visible only on the OpenSearch (`AWS/AOSS`) side, not through
Firehose. Assess Firehose delivery health here; direct capacity questions to
OpenSearch monitoring.

**Snowflake — CloudWatch is not the whole picture.** `AWS/Firehose` surfaces only
Firehose's view of Snowflake delivery: `DeliveryToSnowflake.Success` (insert-call
success ratio), `.Records`/`.Bytes`, `.DataFreshness`, and `.DataCommitLatency`. A
successful Firehose insert call does **not** guarantee the row committed cleanly on
the Snowflake side — Snowflake-side errors, ingestion-queue backlog, and pipe/warehouse
issues do **not** appear in `AWS/Firehose` at all. For Snowflake destinations, treat
CloudWatch as necessary-but-not-sufficient: **N/A — check Snowflake-side monitoring**
(Snowpipe Streaming / `COPY_HISTORY` / account usage views) for delivery correctness
beyond what Firehose reports.

**Iceberg — delivery metrics don't prove landing.** For Apache Iceberg destinations,
`DeliveryToIceberg.Bytes`/`.Records` reflect Firehose's delivery attempt, not confirmed
rows in the table. Firehose requires **one JSON object per record**; aggregated or
compressed source records (e.g. gzipped multi-event payloads from a CloudWatch Logs
subscription filter, or KPL-aggregated records) may not land as expected, and the S3
error prefix is not a guaranteed catch-all for every such case. Treat Iceberg delivery
like Snowflake: **N/A — verify at the destination.** Reconcile ingested count
(`IncomingRecords`) against actual Iceberg table row count, and ensure records are
decompressed/split to one JSON object per record upstream (e.g. in the transform Lambda).

## Backup-to-S3 Metrics (when backup enabled)

Interpretation depends on the backup mode. On `AllData` streams, non-zero
`BackupToS3.Records` is **expected** (every record is backed up) and is
informational. On `FailedDataOnly` streams, non-zero `BackupToS3.Records` means the
primary destination rejected records — that is the signal that matters.

| Metric | Stat | Normal | Warning | Critical | Finding |
|---|---|---|---|---|---|
| BackupToS3.Success | Average | ~1.0 | < 1.0 | well below 1.0 | Fallback-put failures — backup bucket/permissions issue (data at risk of loss) |
| BackupToS3.Records / .Bytes | Sum | 0 on `FailedDataOnly`; baseline on `AllData` | `FailedDataOnly`: > 0 (any) | `FailedDataOnly`: sustained/rising > 0 | Primary destination rejecting records — correlate with `DeliveryTo<Dest>.Success`. On `AllData`: informational only |
| BackupToS3.DataFreshness | Max | < buffering interval | > interval + retry window | climbing monotonically | Backup path itself lagging |

## Feature Metrics (only when the feature is enabled)

### Data transformation (Lambda)

| Metric | Stat | Normal | Warning | Finding |
|---|---|---|---|---|
| ExecuteProcessing.Success | Average | ~1.0 | < 1.0 | Failed transforms routed to S3 error prefix; ensure backup |
| ExecuteProcessing.Duration | Average, Max | well under timeout | approaching Lambda timeout | Optimize transform or raise timeout |
| SucceedProcessing.Records / .Bytes | Sum | baseline | — | Successfully transformed volume |

### Format conversion (Parquet/ORC)

| Metric | Stat | Normal | Warning | Finding |
|---|---|---|---|---|
| SucceedConversion.Records / .Bytes | Sum | baseline | — | Successfully converted volume |
| FailedConversion.Records / .Bytes | Sum | 0 | > 0 | Records failing schema conversion go to S3 error prefix |

### Dynamic partitioning

| Metric | Stat | Normal | Warning | Finding |
|---|---|---|---|---|
| PartitionCount | Max | < limit | approaching ActivePartitionsLimit | Records over limit go to error bucket |
| PartitionCountExceeded | Max | 0 | 1 | Active-partition limit breached (default 500) |
| ActivePartitionsLimit | Max | 500 (default) | — | The current limit — request increase if breached |
| PerPartitionThroughput | Average | at/near the destination buffer size before flush | many partitions averaging < ~25% of the configured buffer size (flushing on the time interval, not size) | Fragmented tiny partitions → cost/perf issue. Anchor: `avg bytes per partition per buffer interval = IncomingBytes / PartitionCount / (window / IntervalInSeconds)`; well below the buffer `SizeInMBs` means partitions flush half-empty on the timer |
| DeliveryToS3.ObjectCount | Sum | ≈ `PartitionCount × (window / IntervalInSeconds)` | ObjectCount much higher than `DeliveryToS3.Bytes / buffer SizeInMBs` (objects far smaller than the buffer target) | Many small objects → higher S3 PUT cost + slower queries |

### Server-Side Encryption (SSE)

| Metric | Stat | Threshold | Finding |
|---|---|---|---|
| KMSKeyAccessDenied | Sum | > 0 → CRITICAL | Delivery role lacks KMS permission; records not encrypted/delivered |
| KMSKeyDisabled | Sum | > 0 → CRITICAL | KMS key disabled — active delivery failure |
| KMSKeyInvalidState | Sum | > 0 → CRITICAL | KMS key in invalid state |
| KMSKeyNotFound | Sum | > 0 → CRITICAL | KMS key deleted/missing |

### CloudWatch Logs decompression

| Metric | Stat | Threshold | Finding |
|---|---|---|---|
| OutputDecompressedRecords.Failed | Sum | > 0 | Decompression failures for CloudWatch Logs delivery |
| OutputDecompressedBytes.Failed | Sum | > 0 | Failed decompressed byte volume |

## Service Quota Utilization

| Quota | Source | Warning | Critical | Finding |
|---|---|---|---|---|
| Delivery streams per Region (default 50) | `servicequotas.GetServiceQuota` vs stream count | > 75% | near 100% | Request increase before `LimitExceededException` on create |
| Per-stream records/s (Direct PUT, default 5,000) | `RecordsPerSecondLimit` vs observed P95 | > 75% | near 100% + `ThrottledRecords` > 0 | Request increase; the three PUT limits scale proportionally |
| Per-stream bytes/s (Direct PUT, region-dependent, ~5 MB/s) | `BytesPerSecondLimit` vs observed P95 | > 75% | near 100% + throttling | Request increase |
| Per-stream PUT requests/s (Direct PUT, default 2,000) | `PutRequestsPerSecondLimit` vs observed P95 | > 75% | near 100% + throttling | Batch with `PutRecordBatch`; request increase |
| Iceberg-table throughput (call `GetServiceQuota`; cite returned value — see note) | observed bytes/s vs the per-stream Iceberg limit from `GetServiceQuota` | > 75% | near limit | Request increase, set `AppendOnly=True` for insert-only, or split load |

> Direct PUT throughput defaults vary by Region and the three limits scale
> proportionally. Read the actual limit from the `*PerSecondLimit` CloudWatch metrics
> rather than assuming fixed values.
>
> The Iceberg-table per-stream throughput limit is lower than other destinations, varies
> by Region, and changes over time. **Do NOT state a reference number** — call
> `servicequotas.GetServiceQuota` and cite the value it returns, cross-checking the
> [Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html) and
> [Iceberg considerations](https://docs.aws.amazon.com/firehose/latest/dev/apache-iceberg-considerations.html)
> docs. `AppendOnly=True` streams auto-scale and Firehose auto-increases throttled streams,
> so confirm the effective limit before flagging. Note the Iceberg
> throughput-vs-active-partitions tradeoff (higher ingest reduces max active partitions).

## Derived / tunable thresholds

Single-sourced here so SKILL.md stays procedural — tune these in one place and both
SKILL.md and the checklist inherit the change.

| Threshold | Value | Used by |
|---|---|---|
| Quota-utilization Warning band | > 75% of applied quota | Service Quotas pillar (streams-per-Region, per-stream throughput); also the "approaching the limit" band for Iceberg throughput |
| Quota-utilization Critical band | ≥ 90% of applied quota, sustained (see "sustained" below) | Service Quotas pillar |
| Idle-stream minimum age | `CreateTimestamp` age > ~14 days | Cost Optimization / Sustainability idle-stream check — below this age report "recently created — insufficient history," never "idle" |
| Throttle-rate Warning / Critical | > 1% / > 5% † | Ingestion `ThrottledRecords` |
| **"Sustained"** (default definition) | a condition true in **≥ 3 consecutive datapoints** at the metric's native period (1-min for most `AWS/Firehose` metrics; 5-min where aggregated) — i.e. not a single spike | Data freshness, throttling, delivery-success, quota-Critical, and any check that says "sustained" |
| **"Climbing monotonically" / stalled** | `DataFreshness` (Max) **non-decreasing across ≥ 6 consecutive 5-min datapoints (~30 min)** with no return toward the buffering interval | Reliability data-freshness "delivery stalled → CRITICAL" |
| **"Majority of streams"** (account rollup) | **≥ 60%** of the in-scope streams share the same finding class → treat as a systemic/account-level item | Step 5 account-level rollup |
| **"Large" waste** (Sustainability/Cost escalation) | an opportunity whose estimated monthly impact is **≥ 25%** of the stream's estimated monthly delivered-storage cost, **or** ≥ 100 GB/month of avoidable stored volume — above this, raise severity one level (INFO→LOW, LOW→MEDIUM) | Sustainability 4.7, Cost 4.5 |

† Heuristic, not an AWS-published number — see the ingestion-metrics footnote earlier in this file.
All rows in this table are skill heuristics for consistency, not AWS-published SLAs — tune per environment, but apply them uniformly within a review so two runs agree.
