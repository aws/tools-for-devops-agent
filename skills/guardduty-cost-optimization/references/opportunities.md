# GuardDuty Cost Optimization Opportunity Catalog

Detailed reference for the seven opportunity checks. Load this during Step 4 (Analyze)
after ranking each enabled protection plan by its share of total GuardDuty spend.
Assign each finding a severity (CRITICAL, HIGH, MEDIUM, LOW, INFO) and, where a
usage/cost signal exists, an estimated monthly saving.

**Frame every recommendation against security value** — GuardDuty is a security
control, and cost reductions must not silently remove needed coverage. Present plan
reductions as cost-vs-risk tradeoffs, cite the finding activity for the plan
(`GetFindingsStatistics`), and defer the decision to the user's security posture.

## 4.1 High-cost / low-signal protection plans
Ref: [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/)

- A protection plan consuming a large share of spend while producing few or no
  findings over a representative window → review whether its coverage is warranted for
  the workload → **MEDIUM** (present as a value/cost tradeoff, not an automatic
  "disable"). Use `GetFindingsStatistics` for the value side.

## 4.2 Runtime Monitoring ↔ VPC Flow Log offset
Ref: [Monitoring GuardDuty usage and estimating costs](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html)

- High `VPCFlowLogDNSLogEvents` (AnalyzedBytes) spend **and** EC2/EKS workloads not
  covered by the Runtime Monitoring agent → enabling Runtime Monitoring stops VPC Flow
  Log processing charges on monitored instances and adds deeper runtime detection →
  compare `MonitoredVcpuHours` cost vs the avoided VPC Flow Log cost → **MEDIUM**
  opportunity when the offset is favorable.
- Runtime Monitoring enabled but the **agent not actually transmitting** on many
  instances → the **worst of both worlds**: because the agent isn't covering those
  instances, the VPC Flow Log offset does **not** apply, so the account keeps paying
  **VPC Flow Log processing charges** for them *and* pays for the Runtime Monitoring
  plan, while getting **no runtime detection coverage** in return → fix agent coverage
  so it transmits (or, if runtime coverage is genuinely not wanted, disable the plan
  honestly) rather than treating it as a cost saving → **MEDIUM**.

## 4.3 S3 Protection cost vs value
Ref: [GuardDuty S3 Protection](https://docs.aws.amazon.com/guardduty/latest/ug/s3-protection.html)

- High `S3DataEvents` (AnalyzedCount) spend on buckets with predictable,
  high-volume, low-risk access patterns (e.g. internal data-lake churn) → weigh S3
  Protection cost against exfiltration/destruction risk for those buckets → **MEDIUM**
  tradeoff.

## 4.4 Malware Protection for S3 scan volume
Ref: [Pricing in GuardDuty](https://docs.aws.amazon.com/guardduty/latest/ug/guardduty-pricing.html)

- High `CompletedScanBytes` (namespace `AWS/GuardDuty/MalwareProtection`) driven by
  scanning large, low-risk, or frequently-rewritten objects → scope Malware Protection
  for S3 to the buckets/prefixes that need it → **MEDIUM**. Note On-demand malware
  scan has **no** free tier.

## 4.5 Free-trial cost projection (proactive)
Ref: [Estimating GuardDuty cost](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html#estimating_guardduty_cost)

- One or more plans within the **30-day free trial** → project post-trial monthly cost
  from the observed trial usage metrics **before** the bill lands, per plan → **HIGH**
  visibility (prevents bill shock; lets the user disable a plan before it starts
  charging if the projected cost outweighs value).

## 4.6 Duplicate / inconsistent multi-account coverage
Ref: [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/)

- In an organization, protection plans enabled inconsistently across members, or
  enabled on accounts/Regions with no meaningful workload → align coverage to where
  workloads and risk actually are → **MEDIUM**.
- GuardDuty enabled in Regions the organization does not use → disable in unused
  Regions → **MEDIUM**.

## 4.7 Security Hub consolidated pricing (informational)
Ref: [Monitoring GuardDuty usage and estimating costs](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html#security-hub-customers)

- If the account uses (or is considering) the Security Hub Threat Analytics plan, note
  that it consolidates metering of multiple GuardDuty data sources and can change the
  effective cost model → **INFO** (surface for the user's FinOps decision; the free
  trial status is independent of Security Hub).
