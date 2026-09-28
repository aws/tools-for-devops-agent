---
name: config-cost-optimization
description: Identify and quantify AWS Config cost optimization opportunities.
  Use this skill when a user asks to reduce, review, audit, or optimize AWS Config
  spend, or reports an unexpected AWS Config cost or configuration-item increase.
  Activate on requests like "why is my AWS Config bill so high", "reduce Config
  costs", "AWS Config cost review", "my configuration item count spiked", "should I
  use daily or continuous Config recording", or "which resources are driving Config
  cost". This skill analyzes configuration recorders, recording frequency, recorded
  resource types, Config rules, conformance packs, and the delivery S3 bucket through
  read-only AWS APIs to surface high-churn configuration-item drivers, continuous-vs-
  daily recording mismatches, over-broad resource recording, duplicate global-resource
  recording, and redundant rules/conformance packs, producing a severity-ranked report
  of savings.
metadata:
  author: holmalla
  version: "1.1.0"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "AWS Config"
  aws-devops-agent-skills.technical-domains: "Governance, Cost Optimization"
---

# AWS Config Cost Optimization

Identify, quantify, and prioritize AWS Config cost optimization opportunities aligned
with [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config),
[Cost optimization recommendations for AWS Config](https://aws.amazon.com/blogs/mt/cost-optimization-recommendations-for-aws-config/),
and [AWS Config pricing](https://aws.amazon.com/config/pricing/).

This skill uses **read-only Config, CloudWatch, S3, and Organizations APIs only**. It
never starts, stops, or reconfigures a recorder, rule, or conformance pack — all
remediation is delivered as recommendations for a human to review and apply.

## When to Use

Activate this skill when the user asks to:
- Reduce or optimize AWS Config costs
- Investigate an unexpected Config cost or configuration-item (CI) spike
- Decide between continuous and daily recording frequency
- Review which resource types are recorded, or which rules/conformance packs run
- Perform a Config cost review or FinOps assessment

## How AWS Config Billing Works

AWS Config billing has three primary components plus storage:

| Charge | Billed on |
|--------|-----------|
| Configuration items (CIs) | Each CI recorded — the dominant cost driver |
| Config rule evaluations | Each active rule evaluation |
| Conformance pack evaluations | Each conformance pack rule evaluation |
| S3 storage | Configuration history and snapshots stored in the delivery bucket |

Recording frequency changes the CI price and cadence:

| Mode | Price per CI | Cadence |
|------|-------------|---------|
| Continuous | ~$0.003 | Bills a CI for **every** change |
| Daily | ~$0.012 | Bills at most **one** CI per resource per day |

The counterintuitive consequence the skill reasons about: for **high-churn**
resources (many changes per day), continuous recording bills every single change and
often costs **more** in total than daily recording, even though daily's per-CI price
is higher. For low-churn resources, continuous is usually cheaper. The right choice is
per-resource-type and depends on change frequency.

## Step 1: Identify Target Scope

Ask the user which accounts and Regions to review, and whether this is a standalone
account, an Organizations management/delegated-administrator account (aggregator), or
a member account. Accept specific account IDs and Regions, "all regions", or
"organization". If no scope is given, default to the current account across all
Regions with a 30-day analysis window.

## Step 2: Inventory the Config Setup

Collect the recorder, rule, and conformance-pack inventory per Region:

```
config.DescribeConfigurationRecorders          # recorder config: allSupported,
                                               # includeGlobalResourceTypes, recordingMode
                                               # (per-resource-type frequency overrides),
                                               # resourceTypes list, exclusion list
config.DescribeConfigurationRecorderStatus     # is the recorder running?
config.DescribeDeliveryChannels                # S3 bucket + SNS destination
config.DescribeConfigRules                     # active managed + custom rules
config.DescribeConformancePacks                # conformance packs
config.DescribeConfigurationAggregators        # org/multi-account aggregation
config.GetDiscoveredResourceCounts             # resource-type inventory (CI-generating
                                               # surface, by resource type)
```

Capture: recording mode (continuous vs daily, globally and per-resource-type
overrides), whether `allSupported` is on, whether `includeGlobalResourceTypes` is on
and in how many Regions, the recorded/excluded resource-type lists, the number of
active rules and conformance packs, and the delivery bucket.

## Step 3: Collect Cost and Volume Signals

- **Cost Explorer** (`ce.GetCostAndUsage`, filtered to the `AWSConfig` service,
  grouped by `USAGE_TYPE`) to split spend across `ConfigurationItemRecorded`, rule
  evaluations, and conformance-pack evaluations. This is the most direct dollar
  signal — prefer it when the role has Cost Explorer access.
- **CI drivers**: identify which resource types generate the most CIs. The
  authoritative method is an Athena query over the Config S3 data (see
  [Identifying resources with the most configuration changes](https://aws.amazon.com/blogs/mt/identifying-resources-most-configuration-changes-aws-config/));
  when Athena is not available, use `GetDiscoveredResourceCounts` plus known
  high-churn types (Auto Scaling groups, EC2 instances/ENIs/volumes during scaling,
  spot fleets) as a directional signal, and label it as approximate.
- **S3 delivery bucket size** (`s3.ListObjectsV2` / CloudWatch `BucketSizeBytes`) for
  the storage component.

If Cost Explorer is unavailable, report configuration findings and label dollar
impact as "not quantified — enable Cost Explorer for sizing".

## Step 4: Analyze Cost Optimization Opportunities

Evaluate the setup against the checks below. Assign each finding a severity
(CRITICAL, HIGH, MEDIUM, LOW, INFO) and, where a cost/volume signal exists, an
estimated monthly saving.

### 4.1 Recording frequency mismatch (highest-leverage tuning)
Ref: [Best practices for analyzing AWS Config recording frequencies](https://aws.amazon.com/blogs/mt/best-practices-for-analyzing-aws-config-recording-frequencies/)

- **High-churn resource types recorded continuously** → switch those types to daily
  recording via per-resource-type `recordingMode` overrides → **HIGH**. Continuous
  bills every change; for resources that change many times per day, daily (one CI/day)
  is materially cheaper.
- Conversely, do **not** blanket-recommend daily for everything — low-churn,
  security-critical resources (IAM, security groups) are cheap continuously and
  benefit from real-time change capture. Recommend daily selectively, per type.

### 4.2 Over-broad resource-type recording
Ref: [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

- Recorder set to `allSupported=true` when only a subset of resource types is needed
  for the account's compliance/security requirements → record only the required types
  (or add high-noise types to the exclusion list) → **HIGH**. This directly reduces
  the number of CIs generated.

### 4.3 Duplicate global-resource recording
Ref: [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

- `includeGlobalResourceTypes=true` in **multiple** Regions → global resources (e.g.
  IAM users, roles, policies) are recorded once per Region, multiplying CIs → enable
  global-resource recording in **one** Region only → **HIGH** when many Regions
  record globals.

### 4.4 High-churn CI drivers
- Specific noisy resource types dominating CI volume (from Athena/CI-driver analysis)
  → move those types to daily recording, add to the exclusion list, or stop recording
  if not compliance-relevant → **MEDIUM/HIGH** depending on their share of spend.

### 4.5 Redundant or unnecessary rules
Ref: [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

- Rules that are redundant, disabled-in-intent, or no longer mapped to a live
  requirement → each evaluation is billed → remove or turn off → **MEDIUM**.
- A **standalone (user-managed) rule** that duplicates a rule already delivered inside
  a conformance pack, with **no distinct purpose** (same source identifier, same
  parameters, and the standalone copy is not wired to a separate remediation,
  notification, or reporting path) → the standalone copy is pure duplicated evaluation
  cost → remove the standalone rule and rely on the pack's copy → **MEDIUM**. Before
  recommending removal, confirm the standalone rule's parameters match the pack's
  (e.g. an `acm-certificate-expiration-check` with a *stricter* threshold than the
  pack is **not** a duplicate — it enforces a different requirement; flag the conflict
  for the customer to reconcile rather than deleting it).

### 4.6 Conformance pack overlap and efficiency

Two conformance packs sharing rules is **not automatically waste**, and consolidating
them is frequently the wrong call. Reason explicitly about *why* the packs exist
before recommending anything.

**How pack overlap is billed and reported.** Each conformance pack evaluates its own
rules, so a rule that appears in two packs (e.g. `encrypted-volumes` in both a PCI
pack and a NIST 800-53 pack) is evaluated — and billed — once per pack. But that
second evaluation also produces a **second, independent per-framework compliance
result**: AWS Config tracks compliance per pack (the `AWS::Config::ConformancePackCompliance`
resource and each pack's own dashboard/compliance history), and the AWS-provided pack
templates deliberately map the *same* technical control to *different* framework
controls (one PCI DSS requirement, one NIST 800-53 control). The overlap is the
mechanism by which one resource check satisfies two frameworks' attestations
simultaneously.

**Decision — do NOT default to "merge into one pack".** Apply this test:

- **Keep both packs (overlap is acceptable, usually INFO, not a saving)** when the
  customer must **attest to both frameworks independently** — i.e. an auditor, GRC
  tool, or regulator consumes the PCI scorecard and the NIST scorecard separately. A
  merged "union" pack collapses the two into one compliance view and destroys the
  per-framework control-to-rule traceability that the attestation depends on. The
  duplicate-evaluation cost (only the *overlapping* rules, at the conformance-pack
  evaluation price) is the deliberate price of dual attestation. Report it as an
  **INFO** observation with the tradeoff stated, and size the ceiling (overlapping
  rule count × evaluations × pack-eval price) so the customer sees the cost is small
  relative to losing separate reporting. Do **not** present merging as the
  recommended action.
- **Recommend consolidation or trimming (MEDIUM)** only when separate per-framework
  attestation is genuinely **not** required — for example: one framework is
  aspirational/internal and not separately audited; one framework's control set is
  fully subsumed by the other and the customer confirms they only report against the
  superset; or a pack is deployed but no one consumes its compliance dashboard. In
  that case, either drop the redundant pack or build a single tailored pack, and state
  that per-framework reporting for the dropped framework is lost.
- **Always verify the consumer first.** Ask (or instruct the customer to confirm) who
  reads each pack's compliance status and whether any GRC/audit tooling maps to the
  pack ARNs. Never recommend collapsing packs before that dependency is confirmed —
  the saving is single-digit dollars and the downside is an audit-reporting gap.

A pack whose evaluations genuinely exceed its value (e.g. a pack no one attests
against, or where a handful of individual rules would cover the live requirement more
cheaply than the full template) → evaluate individual rules vs the pack → **MEDIUM**.

### 4.7 S3 storage lifecycle
Ref: [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

- The Config delivery bucket has **no lifecycle policy** transitioning old
  configuration history/snapshots to cheaper tiers or expiring them past the retention
  requirement → **LOW**.

### 4.8 Recorder running with no consumer
- A recorder running in a Region with no rules, no aggregator, and no downstream
  consumer of the configuration history → recording CIs nobody uses → confirm intent;
  if unused, stop recording in that Region → **MEDIUM**.

## Step 5: Generate Report

Generate a shareable Markdown report artifact.

Artifact naming: `config-cost-optimization-<account-id>-<YYYY-MM-DD>.md`
Example: `config-cost-optimization-123456789012-2026-09-24.md`

Structure:

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

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Runaway CI generation causing large ongoing overspend | Fix within 24–48 hours |
| HIGH | Clear, sizable recurring saving (frequency, resource scope, global duplication) | Fix within 1 week |
| MEDIUM | Notable saving (redundant rules, conformance packs, unused recorder) | Plan within 30 days |
| LOW | Minor saving or hygiene (S3 lifecycle) | Address when convenient |
| INFO | Observation, no action required | N/A |

## Safety and Boundaries

- **Read-only.** The skill calls only `Describe*`, `Get*`, `List*` APIs. It never
  calls `PutConfigurationRecorder`, `StopConfigurationRecorder`, `DeleteConfigRule`,
  `PutConfigRule`, or any conformance-pack/delivery-channel mutation.
- **Compliance first.** Before recommending recording fewer resource types, switching
  to daily, or removing a rule, state the compliance/security tradeoff. Real-time
  detection of IAM and security-group changes is often worth the continuous cost.
  Never recommend dropping recording below the organization's audit requirements.
- **Never collapse compliance frameworks to save evaluation cost.** Two conformance
  packs that overlap (e.g. PCI DSS and NIST 800-53) usually exist to produce two
  independent per-framework attestations. Do not recommend merging them into a union
  pack, or deleting one, unless the customer confirms separate per-framework reporting
  is not required. The overlapping-rule evaluation cost is small; the lost per-framework
  compliance view is not recoverable by re-running the report.
- **Proposed changes are suggestions.** Every recommendation is for a human to review
  and apply.

## Known Quirks

- **Daily's higher per-CI price is not a reason to avoid it** — for high-churn
  resources, daily's once-per-day cap beats continuous billing every change. Reason
  per-resource-type on change frequency, not on the sticker price.
- `GetDiscoveredResourceCounts` reflects the current resource inventory, not the CI
  generation rate — a small number of high-churn resources can dominate cost. Use
  Athena over the Config S3 data for authoritative CI-driver attribution and label
  inventory-based estimates as approximate.
- In Control Tower / Organizations environments, recorder settings may be centrally
  managed and reset on account provisioning — flag that recommendations may need to be
  applied through the landing-zone customization path rather than per-account.
- Global resource types recorded in multiple Regions are the classic silent multiplier
  — always check `includeGlobalResourceTypes` across all recording Regions.
- **Overlapping conformance packs are usually intentional, not waste.** AWS Config
  tracks compliance per pack, and the AWS-provided templates deliberately map the same
  technical rule to different framework controls. A rule shared between a PCI pack and
  a NIST pack is billed twice but also produces two independent framework scorecards —
  that is how one resource check satisfies two attestations. Only treat the overlap as
  a saving when the customer confirms they do not need to attest to both frameworks
  separately; otherwise report it as an INFO observation with the cost ceiling, not a
  consolidation recommendation.
