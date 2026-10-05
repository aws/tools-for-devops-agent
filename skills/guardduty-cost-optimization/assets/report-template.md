# Amazon GuardDuty Cost Optimization Report Template

Output template for the report artifact. Load this when generating the final report so
the structure, section order, and table schemas are consistent.

Artifact naming: `guardduty-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
Example: `guardduty-cost-optimization-123456789012-2026-09-24.md`

---

### Report Header
```
# Amazon GuardDuty Cost Optimization — <account-id>
Date: <YYYY-MM-DD> | Scope: <regions / organization> | Analysis window: <start> to <end>
```

### Executive Summary
- Estimated total monthly savings (sum of quantified opportunities) or "not quantified"
- Finding counts by severity
- Top 3 opportunities by estimated saving
- Any plan still in the 30-day free trial with projected post-trial cost

### Protection Plan Usage & Spend
| Protection Plan | Data Source | Usage (window) | Est. Monthly Cost | Findings (window) | Share |
|-----------------|-------------|----------------|-------------------|-------------------|-------|

### Cost Optimization Opportunities
| # | Opportunity | Severity | Current State | Recommendation (value tradeoff) | Security Impact | Evidence | Est. Monthly Saving |
|---|-------------|----------|---------------|----------------------------------|-----------------|----------|---------------------|

Security Impact and Evidence are mandatory for any coverage-reducing recommendation
(disabling or scoping down a protection plan): state in plain language what threat
detection is lost, and cite the specific `AWS/GuardDuty` usage metric, finding
statistic, or cost signal for that plan. For an item with no coverage impact, note
"none" and still cite the evidence.

### Free-Trial Projection (if any plan in trial)
| Protection Plan | Trial usage rate | Projected monthly cost | Trial ends |
|-----------------|------------------|------------------------|------------|

### Priority Matrix
| # | Opportunity | Severity | Effort | Est. Saving |
|---|-------------|----------|--------|-------------|

### Next Steps
- Immediate (HIGH — within 7 days, e.g. free-trial decisions)
- Short-term (MEDIUM — within 30 days)
- Long-term (LOW/INFO)

### Appendix — Reference Links
- [Monitoring GuardDuty usage and estimating costs](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html)
- [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/)
- [Pricing in GuardDuty](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty-pricing.html)
- [GuardDuty S3 Protection](https://docs.aws.amazon.com/guardduty/latest/ug/s3-protection.html)
- [Runtime Monitoring](https://docs.aws.amazon.com/guardduty/latest/ug/runtime-monitoring.html)
