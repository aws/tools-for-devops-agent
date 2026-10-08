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
`wafv2`, `acm`, `ce`. It never calls a mutating API (`Create*`, `Update*`, `Delete*`,
`CreateInvalidation`, `Associate*`, `Tag*`), and uses no internal tooling or non-AWS MCP
servers.

## When to use

Activate when the user asks to review, audit, or assess CloudFront distributions or a CDN;
check CloudFront best practices; evaluate CloudFront security (WAF, TLS, OAC), reliability,
caching/performance, or cost; run a CloudFront operational readiness review (ORR); or
investigate distribution health, high error rates, or low cache hit ratio — even when they
give only a distribution ID or domain.

## Review workflow

Work through these steps in order and track progress. CloudFront is global: do not iterate
per region to list distributions, and query all CloudWatch metrics in `us-east-1`.

- [ ] Step 1 — Scope: ask which distributions to review (IDs, `*.cloudfront.net` domains,
  CNAMEs, tags, or "all"); default to all distributions in the account.
- [ ] Step 2 — Discover: `cloudfront.ListDistributions` (paginate with `Marker`/`NextMarker`),
  then per distribution `GetDistribution` and `GetDistributionConfig`. Record enablement and
  status, aliases, price class, HTTP version, IPv6, `WebACLId` (empty means no WAF), each
  cache behavior (viewer protocol policy, compression, cache/origin-request/response-headers
  policy IDs, trusted key groups, CloudFront Functions and Lambda@Edge associations), each
  origin and origin group (OAC id, legacy OAI, custom-origin protocol/SSL/timeouts, VPC origin
  config, Origin Shield, connection settings), the viewer certificate and
  `MinimumProtocolVersion`, geo restriction, and standard-logging config.
- [ ] Step 3 — Resolve dependencies: `ListCachePolicies`, `ListOriginRequestPolicies`,
  `ListResponseHeadersPolicies`, `ListOriginAccessControls`,
  `ListCloudFrontOriginAccessIdentities`, `ListFieldLevelEncryptionConfigs`, `ListKeyGroups`,
  `ListFunctions`, `ListVpcOrigins` + `GetVpcOrigin`, and `ListTagsForResource` (its parameter
  is `Resource` = the distribution ARN). For WAF and TLS, call `wafv2.GetWebACLForResource`
  with `Scope=CLOUDFRONT` and `acm.DescribeCertificate` — both from `us-east-1`.
- [ ] Step 4 — Logging/monitoring config: `GetMonitoringSubscription` (are additional metrics
  enabled?) and `ListRealtimeLogConfigs`; note whether standard access logging is on and where
  it writes.
- [ ] Step 5 — Metrics (7 days): one `cloudwatch.GetMetricData` per distribution in
  `us-east-1`, namespace `AWS/CloudFront`, `Period=21600`. Default metrics (dimensions
  `DistributionId` + `Region=Global`): Requests, BytesDownloaded, BytesUploaded, 4xxErrorRate,
  5xxErrorRate, TotalErrorRate. Additional metrics (only when the monitoring subscription is
  enabled): CacheHitRate, OriginLatency, and 401/403/404/502/503/504 ErrorRate. Also call
  `DescribeAlarmsForMetric` for 5xxErrorRate, TotalErrorRate, OriginLatency, and CacheHitRate.
  When you need the per-metric warning/critical thresholds, alarm-coverage expectations, or
  the 504 origin-failure triage table to interpret these numbers, load
  [metric thresholds](references/metrics-thresholds.md).
- [ ] Step 6 — Logs (7 days): if standard logging is on and the log bucket or a log table is
  readable, scan for `x-edge-result-type` = Error or a high Miss ratio, `sc-status` 502/503/504,
  `504` with `NonS3OriginCommError`, and deprecated `ssl-protocol` (TLSv1/TLSv1.1). If
  additional metrics are off, derive cache hit ratio from these logs. For the log-signal
  severities and the timeout-vs-refused-vs-TLS 504 breakdown, load
  [metric thresholds](references/metrics-thresholds.md) if you have not already.
- [ ] Step 7 — Change context: read `LastModifiedTime` from `GetDistribution`; if CloudTrail
  access is in scope, correlate `UpdateDistribution`, WAF, and ACM changes from the last 14
  days. If CloudTrail is unavailable, say so in the report.
- [ ] Step 8 — Cost (once per review): `costexplorer.GetCostAndUsage` for 3 months, grouped by
  `USAGE_TYPE`, filtered to Service = "Amazon CloudFront". Cost Explorer has no per-distribution
  breakdown, so attribute proportionally by each distribution's 7-day BytesDownloaded + Requests
  share and label the figures as estimates.
- [ ] Step 9 — Analyze by pillar: evaluate every distribution across **Security** (WAF attached;
  `MinimumProtocolVersion` ≥ TLSv1.2_2021; viewer protocol redirect-to-https or https-only; OAC
  vs public S3 origin; field-level encryption; signed URLs/cookies; geo restriction; custom vs
  default certificate), **Reliability** (origin failover / origin groups; custom- and
  VPC-origin health; 5xx/origin-error trend), **Performance** (cache hit ratio; cache-key
  hygiene; compression; HTTP/2 and HTTP/3; Origin Shield; origin latency; price class vs
  audience), **Cost Optimization** (price class; cache efficiency; idle or disabled
  distributions; cost-allocation tags), and **Operational Excellence** (alarms on
  5xx/TotalError/OriginLatency/CacheHitRate; standard logging; monitoring subscription;
  real-time logs; tags; default root object). Before assigning any severity, load
  [the findings and severity catalog](references/findings-severity-catalog.md) and label each
  finding CRITICAL, HIGH, MEDIUM, LOW, or INFO using its criteria.
- [ ] Step 10 — Validate, then report: run the self-check below, then produce one report per
  distribution by loading [the report template](assets/report-template.md) and filling in every
  section. Save each report as `cloudfront-review-<distribution-id>-<YYYY-MM-DD>.md`.

## Validate your output before presenting

For each report, confirm before showing it to the user:

- every severity matches the criteria in `references/findings-severity-catalog.md`;
- every finding cites data you actually collected (a specific metric value, config field, or
  log signal) — remove any unsupported claim;
- metric readings came from `us-east-1` using the `Region=Global` dimension;
- every template section is filled in or explicitly marked "not applicable";
- the filename is exactly `cloudfront-review-<distribution-id>-<YYYY-MM-DD>.md`.

Fix any mismatch before presenting.

## Severity labels

- **CRITICAL** — immediate risk to availability, security, or data integrity (fix in 24–48h)
- **HIGH** — significant gap that could cause incidents (fix within a week)
- **MEDIUM** — notable improvement opportunity (plan within 30 days)
- **LOW** — minor hardening or optimization (when convenient)
- **INFO** — observation, no action required

## Known API quirks

- CloudFront is global; `cloudfront.*` uses the global endpoint (SDKs sign to `us-east-1`).
  Don't loop per region to list distributions.
- CloudWatch metrics live in `us-east-1`; default and additional metrics both use the
  `Region=Global` dimension, and additional metrics exist only with a monitoring subscription.
- `wafv2.GetWebACLForResource` uses `Scope=CLOUDFRONT` from `us-east-1`; `acm.DescribeCertificate`
  for a CloudFront certificate must also run in `us-east-1`.
- VPC origins are a regional resource even though the distribution is global — resolve their
  backing ALB/NLB health in that region.
- `cloudfront.ListTagsForResource`'s parameter is `Resource` (the ARN), not `ResourceName`.
- CloudFront list APIs paginate with `Marker`/`NextMarker`, not `NextToken`.

## Data source boundaries

Read-only `cloudfront`, `cloudwatch`, `logs`, `wafv2`, `acm`, and `ce` only. No mutating
CloudFront calls, no internal tooling, no non-AWS MCP servers. If the standard access-log
bucket is not readable, note the limitation in the report and rely on CloudWatch metrics.
