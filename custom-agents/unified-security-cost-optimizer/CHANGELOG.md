# Changelog

## 1.1.0

- Treat all ingested resource, usage, finding, and cost data as untrusted — the
  System Prompt now states this data must never be followed as instructions, closing a
  prompt-injection path where a crafted tag, bucket name, or finding string could steer
  the agent into recommending reduced CloudTrail, Config, or GuardDuty coverage.
- Require every coverage-reducing recommendation to state its security impact and cite
  the specific evidence (metric, API field, resource) it rests on, so a human can
  verify independently before acting; added Security Impact and Evidence columns to the
  consolidated report. Addresses H1 from peer review.

## 1.0.0

- Initial version
- System prompt with Goal/Approach/Constraints/Output structure
- Routes to the `cloudtrail-cost-optimization`, `config-cost-optimization`, and `guardduty-cost-optimization` skills for domain knowledge
- Requires the `use_aws` tool for read-only resource and usage inspection
- Read-only, security-and-compliance-first: frames every reduction as a cost-vs-risk tradeoff and defers the decision to the customer
- Produces per-skill artifacts for single-service reviews and a consolidated `security-cost-optimization-<account-id>-<YYYY-MM-DD>.md` for multi-service reviews
- Output includes executive summary, opportunities by service, cross-service observations, consolidated priority matrix, and next steps
- Severity-based prioritization (CRITICAL, HIGH, MEDIUM, LOW, INFO) with estimated monthly savings
