# CloudFront Operational Review — <distribution-id>

Account: <account-id> | Service: Amazon CloudFront (global) | Date: <YYYY-MM-DD>
Domain: <d***.cloudfront.net> | Aliases: <CNAMEs> | Status: <Deployed/InProgress> | Enabled: <yes/no>
Price Class: <PriceClass_*> | HTTP: <http2and3> | WAF: <yes/no>

## Executive Summary

- Health: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
- Finding counts by severity: CRITICAL <n> · HIGH <n> · MEDIUM <n> · LOW <n> · INFO <n> · UNKNOWN <n>
- Top 3 critical/high items: <list>

## Configuration Snapshot

| Item | Value |
|------|-------|
| Origins | domain(s), type (S3 / custom / VPC), OAC or OAI, protocol policy, timeouts, custom header names (never values) |
| Origin groups | members, failover status codes, allowed/cached methods of behaviors that use them |
| Cache behaviors | count, viewer protocol policy, cache policy, compression |
| Security | WAF web ACL (rule names only), TLS min version, viewer protocol, cert (ACM / default), FLE |
| Access control | signed URLs/cookies (key groups), geo restriction |
| Edge compute | CloudFront Functions, Lambda@Edge associations |
| Delivery | price class, HTTP version, IPv6, Origin Shield |
| Observability | legacy standard logging, standard logging v2 (destination type), real-time logs (Kinesis), monitoring subscription, alarms (metric / metric-math / composite) |

## Findings by Pillar

Repeat the table for each pillar — Security, Reliability, Performance, Cost Optimization,
Operational Excellence. Assign severities using `references/findings-severity-catalog.md`.

| # | Finding | Severity | Current State | Recommendation |
|---|---------|----------|---------------|----------------|
|   |         |          |               |                |

## CloudWatch Metrics (7-Day)

| Metric | Stat | 7-Day Value | Status | Finding |
|--------|------|-------------|--------|---------|
|        |      |             |        |         |

## Log Analysis (<window>)

Source: <log group, window, Logs Insights> or "not queried — <reason>" (all rows UNKNOWN)

| Pattern / status | Occurrences or rate | Severity | Finding |
|------------------|---------------------|----------|---------|
|                  |                     |          |         |

When 5xx is present, include the breakdown by `x-edge-detailed-result-type` (timeout:
`OriginCommError`/`OriginReadError`; refused: `OriginConnectError`; DNS: `OriginDnsError`) and
any CloudFront-generated 503s (`CapacityExceeded`, `LimitExceeded`).

## Configuration Change / Event Notes

`LastModifiedTime` and any CloudTrail-visible `UpdateDistribution` / WAF / ACM changes (or a note that CloudTrail was out of scope).

## Cost Summary

- Pricing model: pay-as-you-go, or flat-rate plan `<tier>` (from `pricingplanmanager.ListSubscriptions`)
- Account-level CloudFront cost, latest full month, with the top usage types (Cost Explorer)
- This distribution's usage drivers: 7-day BytesDownloaded, Requests, price class, cache hit
  ratio (CloudWatch, log-derived approx., or UNKNOWN)
- Per-distribution cost: only if resource-level billing data was available — cite the source
  (`GetCostAndUsageWithResources` or the usage report's `Resource` column); otherwise state
  "not available without resource-level billing data". Never split account cost proportionally.
- Top 3 cost-optimization opportunities (linked to findings; none priced per GB or per request
  for a flat-rate distribution)

## Limitations and Unknowns

| Check | API attempted | Error / reason | Status |
|-------|---------------|----------------|--------|
|       |               |                | UNKNOWN — manual verification required |

## Priority Matrix

| # | Finding | Severity | Pillar | Effort | Impact |
|---|---------|----------|--------|--------|--------|
|   |         |          |        |        |        |

## Next Steps

- Immediate (CRITICAL — 24–48 hours; HIGH — 1 week): <list>
- Short-term (MEDIUM — 30 days): <list>
- When convenient (LOW): <list>
- Verify manually (UNKNOWN): <list>

## Appendix — Reference Links

- [Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html)
- [Security in CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/security.html)
- [Restricting access to an S3 origin with OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [Origin failover](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/high_availability_origin_failover.html)
- [Using Origin Shield](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/origin-shield.html)
- [Managed cache policies](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-cache-policies.html)
- [Monitoring CloudFront with CloudWatch](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/monitoring-using-cloudwatch.html)
- [CloudFront pricing / price classes](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/PriceClass.html)
- [AWS WAF with CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-aws-waf.html)
- [Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
