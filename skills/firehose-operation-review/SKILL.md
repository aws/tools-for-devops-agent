---
name: firehose-operation-review
description: 'Comprehensive Amazon Data Firehose (formerly Kinesis Data Firehose) review aligned with the AWS Well-Architected Framework and Firehose best practices. Use this skill when a user asks to review, audit, or assess Amazon Data Firehose delivery streams for best-practices compliance, security posture, reliability, delivery health, performance, cost optimization, service quotas, operational excellence, or sustainability. Triggers on requests like "Firehose review", "Kinesis Firehose best practices audit", "review my delivery streams", "Firehose health check", "why is my Firehose lagging", "Firehose delivery failures", "Firehose cost optimization review", or "ORR for Firehose".'
metadata:
  author: stharolz
  version: "1.4.0"
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

## Review Checklist

Work through these steps in order — each depends on the outputs of the ones before it.
Track progress against this checklist and do not skip a step unless its scope makes it
inapplicable (e.g. a single-stream review skips the account rollup).

- [ ] Step 1: Identify target scope (accounts, regions, streams, pillars, window)
- [ ] Step 2: Discover Firehose resources and capture per-stream config
- [ ] Step 3: Collect CloudWatch metrics (load the thresholds reference first)
- [ ] Step 4: Analyze against best practices (load the checklist reference first)
- [ ] Step 5: Generate the report (load the report template)
- [ ] Step 6: Track findings over time (recurring reviews)

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

**Before querying metrics**, and whenever classifying a metric value as Normal, Warning,
or Critical in this step or Step 4, load the authoritative thresholds reference —
[references/metrics-thresholds.md](references/metrics-thresholds.md) — with:
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
publishes metrics at 1-minute granularity, and `GetMetricData` allows up to 500
metric-data queries per call — batch requests and paginate when a region has many streams.

**Select which metrics to pull from the stream's source and destination (Step 2), then
use the thresholds reference as the authoritative catalog.** `metrics-thresholds.md`
lists every metric — by group (ingestion, source-specific for Kinesis/MSK, per-destination
delivery, backup-to-S3, and feature metrics for transform / format conversion / dynamic
partitioning / SSE / CloudWatch-Logs decompression) — with its statistic and its
Normal/Warning/Critical bands. Pull only the groups that apply:
- **Always**: the ingestion metrics (volume, `ThrottledRecords`, the `*PerSecondLimit`
  metrics).
- **By source**: the Kinesis-source or MSK-source metric group.
- **By destination**: the `DeliveryTo<Dest>.*` group for the stream's one active
  destination (`<Dest>` ∈ `S3`, `Redshift`, `AmazonOpenSearchService`,
  `AmazonOpenSearchServerless`, `Splunk`, `HttpEndpoint`, `Snowflake`), plus `BackupToS3.*`
  when backup is enabled.
- **By enabled feature**: the transform, format-conversion, dynamic-partitioning, SSE, or
  decompression group — only when Step 2 showed that feature is on.

Do not hand-copy metric names from memory; take them and their bands from the loaded
reference so the classification is consistent across runs.

**Alarm coverage.** To evaluate the alarm-coverage checks (the Service Quotas and
Operational Excellence items in the best-practices checklist), call
`cloudwatch.DescribeAlarms` and match alarms whose
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

**Before evaluating findings**, load the best-practices checklist —
[references/best-practices-checklist.md](references/best-practices-checklist.md) — with:
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

Each checklist item carries a **base severity** (and any escalation conditions); the
**Severity Definitions** table (near the end of this file) is the single source of truth
for what each level *means* and its remediation SLA. If an SLA changes, update that table
only.

### Pillar checks: Security, Reliability, Performance, Service Quotas, Operational Excellence, Sustainability

For these six pillars, **work the loaded `references/best-practices-checklist.md` item by
item** — it is the canonical list of checks, and it carries each check's base severity,
escalation conditions, and the judgment rules that must be applied verbatim (e.g. the
customer-managed-KMS data-classification escalation, the "state the fact, don't judge it"
rule for `Resource: "*"` IAM grants, the Redshift-COPY vs Firehose root-causing, Iceberg
landing reconciliation, and the "report CloudWatch error logging once under Operational
Excellence" cross-reference). Classify every metric value against the bands in
`references/metrics-thresholds.md`. Do not re-derive checks or severities from memory —
apply the reference so two runs of the same stream agree.

Two procedural rules that span the pillars:
- **Service Quotas**: read every quota value from `servicequotas.GetServiceQuota` and the
  `*PerSecondLimit` CloudWatch metrics — never hardcode the Region-dependent defaults —
  then apply the Warning/Critical bands from the *Service Quota Utilization* table.
- **Sustainability** overlaps Cost Optimization: cross-reference the Cost items rather than
  duplicating rationale, and raise a finding one severity level only when the waste is
  "large" per `references/metrics-thresholds.md`.

### Cost Optimization — impact-estimation procedure
Ref: [Amazon Data Firehose pricing](https://aws.amazon.com/firehose/pricing/)

The Cost checklist items (compression, columnar conversion, buffering, dynamic-partitioning
efficiency, idle streams) live in `references/best-practices-checklist.md`. This section is
the **procedure for the "Est. Impact" column** those findings reference — it stays in the
body because it is analysis logic, not a lookup table.

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

## Step 5: Generate Report

Generate a shareable Markdown report artifact for the review. **Before writing the
report, load the report template** — [assets/report-template.md](assets/report-template.md)
— and follow its section order and tables exactly:
```
read_skill_resource(skill_id="firehose-operation-review", path="assets/report-template.md")
```
The template covers the artifact naming convention, header, executive summary, the
"Change Since Last Review" diff (Step 6), the account-level rollup, per-pillar findings
tables, configuration and metrics summaries, quota utilization, the combined
cost/sustainability opportunities table, the priority matrix, next steps, and the
reference-links appendix. Populate every applicable section and omit the ones the
template marks as scope-dependent (e.g. skip the account rollup for a single-stream
review).

**If this `read_skill_resource` call fails**, note it at the top of the report —
"⚠️ report template (`assets/report-template.md`) could not be loaded; report structure
follows the skill's general guidance" — and still produce the standard sections
(header, executive summary, findings by pillar, configuration, metrics, quotas, cost,
priority matrix, next steps).

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
and its own `references/` and `assets/` files. `evals/files/firehose-context.json` is an **evaluation
fixture** used solely by the skill-evaluation harness — it is **not** a runtime input and
is not read during an actual review (interactive, scheduled, or automated). If it is
absent or unreadable, real reviews are unaffected; only eval runs that reference it would
skip those fixture-backed cases. There is therefore no unattended-run fallback needed for
this file.
