---
name: cloudfront-operational-review
description: Comprehensive Amazon CloudFront operational review aligned with the AWS
  Well-Architected Framework and CloudFront best practices. Use this skill when a user
  asks to review, audit, or assess CloudFront distributions or a CDN for best-practices
  compliance, security posture (WAF, TLS, OAC), reliability (origin failover), caching
  and performance, cost optimization, or operational readiness. Triggers on requests
  like "CloudFront review", "CDN audit", "review my distribution", "CloudFront best
  practices", "CloudFront health check", "audit my CloudFront security", "why is my
  CloudFront cache hit ratio low", or "ORR for CloudFront" — even when the user names
  a distribution ID or domain without saying "CloudFront" explicitly.
metadata:
  author: derekzie
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon CloudFront"
  aws-devops-agent-skills.technical-domains: "Networking / Content Delivery"
---

# CloudFront Operational Review

Conduct a read-only operational review of Amazon CloudFront distributions against the
AWS Well-Architected Framework and CloudFront best practices (security, reliability,
performance, cost, operational excellence), producing one report per distribution.

This skill uses only native, **read-only** AWS APIs — `cloudfront`, `cloudwatch`, `logs`,
`wafv2`, `acm`, `ce`, `pricingplanmanager`, and, for origin evidence, `s3`,
`elasticloadbalancing`, and `ec2` describe/get calls. It never calls a mutating API
(`Create*`, `Update*`, `Delete*`, `Put*`, `CreateInvalidation`, `Associate*`, `Tag*`), and uses
no internal tooling or non-AWS MCP servers.

## When to use

Activate when the user asks to review, audit, or assess CloudFront distributions or a CDN;
check CloudFront best practices; evaluate CloudFront security (WAF, TLS, OAC), reliability,
caching/performance, or cost; run a CloudFront operational readiness review (ORR); or
investigate distribution health, high error rates, or low cache hit ratio — even when they
give only a distribution ID or domain.

## Evidence rule

Assign a finding only from evidence you collected. When a check needs data you could not
read (`AccessDenied`, a missing permission, an unreadable bucket, an inaccessible origin
account), record that check as **UNKNOWN — manual verification required**, name the API and
error, and continue with the remaining checks. Never infer a HIGH or CRITICAL result from
CloudFront configuration alone when the catalog says it needs origin-side evidence.

## Review workflow

Work through these steps in order and track progress. CloudFront is global: do not iterate
per region to list distributions, and make `cloudfront`, `cloudwatch`, `wafv2`, `acm`, `logs`
delivery, and `pricingplanmanager` calls in `us-east-1`.

- [ ] Step 1 — Scope: ask which distributions to review (IDs, `*.cloudfront.net` domains,
  CNAMEs, tags, or "all"); default to all distributions in the account.
- [ ] Step 2 — Discover: `cloudfront.ListDistributions` (paginate with `Marker`/`NextMarker`),
  then per distribution `GetDistribution` and `GetDistributionConfig`. Record enablement and
  status, aliases, price class, HTTP version, IPv6, `WebACLId`, each cache behavior (viewer
  protocol policy, allowed and cached methods, compression, cache/origin-request/
  response-headers policy IDs, trusted key groups, function and Lambda@Edge associations,
  `RealtimeLogConfigArn`), each origin (domain, `S3OriginConfig` vs `CustomOriginConfig`, OAC id,
  legacy OAI, protocol/SSL/timeouts, `VpcOriginConfig`, Origin Shield, connection settings),
  each origin group (members and `FailoverCriteria.StatusCodes`), the viewer certificate and
  `MinimumProtocolVersion`, geo restriction, and the legacy `Logging` block.
- [ ] Step 3 — Resolve dependencies: `ListCachePolicies`, `ListOriginRequestPolicies`,
  `ListResponseHeadersPolicies`, `ListOriginAccessControls`,
  `ListCloudFrontOriginAccessIdentities`, `ListFieldLevelEncryptionConfigs`, `ListKeyGroups`,
  `ListFunctions`, `ListVpcOrigins` + `GetVpcOrigin`, and `ListTagsForResource` (parameter
  `Resource` = the distribution ARN).
  - WAF: association comes from `WebACLId` in `GetDistributionConfig` (empty string = no WAF).
    Do not call `wafv2.GetWebACLForResource` — it does not support CloudFront. To inspect the
    ACL's rules, parse the name and ID from the `WebACLId` ARN and call `wafv2.GetWebACL` with
    `Scope=CLOUDFRONT` in `us-east-1`.
  - TLS: `acm.DescribeCertificate` for `ACMCertificateArn`, in `us-east-1`.
- [ ] Step 4 — Origin evidence: for each origin, collect the evidence the catalog requires
  before a security or availability finding. Classify each S3 origin as a REST endpoint
  (`S3OriginConfig`) or a website endpoint (`CustomOriginConfig` with an `s3-website` domain).
  For a REST origin without OAC or OAI, call `s3.GetBucketPolicyStatus` and
  `s3.GetPublicAccessBlock`. For a VPC origin, take the backing resource ARN from
  `GetVpcOrigin.VpcOriginEndpointConfig.Arn` and, in that resource's region, call
  `elbv2.DescribeLoadBalancers` (state and Availability Zones) and `DescribeTargetGroups` +
  `DescribeTargetHealth` for an ALB/NLB, or `ec2.DescribeInstanceStatus` for an EC2 instance.
  When you need the rules for interpreting this evidence, load
  [the findings and severity catalog](references/findings-severity-catalog.md).
- [ ] Step 5 — Logging and monitoring config: `GetMonitoringSubscription` (are additional
  metrics enabled?). Detect standard logging in both forms: the legacy `Logging` block, and
  **standard logging v2** — call `logs.DescribeDeliverySources` in `us-east-1`, select sources
  whose `resourceArns` contains the distribution ARN and `logType` is `ACCESS_LOGS`, then
  `DescribeDeliveries` and `DescribeDeliveryDestinations` to name the destination type
  (CloudWatch Logs, Firehose, or S3). Separately, real-time logs: match each behavior's
  `RealtimeLogConfigArn` against `ListRealtimeLogConfigs`; they deliver to Kinesis Data
  Streams and are not queried with CloudWatch Logs APIs.
- [ ] Step 6 — Metrics (7 days): one `cloudwatch.GetMetricData` per distribution in
  `us-east-1`, namespace `AWS/CloudFront`, dimensions `DistributionId` + `Region=Global`,
  `Period=21600`. Default metrics: Requests, BytesDownloaded, BytesUploaded (Sum) and
  4xxErrorRate, 5xxErrorRate, TotalErrorRate (Average). Only when the monitoring subscription
  is enabled: CacheHitRate and the 401/403/404/502/503/504 ErrorRate metrics (Average), and
  OriginLatency with the percentile stat `p95` (OriginLatency supports only percentile
  statistics; label every value as p95). Load [metric thresholds](references/metrics-thresholds.md)
  when you interpret these values or the 504 origin-failure triage.
- [ ] Step 7 — Alarm coverage: call `cloudwatch.DescribeAlarms` in `us-east-1` with
  `AlarmTypes` set to `MetricAlarm` and `CompositeAlarm` (paginate). A distribution is covered
  for a metric when a metric alarm references it directly, when a metric-math alarm's
  `Metrics[].MetricStat` references it, or when a composite alarm's `AlarmRule` includes such an
  alarm. Do not rely on `DescribeAlarmsForMetric` alone; it omits metric-math and composite
  alarms. Assess OriginLatency and CacheHitRate alarms only when additional metrics are enabled.
- [ ] Step 8 — Logs (7 days): if a standard-log destination is readable, scan for
  `x-edge-result-type` = Error, `sc-status` 502/503/504, `504` with `NonS3OriginCommError`, and
  deprecated `ssl-protocol` (TLSv1/TLSv1.1). If additional metrics are off, approximate cache hit
  ratio from these logs using only cacheable requests, as defined in
  [metric thresholds](references/metrics-thresholds.md), and label it as log-derived.
- [ ] Step 9 — Change context: read `LastModifiedTime` from `GetDistribution`; if CloudTrail
  access is in scope, correlate `UpdateDistribution`, WAF, and ACM changes from the last 14
  days. If CloudTrail is unavailable, say so in the report.
- [ ] Step 10 — Cost (once per review): first call `pricingplanmanager.ListSubscriptions` in
  `us-east-1` and note which distributions sit in a flat-rate plan (`resourceArns`, `planTier`).
  Then call `costexplorer.GetCostAndUsage` for 3 months, Service = "Amazon CloudFront", grouped by
  `USAGE_TYPE`, and report the **account-level** total and its main usage types. Per
  distribution, report usage drivers only (BytesDownloaded, Requests, price class, cache hit
  ratio) — do not invent a dollar split. Report per-distribution dollars only when the data
  exposes the distribution as a resource: `ce.GetCostAndUsageWithResources` (requires
  resource-level data enabled in Cost Explorer; last 14 days only) or the CloudFront usage
  report's `Resource` column. For flat-rate distributions, do not present per-GB or per-request
  savings; assess cost against the plan's usage allowance instead.
- [ ] Step 11 — Analyze by pillar: before assigning any severity, load
  [the findings and severity catalog](references/findings-severity-catalog.md) and label each
  finding CRITICAL, HIGH, MEDIUM, LOW, INFO, or UNKNOWN using its criteria. Cover **Security**,
  **Reliability** (including whether origin failover actually applies to the behavior's
  methods), **Performance**, **Cost Optimization**, and **Operational Excellence**.
- [ ] Step 12 — Validate, then report: run the self-check below, then produce one report per
  distribution by loading [the report template](assets/report-template.md) and filling in every
  section. Save each report as `cloudfront-review-<distribution-id>-<YYYY-MM-DD>.md`.

## Validate your output before presenting

For each report, confirm before showing it to the user:

- every severity matches the criteria in `references/findings-severity-catalog.md`;
- every finding cites data you actually collected (a metric value, config field, API
  response, or log signal) — downgrade unsupported claims to UNKNOWN or remove them;
- no HIGH or CRITICAL origin-security or origin-health finding rests on CloudFront config alone;
- metric readings came from `us-east-1` with `Region=Global`, and OriginLatency is labeled p95;
- no "missing alarm" finding ignores metric-math or composite alarms, and no OriginLatency or
  CacheHitRate alarm is recommended while additional metrics are disabled;
- logging status reflects legacy logging, logging v2 deliveries, and real-time logs separately;
- the cost section contains no per-distribution dollar figure unless it came from resource-level
  billing data;
- every check blocked by an access error appears as UNKNOWN with the API and error named;
- every template section is filled in or explicitly marked "not applicable";
- the filename is exactly `cloudfront-review-<distribution-id>-<YYYY-MM-DD>.md`.

Fix any mismatch before presenting.

## Severity labels

- **CRITICAL** — immediate risk to availability, security, or data integrity (fix in 24–48h)
- **HIGH** — significant gap that could cause incidents (fix within a week)
- **MEDIUM** — notable improvement opportunity (plan within 30 days)
- **LOW** — minor hardening or optimization (when convenient)
- **INFO** — observation, no action required
- **UNKNOWN** — evidence could not be collected; manual verification required

## Known API quirks

- CloudFront is global; `cloudfront.*` uses the global endpoint (SDKs sign to `us-east-1`).
- CloudWatch metrics live in `us-east-1` with `Region=Global`; additional metrics exist only with
  a monitoring subscription. OriginLatency accepts only percentile stats (`p95` in
  `GetMetricData`, `ExtendedStatistics` in `GetMetricStatistics`).
- `wafv2.GetWebACLForResource` does not support CloudFront; use `WebACLId`, then
  `wafv2.GetWebACL` with `Scope=CLOUDFRONT` in `us-east-1` if you need the rules.
- Standard logging v2 is configured through CloudWatch Logs delivery APIs in `us-east-1`, not
  through `DistributionConfig.Logging`; a distribution can have v2 logging with the legacy block
  disabled.
- VPC origins are regional resources; resolve their backing ALB/NLB/EC2 health in that region.
- `cloudfront.ListTagsForResource`'s parameter is `Resource` (the ARN), not `ResourceName`.
- CloudFront list APIs paginate with `Marker`/`NextMarker`, not `NextToken`.

## Data source boundaries

Read-only describe/get/list calls only. No mutating calls, no internal tooling, no non-AWS MCP
servers. If a log destination, bucket, or origin account is not readable, record the affected
checks as UNKNOWN and rely on CloudWatch metrics where they apply.
