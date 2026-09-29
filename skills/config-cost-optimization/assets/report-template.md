# AWS Config Cost Optimization Report Template

Output template for the report artifact. Load this when generating the final report so
the structure, section order, and table schemas are consistent.

Artifact naming: `config-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
Example: `config-cost-optimization-123456789012-2026-09-24.md`

---

### Report Header
```
# AWS Config Cost Optimization — <account-id>
Date: <YYYY-MM-DD> | Scope: <regions / organization> | Analysis window: <start> to <end>
```

### Executive Summary
- Estimated total monthly savings (sum of quantified opportunities) or "not quantified"
- Finding counts by severity
- Top 3 opportunities by estimated saving

### Config Setup Inventory
| Region | Recording mode | allSupported | Global types | # Resource types | # Rules | # Conformance packs |
|--------|---------------|--------------|--------------|------------------|---------|---------------------|

### Configuration-Item Drivers
| Resource Type | CI Volume (approx) | Recording Mode | Recommendation |
|---------------|--------------------|----------------|----------------|

### Cost Optimization Opportunities
| # | Opportunity | Severity | Current State | Recommendation | Est. Monthly Saving |
|---|-------------|----------|---------------|----------------|---------------------|

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
- [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)
- [Cost optimization recommendations for AWS Config](https://aws.amazon.com/blogs/mt/cost-optimization-recommendations-for-aws-config/)
- [Best practices for analyzing AWS Config recording frequencies](https://aws.amazon.com/blogs/mt/best-practices-for-analyzing-aws-config-recording-frequencies/)
- [Identifying resources with the most configuration changes](https://aws.amazon.com/blogs/mt/identifying-resources-most-configuration-changes-aws-config/)
- [AWS Config pricing](https://aws.amazon.com/config/pricing/)
