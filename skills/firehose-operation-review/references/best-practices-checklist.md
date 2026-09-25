# Amazon Data Firehose Best Practices Checklist

Organized by pillar. This is the **canonical list of items to evaluate** for `SKILL.md`
Step 4: mark each ✅ Pass / ⚠️ Warning / ❌ Fail / ➖ N/A and raise a finding for every
Fail or Warning.

The **base severity** in each item is the default for that finding. Where a row lists a
condition (e.g. "→ HIGH if …"), apply the escalation. Classify metric values with the
bands in `metrics-thresholds.md`; the "sustained" / "climbing monotonically" / idle-age /
"large waste" definitions live in that file's *Derived / tunable thresholds* table.
Several items carry judgment rules that must be applied exactly as written — they are
called out inline below.

## Security
Ref: [Data protection in Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html) · [Controlling access](https://docs.aws.amazon.com/firehose/latest/dev/controlling-access.html) · [VPC/PrivateLink](https://docs.aws.amazon.com/firehose/latest/dev/vpc.html)

- [ ] **Encryption at rest** (HIGH) — SSE enabled on Direct PUT streams. For Kinesis-sourced
  streams, encryption is inherited from the source data stream — verify the source stream is
  encrypted (HIGH if not).
- [ ] **Customer-managed KMS key** — the stream uses an AWS-owned key (`AWS_OWNED_CMK`), not a
  customer-managed CMK, so there is no independent key-rotation control or CloudTrail
  key-usage audit trail. **State that factual signal first.** Escalate to **MEDIUM only** when
  there is an objective data-classification signal that the stream carries regulated/sensitive
  data — e.g. a `data-classification` / `classification` / `pii` tag = `sensitive` /
  `confidential` / `pci` / `phi` (from `ListTagsForDeliveryStream`), or a user statement that
  the stream is in scope for a compliance regime. Absent such a signal, report **INFO**
  ("consider a CMK if this stream ingests regulated data") — do not assume sensitivity.
- [ ] **Destination S3 encryption** (MEDIUM) — S3/Extended-S3 destination writing objects
  without KMS encryption.
- [ ] **KMS key health** (CRITICAL) — any non-zero `KMSKeyAccessDenied` / `KMSKeyDisabled` /
  `KMSKeyInvalidState` / `KMSKeyNotFound` (records cannot be delivered — active data-loss risk).
- [ ] **IAM role scoping** (INFO) — report the factual signal where the delivery role grants an
  action on `Resource: "*"` rather than the specific destination / transform Lambda / KMS key
  ARNs; quote the statement and recommend narrowing. **Do not judge whether the breadth is
  "justified"** — that's the owner's call, and a full least-privilege audit is out of scope.
- [ ] **Access control beyond the delivery role** (INFO) — flag overly broad `firehose:PutRecord*`
  or admin grants (e.g. `firehose:*` on `*`) on the stream ARN where visible (a full
  identity-policy audit is out of scope). Missing/inconsistent tags weaken tag-based access
  control only where tags actually back a policy condition — report that security angle only
  then (tagging completeness itself is an Operational Excellence item).
- [ ] **VPC / private connectivity** (MEDIUM) — OpenSearch/Redshift destinations reachable over
  the public internet where a VPC configuration is available and appropriate.
- [ ] **Cross-account / PrivateLink destinations** (MEDIUM) — cross-account OpenSearch/Redshift/
  HTTP destinations should use a VPC/PrivateLink path (not the public internet), with the
  delivery role and destination resource policy scoped to the specific cross-account resource.
  → **HIGH** if reachable only over the public internet with a broadly-scoped role.
- [ ] **HTTP endpoint destinations** (HIGH if violated) — HTTPS (TLS) only; access key stored
  securely. A non-HTTPS endpoint is HIGH.
- [ ] **CloudWatch error logging** — enabled so delivery/transform errors can be diagnosed.
  Report this **once, under Operational Excellence** (its incident-diagnosis home); cross-ref
  the security/incident-response angle rather than double-reporting.

## Reliability
Ref: [Troubleshooting Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/troubleshoot-common-issues.html) · [Iceberg considerations](https://docs.aws.amazon.com/firehose/latest/dev/apache-iceberg-considerations.html)

- [ ] **Data freshness** (HIGH) — `DeliveryTo<Dest>.DataFreshness` (Max) **sustained** above the
  configured buffering interval + retry duration means records are aging and at risk. →
  **CRITICAL** when freshness is **climbing monotonically** (delivery stalled). This is the
  single most important Firehose health signal.
- [ ] **Delivery success ratio** (HIGH) — a sustained `DeliveryTo<Dest>.Success` (Average) well
  below 1.0 **with no S3 backup configured** (records can be lost after retries exhaust). Use
  the exact per-destination metric name (`DeliveryToS3`, `DeliveryToRedshift`,
  `DeliveryToAmazonOpenSearchService`, `DeliveryToAmazonOpenSearchServerless`, `DeliveryToSplunk`,
  `DeliveryToHttpEndpoint`, `DeliveryToSnowflake`, `DeliveryToIceberg`). **There is no
  `DeliveryToElasticsearch.*` metric** (the service was renamed) — do not invent one.
- [ ] **S3 backup for failed records** (MEDIUM) — `S3BackupMode` = `Disabled` on
  Redshift/OpenSearch/Splunk/HTTP/Snowflake destinations (failed records unrecoverable). →
  **HIGH** for sensitive or non-reproducible data.
- [ ] **Retry duration** (MEDIUM) — destination `RetryOptions.DurationInSeconds` = 0 or very low
  for a destination that can experience transient failures.
- [ ] **Source read lag** (MEDIUM) — high Kinesis `KinesisMillisBehindLatest`, or high MSK
  `KafkaOffsetLag` / `DataReadFromSource.Backpressured` = true (Firehose falling behind the
  source; check for source-side throttling).
- [ ] **Transform Lambda health** (MEDIUM) — `ExecuteProcessing.Success` < 1.0 or
  `ExecuteProcessing.Duration` approaching the transform timeout (failed transforms route to
  the S3 error prefix; confirm backup).
- [ ] **Format conversion** (MEDIUM) — non-zero `FailedConversion.Records` (records failing
  Parquet/ORC conversion go to the S3 error prefix).
- [ ] **Dynamic partitioning key-extraction failures** (MEDIUM; **HIGH** if no one monitors the
  error prefix) — with dynamic partitioning enabled, records whose partition keys can't be
  extracted route to the S3 error prefix rather than being delivered. Common cause: a **JQ
  expression error** (`MetadataExtraction`/JQ), or records that aren't newline-delimited / valid
  JSON when the config expects it. Watch `JQProcessing.Duration` (present only with JQ-based
  partitioning) and, more importantly, **check the S3 error prefix for partitioning-error
  records** and reconcile against `IncomingRecords`. Validate the JQ expression and source record
  format against the partitioning config.
- [ ] **Redshift COPY health** (MEDIUM) — a sustained `DeliveryToRedshift.Success` < 1.0 **with
  healthy `DeliveryToS3.Success`** for the staging step points to Redshift-side COPY failures,
  not a Firehose problem — common causes: paused/resized cluster, invalid/missing COPY IAM role,
  bad COPY options, schema/column mismatch. These surface in `STL_LOAD_ERRORS` on the cluster,
  not in `AWS/Firehose`. → **HIGH** if staging S3 backup is also disabled. Recommend confirming
  cluster availability and the COPY role separately.
- [ ] **Iceberg landing verified** (MEDIUM) — for Apache Iceberg destinations, delivery metrics
  and the S3 error prefix are **necessary but not sufficient** evidence data landed. Records
  must be **one JSON object per record**; aggregated/compressed sources (notably a CloudWatch
  Logs subscription filter, or KPL aggregation) can fail to land. Confirm one JSON object per
  record (decompress/split upstream) and recommend an independent row-count reconciliation of
  `IncomingRecords` vs rows in the table. Flag MEDIUM where a compressed/aggregated source feeds
  Iceberg without a decompression/split step; recommend reconciliation regardless.
- [ ] **Multi-region / DR posture** (INFO, not API-verifiable) — Firehose has no native
  cross-region delivery/replication, so DR is an architecture decision the skill can't confirm
  from Firehose APIs. For streams the user designates business-critical, surface as INFO (prompt
  whether a regional-failover path exists) rather than a graded finding.

## Performance
Ref: [Amazon Data Firehose data delivery](https://docs.aws.amazon.com/firehose/latest/dev/basic-deliver.html)

- [ ] **Throttling** (HIGH) — sustained non-zero `ThrottledRecords` (ingestion exceeds a stream
  limit). Correlate with `RecordsPerSecondLimit` / `BytesPerSecondLimit` /
  `PutRequestsPerSecondLimit`; request a quota increase and/or add producer-side backoff.
- [ ] **Buffering hints** (MEDIUM) — interval much larger than the latency requirement inflates
  delivery lag; interval/size too small drives excessive small-object writes. Flag hints
  misaligned with the destination and freshness target.
- [ ] **Splunk ack latency** (MEDIUM) — rising `DeliveryToSplunk.DataAckLatency` trend (slow
  Splunk indexers; scale HEC/indexers).
- [ ] **Dynamic partitioning limits** (MEDIUM) — `PartitionCountExceeded` = 1, or `PartitionCount`
  approaching `ActivePartitionsLimit` (default 500) — records over the limit go to the error
  bucket; request a limit increase or reduce partition cardinality.

## Service Quotas
Ref: [Amazon Data Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)

Apply the utilization bands in the *Service Quota Utilization* table of `metrics-thresholds.md`
(Warning > 75%). All quota values come from `servicequotas.GetServiceQuota` / the
`*PerSecondLimit` metrics — do not hardcode Region-dependent numbers.

- [ ] **Streams per Region** (MEDIUM in Warning band) — stream count vs the per-Region quota
  (default 50); request an increase before `LimitExceededException` on create.
- [ ] **Per-stream throughput (Direct PUT)** (MEDIUM in Warning band; **HIGH** in Critical band
  with non-zero `ThrottledRecords`) — observed P95 records/s, bytes/s, PUT/s vs the
  `*PerSecondLimit` metrics (the three limits scale proportionally).
- [ ] **Iceberg-table throughput** (MEDIUM in Warning band) — lower, Region-dependent, evolving
  per-stream limit. **Do not hardcode it** — see the Iceberg throughput note in
  `metrics-thresholds.md` for current values, `AppendOnly` auto-scaling, and the
  throughput-vs-active-partitions tradeoff.
- [ ] **Quota-utilization alarming** (LOW where missing) — a CloudWatch alarm firing as
  throughput approaches the `*PerSecondLimit` values. General alarm coverage
  (`ThrottledRecords`, `DataFreshness`) is assessed under Operational Excellence to avoid
  double-reporting.

## Cost Optimization
Ref: [Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/)

Cost/impact-estimation procedure (rate sourcing, extrapolation formulas, and the base-ingestion
exclusion) lives in `SKILL.md` Step 4's "Cost Optimization — impact-estimation procedure"
section — apply it when populating the "Est. Impact" column.

- [ ] **Compression** (MEDIUM) — S3/Extended-S3 destination with `CompressionFormat` =
  UNCOMPRESSED (GZIP/Snappy/Zip cut S3 storage and downstream scan cost; Snappy/ZIP are
  splittable for query engines).
- [ ] **Columnar format conversion** (MEDIUM opportunity) — S3 data queried by
  Athena/EMR/Redshift Spectrum stored as JSON/CSV rather than Parquet/ORC.
- [ ] **Buffering sized for fewer, larger objects** (MEDIUM) — very small buffer size/interval on
  high-volume S3 streams produces many small objects (higher S3 PUT cost + poor query perf).
- [ ] **Dynamic partitioning efficiency** (LOW opportunity) — many tiny partitions (low
  `PerPartitionThroughput`, high `DeliveryToS3.ObjectCount`); consolidate partition keys.
- [ ] **Idle streams** (INFO) — `IncomingRecords` ≈ 0 over the full window on an existing stream
  (decommissioning candidate). **Guard against false positives on new streams:** only flag idle
  when `CreateTimestamp` age exceeds the idle-stream minimum age in `metrics-thresholds.md`; for
  younger streams note "recently created — insufficient history to judge idleness."

## Operational Excellence
Ref: [Monitoring Amazon Data Firehose](https://docs.aws.amazon.com/firehose/latest/dev/monitoring.html)

- [ ] **CloudWatch error logging** (MEDIUM) — `CloudWatchLoggingOptions.Enabled` = false means
  failures land in the S3 error prefix with no queryable detail (blocks incident diagnosis).
  **This is where the CloudWatch-logging check is reported** — cross-reference the Security angle
  rather than double-reporting.
- [ ] **Tagging / ownership** (LOW) — streams missing ownership and cost-allocation tags (from
  `ListTagsForDeliveryStream`). Note tags only drive cost visibility once **activated as
  cost-allocation tags in the Billing console** — that state isn't readable through this skill's
  APIs, so recommend the user verify activation. **If the user provides an org tagging standard**,
  check completeness against their required keys and flag streams missing any; absent a stated
  standard, flag only fully-untagged streams and suggest a baseline (owner + environment +
  cost-center) rather than asserting specific keys.
- [ ] **Configuration management** (LOW) — config drift from an IaC baseline, or hand-edited
  streams (frequent `LastUpdateTimestamp` changes with no change record); prefer
  CloudFormation/CDK/Terraform-managed streams.
- [ ] **Transform observability** (LOW) — transform-enabled streams without an alarm on
  `ExecuteProcessing.Success` / `.Duration`, or without the Lambda's own logging.
- [ ] **Runbook readiness** (LOW) — failure-prone destinations (Splunk, HTTP endpoint, Snowflake)
  without a documented backup/replay procedure for the S3 error prefix.
- [ ] **Alarm coverage** (MEDIUM when the throttling/freshness alarms are missing) — verified via
  `cloudwatch.DescribeAlarms`. If alarm state could not be read, report "alarm coverage not
  verified" rather than a gap:
  - [ ] Throttling — `ThrottledRecords` alarm per stream
  - [ ] Delivery lag — `DeliveryTo<Dest>.DataFreshness` threshold alarm
  - [ ] Delivery failures — `DeliveryTo<Dest>.Success` (Minimum) alarm
  - [ ] KMS errors — alarm on any `KMSKey*` metric
  - [ ] Quota utilization — alarm approaching per-stream `*PerSecondLimit`

## Sustainability
Ref: [Sustainability Pillar — AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)

Overlaps Cost Optimization — the same efficiency levers reduce spend and footprint. Flag these
with a cross-reference to the Cost items rather than duplicating the rationale; keep severities at
LOW/INFO **unless the waste is "large"** (see the "large waste" definition in
`metrics-thresholds.md`), which raises the finding one severity level.

- [ ] **Data reduction before storage** (LOW) — uncompressed S3 output, or row-oriented (JSON/CSV)
  data that could be columnar (Parquet/ORC). Cross-ref Cost Compression / Format conversion.
- [ ] **Efficient object sizing** (LOW) — many tiny S3 objects (low `PerPartitionThroughput`, high
  `DeliveryToS3.ObjectCount`); right-size buffering. Cross-ref Cost.
- [ ] **Idle streams decommissioned** (INFO) — streams with `IncomingRecords` ≈ 0 hold
  provisioned resources for no workload. Cross-ref Cost Idle streams.
- [ ] **Downstream retention** (INFO) — where Firehose feeds an S3 data lake, recommend S3
  lifecycle/tiering on the delivered prefixes so cold data isn't kept on hot storage
  indefinitely (Firehose doesn't set these, but the review should surface the opportunity).
