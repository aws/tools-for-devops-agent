# Amazon Data Firehose Best Practices Checklist

Organized by pillar. Maps directly to the checks in `SKILL.md` Step 4.

## Security

- [ ] **Encryption at rest** — SSE enabled on Direct PUT streams; for Kinesis-sourced streams the source data stream is encrypted
- [ ] **Customer-managed KMS key** used for sensitive-data workloads (rotation control + audit trail) rather than the AWS-owned key
- [ ] **Destination S3 encryption** — S3/Extended-S3 objects written with KMS encryption
- [ ] **KMS key health** — no `KMSKeyAccessDenied` / `KMSKeyDisabled` / `KMSKeyInvalidState` / `KMSKeyNotFound` events
- [ ] **IAM role scoping** — delivery role scoped to the specific destination, transform Lambda, and KMS key; resource `*` justified and documented
- [ ] **Access control beyond the delivery role** — `firehose:PutRecord*` / admin grants on the stream ARN not overly broad; delivery-stream tags consistent where used for ABAC/policy conditions
- [ ] **VPC / private connectivity** — OpenSearch/Redshift destinations use a VPC configuration where appropriate
- [ ] **Cross-account / PrivateLink destinations** — cross-account OpenSearch/Redshift/HTTP destinations use a VPC/PrivateLink path (not the public internet) and a delivery role + resource policy scoped to the specific cross-account resource
- [ ] **HTTP endpoint destinations** — HTTPS (TLS) only; access key stored securely
- [ ] **CloudWatch error logging** enabled so delivery/transform errors can be diagnosed

## Reliability

- [ ] **Data freshness** — `DeliveryTo<Dest>.DataFreshness` stays below buffering interval + retry window; not climbing monotonically
- [ ] **Delivery success ratio** — `DeliveryTo<Dest>.Success` at/near 1.0
- [ ] **S3 backup for failed records** — `S3BackupMode` configured (at least `FailedDataOnly`) for Redshift/OpenSearch/Splunk/HTTP/Snowflake destinations
- [ ] **Retry duration** — destination `RetryOptions.DurationInSeconds` sized to ride out transient failures
- [ ] **Source read lag** — Kinesis `KinesisMillisBehindLatest` / MSK `KafkaOffsetLag` low; no sustained `DataReadFromSource.Backpressured`
- [ ] **Transform Lambda health** — `ExecuteProcessing.Success` at/near 1.0; duration well under timeout
- [ ] **Format conversion** — `FailedConversion.Records` at 0
- [ ] **Redshift COPY health** — for Redshift destinations, `DeliveryToRedshift.Success` at/near 1.0; cluster available (not paused/resizing), COPY IAM role valid; check `STL_LOAD_ERRORS` cluster-side, not just `AWS/Firehose`
- [ ] **Iceberg landing verified** — for Iceberg destinations, ingested count reconciled against actual table row count; source emits one JSON object per record (decompressed/split upstream)
- [ ] **Multi-region / DR posture** (INFO, not API-verifiable) — for business-critical streams, a regional-failover path is considered (Firehose has no native cross-region delivery)

## Performance

- [ ] **Throttling** — `ThrottledRecords` at 0; ingestion within `*PerSecondLimit`
- [ ] **Buffering hints** tuned to balance delivery latency (freshness target) against object size
- [ ] **Splunk ack latency** — `DeliveryToSplunk.DataAckLatency` stable (no rising trend)
- [ ] **Dynamic partitioning** — `PartitionCountExceeded` at 0; `PartitionCount` below `ActivePartitionsLimit` (default 500)

## Service Quotas

- [ ] **Streams per Region** — count < 75% of the per-Region quota (default 50)
- [ ] **Per-stream throughput** — observed P95 records/s, bytes/s, and PUT/s < 75% of the `*PerSecondLimit` values
- [ ] **Iceberg-table throughput** — within the current per-stream Iceberg limit (verify via `servicequotas.GetServiceQuota` / docs; do not assume a fixed number)
- [ ] **CloudWatch alarms** configured on `ThrottledRecords` and `DeliveryTo<Dest>.DataFreshness` (verified via `cloudwatch.DescribeAlarms`)

## Cost Optimization

- [ ] **Compression** — S3/Extended-S3 destinations use GZIP/Snappy/Zip rather than UNCOMPRESSED
- [ ] **Columnar format conversion** — S3 data queried by Athena/EMR/Redshift Spectrum stored as Parquet/ORC
- [ ] **Buffering sized for fewer, larger objects** — high-volume S3 streams not producing many tiny objects
- [ ] **Dynamic partitioning efficiency** — partition keys not producing many fragmented low-throughput partitions
- [ ] **Idle streams** — streams with ~0 `IncomingRecords` over the window reviewed for decommissioning, but only flagged idle when `CreateTimestamp` age > ~14 days (avoid false positives on new streams)

## Operational Excellence

- [ ] **CloudWatch error logging** — `CloudWatchLoggingOptions.Enabled` = true so delivery/transform errors are diagnosable
- [ ] **Tagging / ownership** — streams carry ownership and cost-allocation tags
- [ ] **Configuration management** — streams managed via IaC (CloudFormation/CDK/Terraform), not hand-edited
- [ ] **Transform observability** — transform-enabled streams have alarms on `ExecuteProcessing.Success`/`.Duration` and Lambda logging
- [ ] **Runbook readiness** — a documented backup/replay procedure exists for the S3 error prefix on failure-prone destinations
- [ ] **Alarm coverage** (verified via `cloudwatch.DescribeAlarms`):
  - [ ] Throttling — `ThrottledRecords` alarm per stream
  - [ ] Delivery lag — `DeliveryTo<Dest>.DataFreshness` threshold alarm
  - [ ] Delivery failures — `DeliveryTo<Dest>.Success` (Minimum) alarm
  - [ ] KMS errors — alarm on any `KMSKey*` metric
  - [ ] Quota utilization — alarm approaching per-stream `*PerSecondLimit`

## Sustainability

Overlaps Cost Optimization — the same efficiency levers reduce spend and footprint.

- [ ] **Data reduction before storage** — compression on, columnar format where the S3 data is queried (less data stored/scanned)
- [ ] **Efficient object sizing** — buffering right-sized so streams aren't emitting many tiny objects
- [ ] **Idle streams decommissioned** — no provisioned streams sitting idle
- [ ] **Downstream retention** — S3 lifecycle/tiering recommended on delivered prefixes so cold data isn't kept on hot storage
