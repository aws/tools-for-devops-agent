# Report Template — Amazon CloudFront Operational Review

Use this structure for the report artifact produced in Step 6. Fill every `<placeholder>`,
drop sections marked "skip when", and keep the order fixed so recurring runs diff cleanly.

Artifact naming: `cloudfront-review-<distribution-or-account>-<YYYY-MM-DD>.md`
Examples: `cloudfront-review-E1A2B3C4D5E6F7-2026-10-20.md` (single distribution),
`cloudfront-review-123456789012-2026-10-20.md` (account)

## Report Header

```
# Amazon CloudFront Operational Review — <distribution or account>
Date: <YYYY-MM-DD> | Metric window: <start> to <end> (us-east-1, Region=Global)
Pillars reviewed: <list>
Distributions: <n> discovered | <n> Pass 2 (deep-dive) | <n> Pass 1 only
Pass 2 selection rule: <all (<10 distributions) | 10 worst-ranked + user-named>
```

Place any "⚠️ reference could not be loaded" notices immediately below the header.

## Executive Summary

- Overall: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
- Readiness score per pillar, with the count of excluded (Inspect / N/A / not evaluated) checks
- Finding counts by severity
- Distributions exposing plaintext HTTP (SEC-01/02/03): <list>
- Top 3 CRITICAL/HIGH items

## Change Since Last Review (recurring runs only — see Step 7)

New / Resolved / Persistent, with new or persistent CRITICAL/HIGH called out. Write
"baseline review — no prior run to compare" when there is no prior report.

## Distribution Inventory

| Distribution | Aliases | Profile | Origins (class) | WAF | Viewer policy | Min TLS | Cert expiry | Logging | Add'l metrics | Pass |
|---|---|---|---|---|---|---|---|---|---|---|

- Profile: static / dynamic. Origin class per Step 2 (S3, S3 website, MRAP, Lambda URL, media, VPC, custom).
- Pass: 1 or 2.
- List staging (continuous deployment) distributions with their primary.

## Account-Level Rollup (skip for a single distribution)

| Issue class | Distributions affected | Of total |
|---|---|---|
| Viewer HTTP allowed | | |
| Origin HTTP / weak origin TLS | | |
| Security policy below TLSv1.2_2021 | | |
| No WAF (dynamic) | | |
| Legacy OAI | | |
| S3 origin with no access restriction | | |
| No access logging | | |
| No 5xx alarm | | |

Report an issue affecting 60 % or more of the distributions as a systemic item.

## Findings by Pillar

For each of Security, Reliability, Performance Efficiency, Operational Excellence, and Cost
Optimization:

| # | Check ID | Distribution / behavior / origin | Finding | Severity | Current | Recommendation |
|---|---|---|---|---|---|---|

- Show a pillar with no findings as "No findings — ✅".
- Behavior findings name the path pattern (`Default (*)` for the default behavior).
- Inspect items appear here with 🔎, state what to confirm, and carry no Pass or Fail.

## Metrics Summary (Pass 2 distributions)

| Distribution | Requests (7d) | 4xx % | 5xx % | Cache hit % | Origin latency p90 | Worst hour | Status |
|---|---|---|---|---|---|---|---|

Write "n/a — additional metrics off" in the opt-in columns when the subscription is disabled.

## Cost Opportunities (skip when the cost pillar is out of scope)

| Opportunity | Check ID | Signal | Est. impact | Source |
|---|---|---|---|---|

Compression impact is a range ($0 to about 70 % of data-transfer-out cost). Label Cost
Explorer figures "from Cost Explorer, unblended". If Cost Explorer was unavailable, say so.

## Visibility Limits

Every check marked "not evaluated" or 🔎 Inspect, with the reason. Always include:
- Origin security groups and bucket policies are not read. Origin lockdown findings are
  Inspect items.
- WAF rules are counted by type, not evaluated for correctness.
- Edge function code is not read.
- Additional-metrics checks are skipped for distributions without the subscription.
- Distributions that received Pass 1 only.

## Prioritized Recommendations

| Priority | Check ID | Distribution(s) | Current → Risk → Fix | Documentation |
|---|---|---|---|---|

Order by severity, then by distributions affected. No effort or time estimates.

## References

Link each AWS documentation page cited above.
