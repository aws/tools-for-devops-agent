# Config Cost Optimization Opportunity Catalog

Detailed reference for the eight opportunity checks. Load this during Step 4 (Analyze)
when evaluating the recorder, rules, and conformance packs. Assign each finding a
severity (CRITICAL, HIGH, MEDIUM, LOW, INFO) and, where a cost/volume signal exists,
an estimated monthly saving.

## 4.1 Recording frequency mismatch (highest-leverage tuning)
Ref: [Best practices for analyzing AWS Config recording frequencies](https://aws.amazon.com/blogs/mt/best-practices-for-analyzing-aws-config-recording-frequencies/)

- **High-churn resource types recorded continuously** → switch those types to daily
  recording via per-resource-type `recordingMode` overrides → **HIGH**. Continuous
  bills every change; for resources that change many times per day, daily (one CI/day)
  is materially cheaper.
- Conversely, do **not** blanket-recommend daily for everything — low-churn,
  security-critical resources (IAM, security groups) are cheap continuously and
  benefit from real-time change capture. Recommend daily selectively, per type.

## 4.2 Over-broad resource-type recording
Ref: [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

- Recorder set to `allSupported=true` when only a subset of resource types is needed
  for the account's compliance/security requirements → record only the required types
  (or add high-noise types to the exclusion list) → **HIGH**. This directly reduces
  the number of CIs generated.

## 4.3 Duplicate global-resource recording
Ref: [Optimize AWS Config costs](https://repost.aws/knowledge-center/optimize-aws-config)

- `includeGlobalResourceTypes=true` in **multiple** Regions → global resources (e.g.
  IAM users, roles, policies) are recorded once per Region, multiplying CIs → enable
  global-resource recording in **one** Region only → **HIGH** when many Regions
  record globals.

## 4.4 High-churn CI drivers
- Specific noisy resource types dominating CI volume (from Athena/CI-driver analysis)
  → move those types to daily recording, add to the exclusion list, or stop recording
  if not compliance-relevant → **MEDIUM/HIGH** depending on their share of spend.

## 4.5 Redundant or unnecessary rules
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

## 4.6 Conformance pack overlap and efficiency

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

## 4.7 S3 storage lifecycle
Ref: [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)

- The Config delivery bucket has **no lifecycle policy** transitioning old
  configuration history/snapshots to cheaper tiers or expiring them past the retention
  requirement → **LOW**.

## 4.8 Recorder running with no consumer
- A recorder running in a Region with no rules, no aggregator, and no downstream
  consumer of the configuration history → recording CIs nobody uses → confirm intent;
  if unused, stop recording in that Region → **MEDIUM**.
