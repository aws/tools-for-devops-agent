# CloudTrail Cost Optimization Report Template

Output template for the Step 5 report artifact. Load this when generating the final
report so the structure, section order, and table schemas are consistent.

Artifact naming: `cloudtrail-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
Example: `cloudtrail-cost-optimization-123456789012-2026-09-24.md`

---

### Report Header
```
# AWS CloudTrail Cost Optimization — <account-id>
Date: <YYYY-MM-DD> | Scope: <regions / organization> | Analysis window: <start> to <end>
```

### Executive Summary
- Estimated total monthly savings (sum of quantified opportunities) or "not quantified"
- Finding counts by severity
- Top 3 opportunities by estimated saving

### Trail & Lake Inventory
| Trail / EDS | Multi-Region | Org | Logging | Mgmt (R/W) | Data events | KMS/RDS excl. | S3 bucket |
|-------------|-------------|-----|---------|-----------|-------------|---------------|-----------|

### Cost Optimization Opportunities
| # | Opportunity | Severity | Current State | Recommendation | Security Impact | Evidence | Est. Monthly Saving |
|---|-------------|----------|---------------|----------------|-----------------|----------|---------------------|

Security Impact and Evidence are mandatory for any coverage-reducing recommendation
(disabling a trail, dropping Read/data events, excluding KMS/RDS, narrowing a
selector): state in plain language what event coverage is lost, and cite the specific
metric, cost signal, or trail/selector field the finding rests on. For an item with no
coverage impact (e.g. S3 lifecycle), note "none" and still cite the evidence.

### Cost Attribution (if Cost Explorer available)
| Usage Type | 30-Day Cost | Share |
|------------|-------------|-------|

### Priority Matrix
| # | Opportunity | Severity | Effort | Est. Saving |
|---|-------------|----------|--------|-------------|

### Next Steps
- Immediate (HIGH — within 7 days)
- Short-term (MEDIUM — within 30 days)
- Long-term (LOW — within 90 days)

### Appendix — Reference Links
- [Managing CloudTrail trail costs](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-trail-manage-costs.html)
- [CloudTrail pricing](https://aws.amazon.com/cloudtrail/pricing/)
- [Remove duplicate CloudTrail events](https://repost.aws/knowledge-center/remove-duplicate-cloudtrail-events)
- [Optimize CloudTrail costs and maintain compliance](https://repost.aws/knowledge-center/optimize-cloudtrail-compliance)
- [Filtering data events with advanced event selectors](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/filtering-data-events.html)
- [Managing CloudTrail Lake costs](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-lake-manage-costs.html)
