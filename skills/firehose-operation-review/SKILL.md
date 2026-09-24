---
name: firehose-operation-review
description: 'Comprehensive Amazon Data Firehose (formerly Kinesis Data Firehose) review aligned with the AWS Well-Architected Framework and Firehose best practices. Use this skill when a user asks to review, audit, or assess Amazon Data Firehose delivery streams for best-practices compliance, security posture, reliability, delivery health, performance, cost optimization, service quotas, operational excellence, or sustainability. Triggers on requests like "Firehose review", "Kinesis Firehose best practices audit", "review my delivery streams", "Firehose health check", "why is my Firehose lagging", "Firehose delivery failures", "Firehose cost optimization review", or "ORR for Firehose".'
metadata:
  author: stharolz
  version: "1.2.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon Data Firehose"
  aws-devops-agent-skills.technical-domains: "Analytics, Streaming Data"
---

# Amazon Data Firehose Operational Review

Conduct a comprehensive operational review of Amazon Data Firehose (formerly Amazon
Kinesis Data Firehose) delivery streams aligned with the
[AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
and [Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html)
best practices.

This skill uses the **Firehose, CloudWatch, and Service Quotas APIs only** — all data
is collected through native AWS control-plane APIs and CloudWatch metrics. It performs
no data-plane record puts and reads no delivered record content.

## When to Use

Activate this skill when the user asks to:
- Review, audit, or assess Amazon Data Firehose delivery streams
- Check Firehose best-practices compliance
- Evaluate Firehose security, reliability, delivery health, performance, cost, or quotas
- Perform a Firehose operational readiness review (ORR)
- Investigate delivery lag (data freshness), delivery failures, throttling, or cost drivers

## Step 1: Identify Target Scope

Ask the user which accounts and regions to review, and whether to focus on a specific
delivery stream. Accept:
- Specific account IDs and regions
- A specific delivery stream name (or "all streams")
- "all regions" for a given account
- A specific pillar or set of checks (e.g. "just reliability and cost"). Map free-text
  pillar names to this **canonical set** (accept the listed aliases, case-insensitive):
  `security`; `reliability` (aliases: resiliency, availability, durability);
  `performance` (perf); `service-quotas` (quotas, limits); `cost` (cost-optimization,
  cost optimization, finops); `operational-excellence` (ops, opex, operations);
  `sustainability` (green, efficiency). If a requested term matches none of these, ask the
  user to pick from the canonical list rather than guessing; if the run is unattended,
  default to all pillars.

If no scope is given, default to all configured account regions, all delivery streams,
and all pillars. Default the analysis window to the last 7 days unless the user
specifies a range (historical windows older than ~2 weeks may have reduced CloudWatch
resolution).

**Unattended / scheduled runs.** If the skill is invoked without an interactive user
turn — e.g. as a scheduled custom agent or an automated evaluation task — do **not** wait
for scope input. Proceed immediately with the full default scope: all configured accounts
and regions, all delivery streams, all seven pillars, and a 7-day window. Only pause to
ask for scope when there is an interactive user to answer.

## Step 2: Discover Firehose Resources

**Account scoping.** This skill operates within the accounts the DevOps Agent Space is
configured to access — it does not assume roles or enumerate an Organization itself.
"All accounts" means the accounts already associated with the Agent Space as cloud
sources; the agent invokes the read APIs below in each in-scope account/region using the
Space's configured access. If a requested account is not associated with the Space,
report it as "not accessible from this Agent Space" rather than attempting to assume into
it. Iterate account × region across the resolved scope.

Per account/region, list the delivery streams and describe each one:

```
firehose.ListDeliveryStreams                   # enumerate streams in the region
firehose.DescribeDeliveryStream                 # full config for each stream
firehose.ListTagsForDeliveryStream              # tags (cost allocation, ownership)
```

**If `ListDeliveryStreams` returns no streams for a region, record "No Firehose
delivery streams in this region — skipping analysis" and move on. Do not generate
empty findings tables for regions with no streams.**

From `DescribeDeliveryStream`, capture per stream:
- **Stream type / source**: `DirectPut`, `KinesisStreamAsSource` (with the source
  Kinesis stream ARN), or MSK as source. This determines which ingestion metrics and
  quotas apply.
- **Destination**: S3 / Extended S3, Redshift, OpenSearch Service, OpenSearch
  Serverless, Splunk, HTTP endpoint, Snowflake, or Apache Iceberg tables. A stream has
  exactly one active destination.
- **Buffering hints**: `SizeInMBs` and `IntervalInSeconds` for the destination.
- **Compression**: `CompressionFormat` (UNCOMPRESSED, GZIP, Snappy, Zip, HADOOP_SNAPPY).
- **Encryption at rest**: server-side encryption (`DeliveryStreamEncryptionConfiguration`)
  — `AWS_OWNED_CMK` vs `CUSTOMER_MANAGED_CMK` — and destination S3 `EncryptionConfiguration`
  (KMS key).
- **Error/backup config**: `S3BackupMode` (`FailedDataOnly` / `AllData` / `Disabled`),
  the backup S3 bucket, and destination `RetryOptions.DurationInSeconds`.
- **Data transformation**: `ProcessingConfiguration` — whether a Lambda transform is
  enabled and its ARN (do NOT read the Lambda's code or invoke it).
- **Format conversion**: `DataFormatConversionConfiguration` (Parquet/ORC) for S3
  destinations.
- **Dynamic partitioning**: enabled/disabled and the partitioning config.
- **CloudWatch error logging**: `CloudWatchLoggingOptions.Enabled`.
- **VPC configuration**: `VpcConfiguration` for OpenSearch/Redshift destinations.
- **Cross-account / PrivateLink destinations**: for OpenSearch, Redshift, and HTTP-endpoint
  destinations, note whether the destination ARN/endpoint is in a different account or
  reached through a VPC/PrivateLink endpoint versus the public internet — this feeds the
  Security and Reliability checks.
- **Timestamps and status**: `CreateTimestamp`, `LastUpdateTimestamp`, and
  `DeliveryStreamStatus`.

**Guard on stream status.** Only run the full metric-and-pillar analysis on streams in
`ACTIVE` status. For a stream in `CREATING`, `CREATING_FAILED`, or `DELETING` state,
record its status and skip the CloudWatch/pillar analysis — these streams have partial
or no metrics, and analyzing them produces misleading "0 IncomingRecords" findings. For
`CREATING_FAILED`, surface the failure itself as a HIGH reliability finding.

## Step 3: Collect CloudWatch Metrics (namespace `AWS/Firehose`)

**Before querying metrics, load the authoritative thresholds reference:**
```
read_skill_resource(skill_id="firehose-operation-review", path="references/metrics-thresholds.md")
```
Use the thresholds from that file when classifying metric values as Normal, Warning,
or Critical throughout this step and Step 4.

**If this `read_skill_resource` call fails** (e.g. resource not found), do **not** silently
proceed on the model's own judgment. State it explicitly at the top of the report —
"⚠️ thresholds reference (`references/metrics-thresholds.md`) could not be loaded; metric
classifications use general Firehose guidance and may be less precise" — and continue with
best-effort general guidance. Surfacing the gap keeps reviews consistent and auditable.

All Firehose metrics use the dimension `DeliveryStreamName`. Pull metric data with
`cloudwatch.GetMetricData` over the selected window (default 7 days). Firehose
publishes metrics at 1-minute granularity. Select the metric set based on the stream's
**source** and **destination** discovered in Step 2 — many metrics are only emitted for
a specific destination or when a feature (backup, transform, format conversion,
dynamic partitioning) is enabled.

Core ingestion metrics (all streams):

| Metric | Stat | Signal |
|--------|------|--------|
| IncomingRecords / IncomingBytes | Sum | Volume; denominator for rate calcs (throttled data is excluded) |
| IncomingPutRequests | Sum | Direct PUT request volume |
| ThrottledRecords | Sum | Records dropped because an ingestion limit was exceeded |
| RecordsPerSecondLimit / BytesPerSecondLimit / PutRequestsPerSecondLimit | Max | Current throttling limits — compare observed load against these |

Source-specific ingestion metrics:
- **Kinesis Data Streams source**: `DataReadFromKinesisStream.Records/Bytes`,
  `KinesisMillisBehindLatest` (read lag), `ThrottledGetRecords`,
  `ThrottledGetShardIterator`, `ThrottledDescribeStream`.
- **MSK source**: `DataReadFromSource.Records/Bytes`, `KafkaOffsetLag`,
  `DataReadFromSource.Backpressured`, `SourceThrottled.Delay`.

Delivery metrics — pick the set matching the destination (`<Dest>` is one of
`S3`, `Redshift`, `AmazonOpenSearchService`, `AmazonOpenSearchServerless`, `Splunk`,
`HttpEndpoint`, `Snowflake`):

| Metric | Stat | Signal |
|--------|------|--------|
| DeliveryTo`<Dest>`.Success | Average | Delivery success ratio (successful / total). < 1.0 = retries/failures |
| DeliveryTo`<Dest>`.Records / .Bytes | Sum | Delivered volume |
| DeliveryTo`<Dest>`.DataFreshness (or `DeliveryToS3.DataFreshness` for warehouse dests) | Max | Age of oldest undelivered record (seconds) — the key delivery-lag signal |
| DeliveryToSplunk.DataAckLatency | Average | Splunk ack latency (rising trend = slow indexers) |
| DeliveryToSnowflake.DataCommitLatency | Average | Snowflake commit latency after insert |
| BackupToS3.Success / .Records / .DataFreshness | Avg / Sum / Max | Fallback-to-S3 activity for failed (or all) records |

Feature metrics (only when the feature is enabled):
- **Transform Lambda**: `ExecuteProcessing.Success` (ratio), `ExecuteProcessing.Duration`
  (ms), `SucceedProcessing.Records/Bytes`.
- **Format conversion**: `SucceedConversion.Records/Bytes`, `FailedConversion.Records/Bytes`.
- **Dynamic partitioning**: `PartitionCount`, `PartitionCountExceeded` (1/0),
  `ActivePartitionsLimit`, `PerPartitionThroughput`, `DeliveryToS3.ObjectCount`.
- **SSE**: `KMSKeyAccessDenied`, `KMSKeyDisabled`, `KMSKeyInvalidState`, `KMSKeyNotFound`.
- **CloudWatch Logs decompression**: `OutputDecompressedRecords.Failed`,
  `OutputDecompressedBytes.Failed`.

`cloudwatch.GetMetricData` allows up to 500 metric-data queries per call — batch
requests and paginate when a region has many streams.

**Alarm coverage.** To evaluate the alarm-coverage checks (Steps 4.4 and the
best-practices checklist), call `cloudwatch.DescribeAlarms` and match alarms whose
`MetricName` is `ThrottledRecords` or `DeliveryTo<Dest>.DataFreshness` with a
`Dimensions` entry of `DeliveryStreamName` = the stream under review. A stream with no
such alarm is a coverage gap.

**`DescribeAlarms` permission handling (per-region, partial results).** `DescribeAlarms`
is Region-scoped and permissions can differ across Regions in a multi-region scan, so
evaluate it **per Region, independently** — a denial in one Region must not suppress
alarm-coverage results in Regions where the call succeeds. On `AccessDenied` for a Region:
(1) do not fail the whole review; (2) mark **only that Region's** alarm coverage as
"not verified — `cloudwatch:DescribeAlarms` denied in `<region>`"; (3) still report alarm
coverage normally for Regions where the call succeeded; and (4) list the affected Regions
in the report so the reader knows which results are partial. Never infer a coverage gap
from a permission denial.

## Step 4: Analyze Against Best Practices

**Before evaluating findings, load the best-practices checklist:**
```
read_skill_resource(skill_id="firehose-operation-review", path="references/best-practices-checklist.md")
```
**If this `read_skill_resource` call fails**, state it explicitly at the top of the report
— "⚠️ best-practices checklist (`references/best-practices-checklist.md`) could not be
loaded; findings are based on the pillar guidance in this SKILL.md only" — and continue
using the per-pillar guidance in Step 4 below rather than silently skipping checks.

Use the checklist as the canonical list of items to evaluate for each pillar. Mark
each item as ✅ Pass, ⚠️ Warning, ❌ Fail, or ➖ Not Applicable, and generate a
finding for every Fail or Warning.

Evaluate all collected data across the pillars below and assign a severity to every
finding: CRITICAL, HIGH, MEDIUM, LOW, or INFO. The pillars are: **Security,
Reliability, Performance, Service Quotas, Cost Optimization, Operational Excellence,
Sustainability** — the seven Well-Architected-aligned pillars for Firehose.

The overall review *is* a best-practices assessment: every finding maps to an item in
`best-practices-checklist.md`. "Best Practices" is therefore the framing for the whole
review, not a separate pillar — do not create a "Best Practices" pillar section.

The inline `→ SEVERITY` tags below assign each finding's severity; the **Severity
Definitions** table (near the end of this file) is the single source of truth for what
each level *means* and its remediation SLA. If an SLA changes, update that table only —
the inline tags reference it, they do not restate the SLA.

### 4.1 Security
Ref: [Data protection in Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html)

- **Encryption at rest**: Direct PUT streams without server-side encryption (SSE)
  enabled → HIGH. For streams sourced from a Kinesis data stream, encryption is
  inherited from the source stream — verify the source stream is encrypted → HIGH if
  not.
  [Server-side encryption](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html)
- **Customer-managed KMS keys**: state the factual signal first — "stream uses an
  AWS-owned key (`AWS_OWNED_CMK`), not a customer-managed CMK, so there is no independent
  key rotation control or CloudTrail key-usage audit trail." Only escalate to → MEDIUM
  when there is an **objective data-classification signal** that the stream carries
  regulated/sensitive data — e.g. a data-classification tag such as
  `data-classification` / `classification` / `pii` = `sensitive`/`confidential`/`pci`/`phi`
  (from `ListTagsForDeliveryStream`), or a user-provided statement that the stream is
  in scope for a compliance regime. Absent such a signal, report it as **INFO**
  ("consider a CMK if this stream ingests regulated data") rather than assuming
  sensitivity.
- **Destination S3 encryption**: an S3/Extended-S3 destination writing objects without
  KMS encryption → MEDIUM.
- **KMS key health**: any non-zero `KMSKeyAccessDenied`, `KMSKeyDisabled`,
  `KMSKeyInvalidState`, or `KMSKeyNotFound` → CRITICAL (records cannot be delivered and
  are dropped or backed up — active data-loss risk).
- **IAM role scoping**: report the factual signal — the stream's delivery IAM role grants
  an action on `Resource: "*"` (rather than the specific destination / transform Lambda /
  KMS key ARNs). Flag any such `*`-resource grant at **INFO** with the specific
  statement quoted, and recommend narrowing to the concrete ARNs the stream actually uses;
  do not judge whether the breadth is "justified" — that's the owner's call, and a
  comprehensive least-privilege audit is out of scope. State the fact and the
  least-privilege alternative; let the reader decide.
  [Controlling access](https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html)
- **Access control beyond the delivery role**: the delivery IAM role governs what Firehose
  can write to the destination, but *who/what can put records to, or administer, the stream*
  is controlled by identity/SCP policies granting `firehose:PutRecord*` / `firehose:*` on
  the stream ARN. Flag overly broad grants of `firehose:PutRecord*` or admin actions (e.g.
  `firehose:*` on `*`) where visible → INFO (a full identity-policy audit is out of scope).
  Also treat delivery-stream tags as an access-control input: tags can back ABAC / condition
  keys, so missing or inconsistent tags weaken tag-based access control (this overlaps the
  Operational Excellence tagging check — report the security angle only where tags are
  actually used in a policy condition).
- **VPC / private connectivity**: OpenSearch or Redshift destinations reachable over
  the public internet where a VPC configuration is available and appropriate → MEDIUM.
- **Cross-account / PrivateLink destinations**: for OpenSearch, Redshift, and HTTP-endpoint
  destinations that write cross-account or over a public endpoint, prefer a VPC/PrivateLink
  path so delivery traffic stays off the public internet, and confirm the destination
  resource policy and the delivery IAM role are scoped to the specific cross-account
  resource → MEDIUM. A cross-account destination reachable only over the public internet
  with a broadly-scoped role → HIGH.
  [Firehose and interface VPC endpoints (PrivateLink)](https://docs.aws.amazon.com/firehose/latest/dev/vpc.html)
- **HTTP endpoint destinations**: verify TLS (HTTPS) is used and the access key is
  stored securely → HIGH if a non-HTTPS endpoint is configured.
- **CloudWatch error logging**: evaluated under Operational Excellence (4.6) — a
  disabled log config blocks diagnosis of delivery/transform errors. Not double-reported
  here.

### 4.2 Reliability
Ref: [Troubleshooting Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/troubleshoot-common-issues.html)

- **Data freshness (delivery lag)**: `DeliveryTo<Dest>.DataFreshness` (Max)
  **sustained** (per the "sustained" definition in `references/metrics-thresholds.md` —
  ≥ 3 consecutive datapoints) above the configured buffering interval plus the retry
  duration indicates records are aging out and at risk of loss → HIGH; freshness
  **climbing monotonically** (per that file's definition — non-decreasing across ≥ 6
  consecutive 5-min datapoints, ~30 min, delivery stalled) → CRITICAL. This is the single
  most important Firehose health signal.
  [Data freshness](https://docs.aws.amazon.com/firehose/latest/dev/troubleshoot-common-issues.html)
- **Delivery success ratio**: `DeliveryTo<Dest>.Success` (Average) < 1.0 indicates
  retries; a sustained ratio well below 1.0 with no S3 backup configured → HIGH
  (records can be lost after retries exhaust). Use the **exact per-destination metric
  name** for `<Dest>`: `DeliveryToS3`, `DeliveryToRedshift`,
  `DeliveryToAmazonOpenSearchService`, `DeliveryToAmazonOpenSearchServerless`,
  `DeliveryToSplunk`, `DeliveryToHttpEndpoint`, `DeliveryToSnowflake`, `DeliveryToIceberg`.
  Note the OpenSearch metric is `DeliveryToAmazonOpenSearchService.*` — there is **no**
  `DeliveryToElasticsearch.*` metric (the service was renamed; the old name does not exist
  in `AWS/Firehose`). Do not invent a metric for a destination not in this list.
- **S3 backup for failed records**: streams to Redshift/OpenSearch/Splunk/HTTP/Snowflake
  with `S3BackupMode` = `Disabled` → MEDIUM (failed records are not recoverable). For
  sensitive or non-reproducible data → HIGH.
- **Redshift-specific delivery failures**: for Redshift destinations, a sustained
  `DeliveryToRedshift.Success` < 1.0 (with healthy `DeliveryToS3.Success` for the staging
  step) points to Redshift-side COPY failures, not a Firehose problem — common causes are a
  **paused/resized cluster**, an **invalid or missing COPY IAM role**, a bad COPY option
  string, or a schema/column mismatch. These surface in `STL_LOAD_ERRORS` on the cluster,
  not in `AWS/Firehose` → MEDIUM (HIGH if the staging S3 backup is also disabled, since
  rows then have no recoverable copy). Recommend confirming cluster availability and the
  COPY role separately from the generic delivery-success check.
- **Retry duration**: destination `RetryOptions.DurationInSeconds` set to 0 or very low
  for a destination that can experience transient failures → MEDIUM.
- **Source read lag**: for Kinesis-sourced streams, high `KinesisMillisBehindLatest` →
  MEDIUM (Firehose is falling behind the source; check for throttling on the source
  stream). For MSK-sourced streams, high `KafkaOffsetLag` or
  `DataReadFromSource.Backpressured` = true → MEDIUM.
- **Transform Lambda failures**: `ExecuteProcessing.Success` < 1.0 or elevated
  `ExecuteProcessing.Duration` approaching the transform timeout → MEDIUM (failed
  transforms are sent to the S3 error prefix; confirm backup is configured).
- **Format conversion failures**: non-zero `FailedConversion.Records` → MEDIUM
  (records that fail Parquet/ORC conversion go to the S3 error prefix).
- **Dynamic partitioning key-extraction failures**: for streams with dynamic partitioning
  enabled, records whose partition keys can't be extracted are routed to the S3 error
  prefix rather than delivered — a common cause is a **JQ expression error** (partitioning
  via `MetadataExtraction`/JQ) or records that aren't newline-delimited / valid JSON when
  the config expects them to be. Watch `JQProcessing.Duration` (present only when JQ-based
  partitioning is enabled) and, more importantly, **check the S3 error prefix for
  partitioning-error records** and reconcile against `IncomingRecords` → MEDIUM when the
  error prefix is accumulating partitioning failures (HIGH if no one is monitoring the
  error prefix). Validate the JQ expression and the source record format against the
  partitioning config.
- **Iceberg delivery correctness (CloudWatch is not sufficient)**: for Apache Iceberg
  destinations, delivery metrics (`DeliveryToIceberg.Bytes`/`.Records`) and the S3 error
  prefix are **necessary but not sufficient** evidence that data landed. Records must be
  **one JSON object per record**; aggregated or compressed source records — notably from a
  **CloudWatch Logs subscription filter** (gzipped, multi-event payloads) or KPL
  aggregation — can fail to land in the Iceberg table. Confirm the source emits a single
  JSON object per record (decompress/split upstream, e.g. in the transform Lambda), and
  recommend an **independent row-count reconciliation** between records ingested
  (`IncomingRecords`) and rows actually present in the Iceberg table → MEDIUM where a
  compressed/aggregated source feeds an Iceberg destination without a decompression/split
  step; recommend reconciliation regardless.
  [Iceberg considerations — one JSON object per record](https://docs.aws.amazon.com/firehose/latest/dev/apache-iceberg-considerations.html)
- **Multi-region / DR posture (architecture consideration, not API-verifiable)**: Firehose
  has no native cross-region delivery or replication, so DR for a critical stream is an
  architecture decision (e.g. a parallel stream in a second Region, or region-redundant
  producers) that the skill cannot confirm from Firehose APIs. For streams the user
  designates business-critical, surface this as an **INFO** consideration — prompt whether a
  regional-failover path exists — rather than a graded finding.

### 4.3 Performance
Ref: [Amazon Data Firehose data delivery](https://docs.aws.amazon.com/firehose/latest/dev/basic-deliver.html)

- **Throttling**: sustained non-zero `ThrottledRecords` → HIGH (ingestion exceeds a
  stream limit; request a quota increase and/or add producer-side backoff). Correlate
  with `RecordsPerSecondLimit` / `BytesPerSecondLimit` / `PutRequestsPerSecondLimit`.
- **Buffering hints tuning**: buffering interval much larger than the workload's
  latency requirement inflates delivery lag; interval/size too small drives excessive
  small-object writes (cost + downstream inefficiency). Flag hints misaligned with the
  destination and freshness target → MEDIUM.
- **Splunk ack latency**: rising `DeliveryToSplunk.DataAckLatency` trend → MEDIUM (slow
  Splunk indexers; scale HEC/indexers).
- **Dynamic partitioning limits**: `PartitionCountExceeded` emitting 1, or
  `PartitionCount` approaching `ActivePartitionsLimit` (default 500) → MEDIUM (records
  over the limit go to the error bucket; request a limit increase or reduce
  partition cardinality).

### 4.4 Service Quotas
Ref: [Amazon Data Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)

- **Streams per region**: default 50 delivery streams per account per Region. Compare the
  stream count against the quota from `servicequotas.GetServiceQuota` and apply the
  utilization bands in the "Service Quota Utilization" table of
  `references/metrics-thresholds.md` → MEDIUM in the Warning band (request an increase
  before hitting `LimitExceededException` on create).
- **Per-stream throughput (Direct PUT)**: default 2,000 transactions/s, 5,000 records/s,
  and (region-dependent) 5 MB/s — these three scale proportionally. Compare observed P95
  ingestion (records/s, bytes/s from `IncomingRecords`/`IncomingBytes`, PUT rate from
  `IncomingPutRequests`) against `RecordsPerSecondLimit` / `BytesPerSecondLimit` /
  `PutRequestsPerSecondLimit`, and apply the utilization bands from the "Service Quota
  Utilization" table in `references/metrics-thresholds.md` → MEDIUM in the Warning band;
  Critical band with non-zero `ThrottledRecords` → HIGH.
- **Iceberg-table throughput**: Direct PUT to Apache Iceberg tables has a lower,
  Region-dependent, evolving per-stream limit. **Do not hardcode it** — see the Iceberg
  throughput note in `references/metrics-thresholds.md` (Service Quota Utilization section)
  for the current values, the `AppendOnly` auto-scaling behavior, and the
  throughput-vs-active-partitions tradeoff. "Approaching the limit" = the Warning band
  (> 75% of the `GetServiceQuota` value) from that file → MEDIUM.
- **Quota-utilization alarming**: recommend a CloudWatch alarm that fires as observed
  throughput approaches the `*PerSecondLimit` values → LOW where missing. General alarm
  coverage (`ThrottledRecords`, `DataFreshness`) is assessed under Operational Excellence
  (4.6) to avoid double-reporting.

### 4.5 Cost Optimization
Ref: [Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/)

- **Compression**: an S3/Extended-S3 destination with `CompressionFormat` = UNCOMPRESSED
  → MEDIUM (GZIP/Snappy/Zip cut S3 storage and downstream scan cost; Snappy/ZIP are
  splittable for query engines).
  [Compression](https://docs.aws.amazon.com/firehose/latest/dev/create-configure.html)
- **Format conversion to columnar**: S3 data queried by Athena/EMR/Redshift Spectrum
  stored as JSON/CSV rather than Parquet/ORC → MEDIUM opportunity (columnar formats cut
  scan cost dramatically).
  [Record format conversion](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html)
- **Buffering sized for fewer, larger objects**: very small buffer size/interval on
  high-volume S3 streams produces many small objects → MEDIUM (higher S3 PUT cost and
  poor query performance). Increase buffer size where the freshness target allows.
- **Dynamic partitioning efficiency**: dynamic partitioning producing many tiny
  partitions (low `PerPartitionThroughput`, high `DeliveryToS3.ObjectCount`) → LOW
  opportunity (consolidate partition keys).
- **Idle streams**: `IncomingRecords` ≈ 0 over the full window on an existing stream →
  INFO (candidate for decommissioning; Firehose bills on ingested volume, but idle
  streams still consume the per-region stream quota). **Guard against false positives on
  new streams:** `IncomingRecords` ≈ 0 alone does not distinguish "abandoned" from "newly
  created, not yet in use." Only flag as idle when `CreateTimestamp` age exceeds the
  idle-stream minimum-age threshold in `references/metrics-thresholds.md`; for younger
  streams, note "recently created — insufficient history to judge idleness" instead.

**Estimating the "Est. Impact" column (rough, directional).** These are back-of-envelope
figures for prioritization, not billing forecasts — always confirm against the current
[Firehose pricing page](https://aws.amazon.com/firehose/pricing/) and the destination's
own storage/scan pricing.

**Where the unit rates come from (in priority order):**
1. **Ask the user for their negotiated / EDP rate** if cost precision matters and there is
   an interactive user. **Never block on this** — if there is no interactive user
   (scheduled/automated run per Step 1) or the user does not respond, do **not** wait;
   fall straight through to (2).
2. **Default: current public on-demand list prices** (S3 Standard `$/GB-month`, S3 PUT
   `$/1,000 requests`, and the relevant Athena/scan rate) for the stream's Region, applied
   as constants and **explicitly labeled "rough estimate at public on-demand list rates,
   <region>, as of <date the skill was run>."** This is the default path, not a last
   resort — always produce a labeled figure rather than omitting cost.
3. `pricing.GetProducts` (AWS Price List API) can supply these programmatically, but it is
   **not** in the default `AIDevOpsAgentAccessPolicy`. If the permission is present, use it.
   **On `AccessDenied` (or if the permission is absent), degrade to option (2)** — a
   clearly-labeled list-price estimate — rather than silently omitting the cost figure.
   Never drop a cost estimate solely because `pricing.GetProducts` was denied.

Never emit a dollar figure without stating which rate source (1/2/3) was used.

- Extrapolate monthly ingested volume from the window: `GB/month ≈ (Sum of IncomingBytes
  over window / window days) × 30 / 1e9`.
- **Compression / columnar conversion** savings land mostly *downstream* (S3 storage +
  Athena/Spectrum scan cost), not on the Firehose bill: `downstream monthly saving ≈
  stored_GB × storage_$/GB × (1 − compression_ratio)`, where `storage_$/GB` is the rate
  from the source chosen above, plus query-scan savings proportional to the same ratio.
  The ~0.3–0.5-of-original ratio for GZIP on JSON is a **static default assumption, not
  measured** — where possible refine it from the stream's own observed data (e.g. compare
  `IncomingBytes` against `DeliveryToS3.Bytes`, or a sample) and state whether the ratio
  used is the default or observed. Always label the resulting figure an estimate.
- **Small-object / buffering** impact is driven by S3 PUT request cost: `monthly PUT cost
  ≈ (DeliveryToS3.ObjectCount rate × 30 days) × S3_PUT_$` (S3 PUT rate from the chosen
  source). Larger buffers cut object count roughly linearly.
- Firehose format-conversion and dynamic-partitioning features carry their own per-GB
  charges — net them against the downstream savings before calling an opportunity
  worthwhile.
- **Firehose base ingestion cost is deliberately excluded from these estimates.** Firehose
  bills per GB ingested (plus format-conversion/partitioning surcharges), but the
  optimizations above — compression, columnar conversion, buffer sizing — change *downstream*
  storage/scan cost, not the volume ingested into Firehose, so they don't reduce the base
  ingestion charge. State this in the report so a reader doesn't assume the ingestion line
  item is part of the savings. (The only lever that reduces base ingestion cost is
  ingesting less data — e.g. filtering/decommissioning idle streams, covered separately.)
Keep every figure clearly marked as an estimate with its assumptions and rate source stated.

### 4.6 Operational Excellence
Ref: [Monitoring Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/monitoring.html)

- **CloudWatch error logging**: `CloudWatchLoggingOptions.Enabled` = false means
  delivery and transform failures land in the S3 error prefix with no queryable error
  detail → MEDIUM (blocks incident diagnosis). (This is the operational-diagnosis angle;
  the Security pillar flags the same setting for its incident-response impact — report it
  once, under Operational Excellence, and cross-reference.)
- **Alarm coverage**: using the `cloudwatch.DescribeAlarms` results from Step 3, a stream
  with no alarm on `ThrottledRecords` or `DeliveryTo<Dest>.DataFreshness` → MEDIUM (no
  proactive signal for throttling or delivery lag). Also recommend alarms on
  `DeliveryTo<Dest>.Success` (Minimum) and any `KMSKey*` metric. If alarm state could not
  be read, report "alarm coverage not verified" rather than a gap.
- **Tagging / ownership**: streams missing ownership and cost-allocation tags (from
  `ListTagsForDeliveryStream`) → LOW (hinders cost attribution and incident routing). Note
  that tags only drive cost visibility once **activated as cost-allocation tags in the
  Billing console** — that activation state is a billing-account setting not readable
  through this skill's APIs, so recommend the user verify activation in Billing / Cost
  Explorer rather than reporting it as verified here. **If the user provides an org tagging
  standard**, check completeness against their required keys (commonly `team`/`owner`,
  `environment`, `cost-center`, `application`) and flag streams missing any required key;
  absent a stated standard, flag only fully-untagged streams and suggest a baseline
  ownership + environment + cost-center tag set rather than asserting specific keys.
- **Configuration management**: streams whose config drifts from an IaC baseline, or that
  appear hand-edited (frequent `LastUpdateTimestamp` changes with no change record) → LOW
  (prefer CloudFormation/CDK/Terraform-managed streams for repeatability and auditability).
- **Observability of transforms**: transform-Lambda-enabled streams without an alarm on
  `ExecuteProcessing.Success` / `.Duration`, or without the Lambda's own logging → LOW.
- **Runbook readiness**: destinations prone to transient failure (Splunk, HTTP endpoint,
  Snowflake) without a documented backup/replay procedure for the S3 error prefix → LOW.

### 4.7 Sustainability
Ref: [Sustainability Pillar — AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)

Firehose sustainability levers overlap heavily with Cost Optimization — the same
efficiency measures reduce both spend and the energy/storage footprint of the data. Flag
these under Sustainability with a cross-reference to 4.5 rather than duplicating the cost
rationale; keep severities at LOW/INFO unless the waste is **large** — see the
"large waste" definition in `references/metrics-thresholds.md` (≥ 25% of the stream's
estimated monthly delivered-storage cost, or ≥ 100 GB/month of avoidable volume), which
raises the finding one severity level.

- **Data reduction before storage**: uncompressed S3 output, or row-oriented (JSON/CSV)
  data that could be columnar (Parquet/ORC), stores and later scans more bytes than
  necessary → LOW (less data provisioned and processed downstream). Cross-ref 4.5
  Compression / Format conversion.
- **Efficient object sizing**: many tiny S3 objects (low `PerPartitionThroughput`, high
  `DeliveryToS3.ObjectCount`) increase request overhead and downstream scan inefficiency →
  LOW. Right-size buffering. Cross-ref 4.5.
- **Decommission idle streams**: streams with `IncomingRecords` ≈ 0 over the window hold
  provisioned resources for no workload → INFO (remove to shrink the footprint). Cross-ref
  4.5 Idle streams.
- **Right-size retention downstream**: where Firehose feeds an S3 data lake, recommend S3
  lifecycle policies / tiering on the delivered prefixes so cold data is not kept on hot
  storage indefinitely → INFO (Firehose does not set these, but the review should surface
  the opportunity for the destination bucket).

## Step 5: Generate Report

Generate a shareable report artifact for the review.

Artifact naming: `firehose-review-<stream-or-account>-<region>-<YYYY-MM-DD>.md`
Examples: `firehose-review-orders-stream-us-east-1-2026-09-17.md` (single stream),
`firehose-review-123456789012-us-east-1-2026-10-02.md` (account/region rollup)

Structure the Markdown document with:

### Report Header
```
# Amazon Data Firehose Operational Review — <stream or account-id> / <region>
Date: <YYYY-MM-DD> | Analysis window: <start> to <end>
Pillars reviewed: <list>
```

### Executive Summary
- Health: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
- Finding counts by severity
- Top 3 critical/high items

### Change Since Last Review (recurring runs only — see Step 6)
When a prior report for this scope exists, summarize before the detailed findings:
- New (with severity), Resolved, and Persistent (with any severity change) counts
- Call out any new or persistent CRITICAL/HIGH explicitly
Omit this section (or note "baseline review") when there is no prior run to compare.

### Account-Level Rollup (when scope spans multiple streams/regions)
When the review covers more than one stream, lead with an account/region rollup before
the per-stream detail so the reader sees systemic gaps at a glance:

| Region | Streams | Encryption gaps | Streams w/o backup | Streams throttling | Delivery-lag alerts | Uncompressed S3 |
|--------|---------|-----------------|--------------------|--------------------|--------------------|-----------------|

Summarize as "X of Y streams" per issue class, and call out any finding that affects a
**majority of streams** — per the "majority of streams" definition in
`references/metrics-thresholds.md` (≥ 60% of in-scope streams) — as a systemic
(account-level) item rather than repeating it per stream. Skip this section for a
single-stream review.

### Findings by Pillar
For each of Security, Reliability, Performance, Service Quotas, Cost Optimization,
Operational Excellence, and Sustainability:

| # | Finding | Severity | Current State | Recommendation |

Include a pillar even when it has no findings — show it with a "No findings — ✅" row so
the reader can see the pillar was assessed (Sustainability and Operational Excellence will
often be light).

### Delivery Stream Configuration
Per stream: source type, destination, buffering hints, compression, encryption,
backup mode, transform/format-conversion status, and CloudWatch logging.

### CloudWatch Metrics Summary
| Stream | Metric | Stat | Value | Status | Finding |

### Service Quota Utilization
| Quota | Value | Observed P95 | Utilization % | Risk |

### Cost Optimization & Sustainability Opportunities
Cost and sustainability opportunities share the same efficiency levers — list them
together, marking which pillar(s) each serves:

| Opportunity | Signal | Pillar(s) | Est. Impact | Effort |

### Priority Matrix
| # | Finding | Severity | Pillar | Effort | Impact |

### Next Steps
- Immediate (CRITICAL/HIGH — 7 days)
- Short-term (MEDIUM — 30 days)
- Long-term (LOW — 90 days)

### Appendix — Reference Links
- [Amazon Data Firehose Developer Guide](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html)
- [Monitoring with CloudWatch metrics](https://docs.aws.amazon.com/firehose/latest/dev/monitoring-with-cloudwatch-metrics.html)
- [CloudWatch alarm best practices](https://docs.aws.amazon.com/firehose/latest/dev/firehose-cloudwatch-metrics-best-practices.html)
- [Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)
- [Data protection / encryption](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html)
- [Record format conversion](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html)
- [Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)
- [Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)

**Re-run behavior:** Before creating a new report artifact, check for an existing report
for the same stream/account and region. If one exists, refresh it with the latest data
instead of creating a duplicate.

## Step 6: Track Findings Over Time (recurring reviews)

When this skill runs on a schedule (or is re-run manually), a stateless snapshot loses
the most useful operational signal: what changed since last time. If a prior report
artifact exists for the same stream/account + region (from the re-run check above),
diff this run's findings against it and lead the new report with a **Change Since Last
Review** section:

- **New** — findings present now but not in the prior report (regressions or newly
  surfaced issues). Highlight these first; a new CRITICAL/HIGH is the top signal.
- **Resolved** — findings in the prior report absent now (fixed or no longer applicable).
  Acknowledge them so the reader sees progress.
- **Persistent** — findings in both, with any severity change noted (e.g. MEDIUM → HIGH as
  utilization climbs). Persistent CRITICAL/HIGH items that recur across runs warrant
  escalation, not just re-listing.

Match findings across runs by a stable key (stream name + pillar + check identity), not
by exact wording, so a re-phrased finding isn't miscounted as new+resolved. If no prior
report exists, note "baseline review — no prior run to compare" and skip the diff. Keep
the diff advisory: never suppress a current finding just because it also appeared last
time.

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity (e.g. delivery stalled, KMS key failures) | Fix within 24–48 hours |
| HIGH | Significant gap that could lead to data loss or incidents | Fix within 1 week |
| MEDIUM | Notable improvement opportunity | Plan within 30 days |
| LOW | Minor optimization or hardening | Address when convenient |
| INFO | Observation, no action required | N/A |

## Region-Restricted Checks

Some checks depend on Region:
- **Iceberg-table throughput cap**: lower and Region-dependent — call
  `servicequotas.GetServiceQuota` and cite the returned value. Do not state a reference
  number; the limit varies by Region and changes over time, and `AppendOnly=True` streams
  auto-scale. See the Iceberg note in `references/metrics-thresholds.md`.
- **Direct PUT throughput defaults** vary by Region — read the actual limit from the
  `*PerSecondLimit` CloudWatch metrics rather than assuming a fixed value.

## Known API Quirks

- `DeliveryTo<Dest>.Success` is a **ratio** (successful puts / total puts), not a count.
  Small dips below 1.0 do not mean data loss — Firehose retries and, when backup is
  configured, falls back to S3. Sustained low values with no backup are the concern.
- `DataFreshness` is emitted per destination; for warehouse destinations (Redshift) the
  S3 staging freshness appears as `DeliveryToS3.DataFreshness`.
- `ThrottledRecords` counts records dropped at ingestion — throttled data is **excluded**
  from `IncomingRecords`/`IncomingBytes`, so compute throttle rate as
  `ThrottledRecords / (IncomingRecords + ThrottledRecords)`.
- Metrics are aggregated over 1-minute intervals; sub-second bursts may not appear.
- `cloudwatch.GetMetricData` caps at 500 metric-data queries per call — batch and
  paginate for accounts with many streams.

## Data Source Boundaries

This skill collects data exclusively through native AWS APIs
(`firehose`, `cloudwatch`, `servicequotas`). It does **not**:
- Put, read, or transform any records (no data-plane calls).
- Read delivered object content, transform Lambda code, or destination data.
- Depend on any non-AWS tooling or internal scripts — the skill is self-contained on
  the DevOps Agent's primary cloud-source IAM role.

**Runtime inputs vs. eval fixtures.** At review time the skill reads only live AWS APIs
and its own `references/` files. `evals/files/firehose-context.json` is an **evaluation
fixture** used solely by the skill-evaluation harness — it is **not** a runtime input and
is not read during an actual review (interactive, scheduled, or automated). If it is
absent or unreadable, real reviews are unaffected; only eval runs that reference it would
skip those fixture-backed cases. There is therefore no unattended-run fallback needed for
this file.
