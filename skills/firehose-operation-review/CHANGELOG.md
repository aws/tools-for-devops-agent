# Changelog

## [1.4.0] - 2026-09-24
### Changed
- Addressed best-practices evaluation finding **BP-03 (detailed reference materials must not be in body)** by applying progressive disclosure to the two content areas the evaluator flagged:
  - **Step 3 (metrics):** removed the inline CloudWatch metric tables (core ingestion, source-specific, per-destination delivery, and feature metrics). `SKILL.md` now instructs which metric *groups* to pull based on the stream's source/destination/enabled features and defers every metric name, statistic, and Normal/Warning/Critical band to `references/metrics-thresholds.md` (which already held them, in richer form)
  - **Step 4 (pillar checks):** removed the verbose per-pillar bullet lists (old §4.1–4.7) that restated each check with its severity inline. The pillar checks now direct the agent to work `references/best-practices-checklist.md` item by item as the canonical list; the body retains only the cross-pillar procedural rules (Service Quotas read from `GetServiceQuota`; Sustainability cross-reference + large-waste escalation) and the Cost "Est. Impact" estimation *procedure* (analysis logic, not a lookup table)
- Moved each check's **base severity, escalation conditions, and judgment rules** (customer-managed-KMS data-classification escalation, the "state the fact, don't judge" rule for `Resource: "*"` IAM grants, Redshift-COPY vs Firehose root-causing, Iceberg landing reconciliation, and the "report CloudWatch error logging once under Operational Excellence" cross-reference) into `references/best-practices-checklist.md` so no analysis detail was lost in the move
- Restored the **dynamic-partitioning key-extraction failure** check (JQ expression/record-format errors, `JQProcessing.Duration`, reconcile the S3 error prefix against `IncomingRecords`) into the checklist's Reliability section

## [1.3.0] - 2026-09-24
### Changed
- Addressed best-practices evaluation findings (BP-12, BP-16, BP-04/BP-05):
  - **BP-16 (step-by-step guidance):** added a top-level `- [ ]` checkbox "Review Checklist" summarizing Steps 1–6 so the multi-step workflow uses checklist format, not just `## Step N:` headings
  - **BP-12 (templates must not be in body):** moved the full Step 5 report template out of `SKILL.md` into `assets/report-template.md`, loaded conditionally via `read_skill_resource`; Step 5 now keeps only a brief summary plus a load-failure fallback
  - **BP-04/BP-05 (reference links + when to load):** the thresholds and best-practices-checklist references and the new report template are now cited with markdown links (`[references/…](references/…)`, `[assets/report-template.md](assets/report-template.md)`) at their load points, each with an explicit "when to load" condition
- Data Source Boundaries note updated to mention the skill's `assets/` files alongside `references/`

## [1.2.0] - 2026-09-23
### Changed
- Defined previously-vague judgment thresholds concretely and single-sourced them in the `references/metrics-thresholds.md` "Derived / tunable thresholds" table: **"sustained"** = ≥ 3 consecutive datapoints; **"climbing monotonically"/stalled** = non-decreasing across ≥ 6 consecutive 5-min datapoints (~30 min); **"majority of streams"** = ≥ 60% of in-scope streams; **"large waste"** = ≥ 25% of a stream's estimated monthly delivered-storage cost or ≥ 100 GB/month avoidable; quota Critical band tightened to ≥ 90%. SKILL.md data-freshness, Iceberg "approaching the limit", account-rollup, and Sustainability wording now reference these definitions
- Cost estimation hardened: never blocks on interactive pricing input (unattended runs skip straight to defaults); public on-demand list prices are the labeled default path, not a last resort; `pricing.GetProducts` `AccessDenied`/absence now degrades to a labeled list-price estimate instead of omitting the cost figure; compression ratio explicitly labeled a static default to refine from observed data where possible
- Security judgment language replaced with objective signals: customer-managed-KMS finding escalates to MEDIUM only on a data-classification tag or user-stated compliance scope (else INFO + factual statement); IAM `*`-resource scoping reported as a factual INFO finding with the least-privilege alternative rather than a "without justification" judgment
- Alarm coverage evaluated per-Region with partial-result handling: a `cloudwatch:DescribeAlarms` denial in one Region marks only that Region "not verified" and never suppresses results or infers a gap in Regions where the call succeeds
- Step 1 scope parsing: added a canonical pillar-alias list (security, reliability, performance, service-quotas, cost, operational-excellence, sustainability with accepted aliases) so free-text scoping doesn't misfire

## [1.1.0] - 2026-09-23
### Added
- Step 6 "Track Findings Over Time" — recurring/scheduled runs diff against the prior report artifact for the same scope and lead with a New / Resolved / Persistent (with severity changes) summary; matches findings by stable key (stream + pillar + check) and degrades to "baseline review" when no prior run exists
- Dynamic-partitioning key-extraction failure check (JQ expression / record-format errors route records to the S3 error prefix; watch `JQProcessing.Duration` and reconcile the error prefix against `IncomingRecords`)
- Explicit per-destination delivery-success metric naming (`DeliveryToS3`/`Redshift`/`AmazonOpenSearchService`/`AmazonOpenSearchServerless`/`Splunk`/`HttpEndpoint`/`Snowflake`/`Iceberg`), with a note that `DeliveryToElasticsearch.*` does not exist (service renamed)
- Conditional org-tagging-standard check (validate against user-provided required keys such as team/environment/cost-center; otherwise flag only fully-untagged streams)

### Changed
- Moved tunable numeric thresholds (quota-utilization 75%/near-100% bands, idle-stream 14-day minimum age, throttle-rate 1%/5%) into a single "Derived / tunable thresholds" table in `references/metrics-thresholds.md`; SKILL.md now references the bands instead of restating numbers
- Clarified that `evals/files/firehose-context.json` is an evaluation fixture, not a runtime input — real reviews (interactive/scheduled/automated) never read it, so no unattended-run fallback is required for it

## [1.0.0] - 2026-09-17
### Added
- Initial release
- Comprehensive Amazon Data Firehose (formerly Kinesis Data Firehose) operational review aligned with the AWS Well-Architected Framework and Firehose best practices
- Seven review pillars: Security, Reliability, Performance, Service Quotas, Cost Optimization, Operational Excellence, and Sustainability (with the overall review framed as a best-practices assessment rather than a separate "Best Practices" pillar)
- Operational Excellence pillar: CloudWatch error logging, alarm coverage (via `cloudwatch.DescribeAlarms`), tagging/ownership, IaC-managed configuration, transform observability, and error-prefix runbook readiness
- Sustainability pillar: data reduction (compression/columnar), efficient object sizing, idle-stream decommissioning, and downstream S3 retention/tiering — cross-referenced with Cost Optimization since the levers overlap
- Resource discovery across delivery streams: source type (Direct PUT, Kinesis Data Streams, MSK), destination (S3, Redshift, OpenSearch Service, OpenSearch Serverless, Splunk, HTTP endpoint, Snowflake, Apache Iceberg), buffering hints, compression, encryption, backup mode, data transformation, and format conversion
- Empty-region detection based on `ListDeliveryStreams` results
- CloudWatch metric collection and threshold-based classification (Normal/Warning/Critical) in the `AWS/Firehose` namespace, selected per stream source and destination
- Service quota utilization analysis (streams per Region, per-stream records/bytes/PUT throughput, Iceberg-table caps) via the Service Quotas API and `*PerSecondLimit` metrics
- Reliability checks driven by data freshness, delivery success ratio, S3 backup mode, retry duration, source read lag, and transform/conversion failures
- Iceberg delivery-correctness caveat: delivery metrics and the S3 error prefix are necessary-but-not-sufficient for Iceberg destinations (records must be one JSON object per record; aggregated/compressed sources like CloudWatch Logs subscription filters may not land), so the skill recommends an independent ingested-vs-table row-count reconciliation and upstream decompression/split
- Removed the hardcoded Iceberg throughput numbers entirely (Step 4.4, Region-Restricted Checks, and metrics-thresholds.md) in favor of "call `servicequotas.GetServiceQuota` and cite the returned value" — no stale reference figure to fall back on
- Cost-estimate rate sourcing: named the unit-rate source order (user negotiated/EDP rate → current public on-demand rates labeled as rough estimates → optional `pricing.GetProducts`, which is not in the default managed policy); every dollar figure must state its rate source
- Added Redshift-specific delivery-failure check (paused/resized cluster, invalid COPY IAM role, `STL_LOAD_ERRORS` cluster-side) distinct from generic delivery-success
- Added multi-region/DR posture as an INFO architecture consideration (Firehose has no native cross-region delivery; not API-verifiable)
- Tagging check now notes cost-allocation tags must be activated in Billing (not readable via the skill's APIs — recommend user verifies in Billing/Cost Explorer)
- Noted the Severity Definitions table is the single source of truth for SLAs; inline severity tags reference it rather than restating SLAs
- Reference-load resilience: if a `read_skill_resource` call for the thresholds reference or best-practices checklist fails, the skill now states the gap at the top of the report and continues on general guidance rather than silently proceeding
- Step 1: added an unattended/scheduled-run rule — proceed with full default scope (all accounts/regions/streams, all pillars, 7-day window) instead of waiting for scope input when there is no interactive user
- Step 2: clarified multi-account mechanics — the skill operates within accounts the Agent Space is configured to access (no self-assumed roles / Org enumeration); accounts not associated with the Space are reported as inaccessible
- Security (4.1): added an access-control-beyond-the-delivery-role check (broad `firehose:PutRecord*`/admin grants; tag-based ABAC consistency)
- Cost (4.5): clarified that Firehose base per-GB ingestion cost is excluded from the optimization estimates (the levers change downstream cost, not ingested volume)
- Idle-stream detection now guards against false positives on new streams — only flag idle when `CreateTimestamp` age > ~14 days
- Cost optimization checks: compression, columnar format conversion, buffer sizing, dynamic partitioning efficiency, and idle-stream detection
- Severity-ranked findings (CRITICAL, HIGH, MEDIUM, LOW, INFO) and a shareable Markdown report artifact
- AWS-API-only data collection (Firehose, CloudWatch, Service Quotas) with no data-plane record puts and no delivered content read
- Stream-status guard: only ACTIVE streams get full analysis; CREATING/DELETING are skipped and CREATING_FAILED is surfaced as a reliability finding
- Cross-account / PrivateLink destination checks for OpenSearch, Redshift, and HTTP destinations
- CloudWatch alarm-coverage check backed by `cloudwatch.DescribeAlarms` for `ThrottledRecords` and `DeliveryTo<Dest>.DataFreshness`
- Iceberg-table throughput treated as a verify-against-current-quota check (via `servicequotas.GetServiceQuota` / docs, with `AppendOnly` auto-scaling and the throughput-vs-partitions tradeoff noted) rather than a hardcoded cap
- Rough cost-impact estimation guidance for the Cost Optimization pillar (monthly volume extrapolation, compression/columnar downstream savings, small-object PUT cost)
- Account-level rollup section in the report for multi-stream / multi-region reviews
- Reference files: best-practices checklist and CloudWatch metric thresholds
- Threshold-reference precision fixes: labeled the throttle-rate/utilization thresholds (1%/5%/75%) as skill heuristics rather than AWS-published numbers; guarded against reporting 0% utilization when `*PerSecondLimit` emits no datapoints (new/idle streams); added OpenSearch Service/Serverless `AuthFailure`/`DeliveryRejected` metrics and clarified there are no OCU-specific `AWS/Firehose` metrics; added a Snowflake "check Snowflake-side monitoring" caveat; gave the BackupToS3, dynamic-partitioning `PerPartitionThroughput`/`ObjectCount`, and Kinesis-source throttle metrics concrete Normal/Warning/Critical anchors; de-duplicated the Iceberg-throughput caveat to live only in `metrics-thresholds.md` with a one-line pointer from `SKILL.md`
- Evaluation test cases: 6 trigger/no-trigger queries (`eval_queries.json`) and 6 functional assertion cases (`evals.json`) with a context fixture (`files/firehose-context.json`); benchmark/report artifacts are generated by running the eval tool against a live Agent Space
