# Report Template — Amazon Data Firehose Operational Review

Use this structure for the review report artifact produced in Step 5. Fill every
`<placeholder>`, drop sections that do not apply to the scope (per the inline "skip when"
notes), and keep the pillar order consistent so recurring runs diff cleanly.

Artifact naming: `firehose-review-<stream-or-account>-<region>-<YYYY-MM-DD>.md`
Examples: `firehose-review-orders-stream-us-east-1-2026-09-17.md` (single stream),
`firehose-review-123456789012-us-east-1-2026-10-02.md` (account/region rollup)

## Report Header

```
# Amazon Data Firehose Operational Review — <stream or account-id> / <region>
Date: <YYYY-MM-DD> | Analysis window: <start> to <end>
Pillars reviewed: <list>
```

## Executive Summary

- Health: ✅ HEALTHY / ⚠️ WARNINGS / ❌ CRITICAL
- Finding counts by severity
- Top 3 critical/high items

## Change Since Last Review (recurring runs only — see Step 6)

When a prior report for this scope exists, summarize before the detailed findings:
- New (with severity), Resolved, and Persistent (with any severity change) counts
- Call out any new or persistent CRITICAL/HIGH explicitly

Omit this section (or note "baseline review") when there is no prior run to compare.

## Account-Level Rollup (when scope spans multiple streams/regions)

When the review covers more than one stream, lead with an account/region rollup before
the per-stream detail so the reader sees systemic gaps at a glance:

| Region | Streams | Encryption gaps | Streams w/o backup | Streams throttling | Delivery-lag alerts | Uncompressed S3 |
|--------|---------|-----------------|--------------------|--------------------|--------------------|-----------------|

Summarize as "X of Y streams" per issue class, and call out any finding that affects a
**majority of streams** — per the "majority of streams" definition in
`references/metrics-thresholds.md` (≥ 60% of in-scope streams) — as a systemic
(account-level) item rather than repeating it per stream. Skip this section for a
single-stream review.

## Findings by Pillar

For each of Security, Reliability, Performance, Service Quotas, Cost Optimization,
Operational Excellence, and Sustainability:

| # | Finding | Severity | Current State | Recommendation |

Include a pillar even when it has no findings — show it with a "No findings — ✅" row so
the reader can see the pillar was assessed (Sustainability and Operational Excellence will
often be light).

## Delivery Stream Configuration

Per stream: source type, destination, buffering hints, compression, encryption,
backup mode, transform/format-conversion status, and CloudWatch logging.

## CloudWatch Metrics Summary

| Stream | Metric | Stat | Value | Status | Finding |

## Service Quota Utilization

| Quota | Value | Observed P95 | Utilization % | Risk |

## Cost Optimization & Sustainability Opportunities

Cost and sustainability opportunities share the same efficiency levers — list them
together, marking which pillar(s) each serves:

| Opportunity | Signal | Pillar(s) | Est. Impact | Effort |

## Priority Matrix

| # | Finding | Severity | Pillar | Effort | Impact |

## Next Steps

- Immediate (CRITICAL/HIGH — 7 days)
- Short-term (MEDIUM — 30 days)
- Long-term (LOW — 90 days)

## Appendix — Reference Links

- [Amazon Data Firehose Developer Guide](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html)
- [Monitoring with CloudWatch metrics](https://docs.aws.amazon.com/firehose/latest/dev/monitoring-with-cloudwatch-metrics.html)
- [CloudWatch alarm best practices](https://docs.aws.amazon.com/firehose/latest/dev/firehose-cloudwatch-metrics-best-practices.html)
- [Firehose quotas](https://docs.aws.amazon.com/firehose/latest/dev/limits.html)
- [Data protection / encryption](https://docs.aws.amazon.com/firehose/latest/dev/encryption.html)
- [Record format conversion](https://docs.aws.amazon.com/firehose/latest/dev/record-format-conversion.html)
- [Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Operational Excellence Pillar](https://docs.aws.amazon.com/wellarchitected/latest/operational-excellence-pillar/welcome.html)
- [Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)
