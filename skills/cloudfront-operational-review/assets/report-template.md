# CloudFront Operational Review — <distribution-id>

Account: <account-id> | Service: Amazon CloudFront (global) | Date: <YYYY-MM-DD>
Domain: <d***.cloudfront.net> | Aliases: <CNAMEs> | Status: <Deployed/InProgress> | Enabled: <yes/no>
Price Class: <PriceClass_*> | HTTP: <http2and3> | WAF: <yes/no>

## Executive Summary

- Health: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
- Finding counts by severity: CRITICAL <n> · HIGH <n> · MEDIUM <n> · LOW <n> · INFO <n>
- Top 3 critical/high items: <list>

## Configuration Snapshot

| Item | Value |
|------|-------|
| Origins | domain(s), type (S3 / custom / VPC), OAC or OAI, protocol policy, timeouts |
| Origin groups | failover configured? members |
| Cache behaviors | count, viewer protocol policy, cache policy, compression |
| Security | WAF web ACL, TLS min version, viewer protocol, cert (ACM / default), FLE |
| Access control | signed URLs/cookies (key groups), geo restriction |
| Edge compute | CloudFront Functions, Lambda@Edge associations |
| Delivery | price class, HTTP version, IPv6, Origin Shield |
| Observability | standard logging, monitoring subscription, real-time logs, alarms |

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

## Log Analysis (7-Day)

| Pattern / status | Occurrences or rate | Severity | Finding |
|------------------|---------------------|----------|---------|
|                  |                     |          |         |

Include the 504 / origin-connection-failure breakdown (timeout vs refused vs TLS) when 5xx is present.

## Configuration Change / Event Notes

`LastModifiedTime` and any CloudTrail-visible `UpdateDistribution` / WAF / ACM changes (or a note that CloudTrail was out of scope).

## Cost Summary

- Latest-month estimated cost for this distribution (proportional split, marked "estimated")
- Top 3 cost-optimization opportunities (linked to findings)

## Priority Matrix

| # | Finding | Severity | Pillar | Effort | Impact |
|---|---------|----------|--------|--------|--------|
|   |         |          |        |        |        |

## Next Steps

- Immediate (CRITICAL/HIGH — 7 days): <list>
- Short-term (MEDIUM — 30 days): <list>
- Long-term (LOW — 90 days): <list>

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
