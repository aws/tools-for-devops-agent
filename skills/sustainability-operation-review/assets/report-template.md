# Report Template

Read this file at Step 9, immediately before writing the report. Produce every section in
order. A section with nothing to report still appears, with an explicit `None` line.

## Step 9: Generate Report

Create one shareable report artifact per workload reviewed.

Naming: `sustainability-review-<workload-name>-<YYYY-MM-DD>.md`

### Report Structure

```
# Workload Sustainability Review — <workload-name>
Account(s): <ids> | Region(s): <regions> | Date: <YYYY-MM-DD>
Workload shape: <shape> | Business output metric: <metric> (<source, or fallback used>)
Emissions data: <available: carbon model vX.Y.Z, window YYYY-MM to YYYY-MM | unavailable: verbatim error or guard message>
Water data:     <available: water model vX.Y.Z, year(s) YYYY | unavailable: verbatim error or guard message>
Impact source:  carbon <Sustainability API | user-provided CSV: <filename>, granularity <monthly|annual>, periods <...>, latest period <complete|partial: N of 12 months>>
                water <Sustainability API | user-provided CSV: <filename>, year(s) <...>>
                <add "ILLUSTRATIVE — sample data, not this account's measured emissions" when Step 5.0 flagged the file as sample/mock>
Account view:   <management account — N usage accounts | member or standalone — this account only | not determined>
```

Set `Account view` from the Step 5.1 `USAGE_ACCOUNT_ID` call (or the CSV's account column); use
`not determined` when neither is available.

### 1. Executive Summary
- Posture: ✅ EFFICIENT / ⚠️ IMPROVEMENT AVAILABLE / ❌ SIGNIFICANT WASTE
- Finding counts by severity
- Top 3 opportunities by estimated resource-footprint reduction
- **One-line honest statement of what is and is not attributable.**

### 2. Resource Intensity KPIs
| KPI | Current | 30 Days Prior | Change | Direction | Lever |

Include an explicit note on which KPIs are attributable to customer action (all of them)
versus the emissions figures (not attributable).

If the AI/ML reference was loaded, add its KPIs as a second table beneath this one.

### 3. Environmental Impact Context
Only if data is available. Clearly labelled as context, not assessment. State the source
(API or user-provided CSV) and the granularity at the top of this section.

If Amazon Bedrock or Amazon SageMaker AI is in scope, state that their emissions are reported
under "Other" and cannot be separated from published data, that a dedicated AI account makes
them visible by account, and that the AI KPIs in Section 2 are this review's measure of AI
efficiency.

**3a. Carbon**

| Month | Total MTCO2e (LBM) | Total MTCO2e (MBM) | Scope 1 | Scope 2 LBM | Scope 2 MBM | Scope 3 LBM | Scope 3 MBM | Model Version |

If the source is an **annual** CSV, replace the `Month` column with `Year`, add a `Coverage`
column stating each period's completeness (e.g. `12 of 12 months` / `6 of 12 months`), and
carry no month-over-month or year-over-year delta for a partial period — see the Step 5.0
partial-period rule. If a `cfe_savings_value` column was present, report it as its own column,
never folded into a total.

For a **monthly** source, add a `Days` column and report month-over-month change on a per-day
basis — see the Step 5.0 month-length rule — so February does not read as an improvement. Also
report, beneath the table:

- The **service × Region hotspot ranking** for the latest complete month, with each row's share
  of that month's total. Only Amazon EC2, Amazon S3 and Amazon CloudFront appear by name; label
  every other service "Other", and CloudFront's Region "Global".
- The **scope split** across the whole window. Scope 3 dominating is the normal case, and the
  report must say plainly that this is embodied hardware carbon which scales with provisioned
  capacity rather than with traffic — it is the scope most responsive to rightsizing and
  decommissioning.
- Any month where **LBM and MBM moved in opposite directions**, naming both figures. This is the
  single most common source of customer confusion and is direct evidence for the Core Framing
  Rule: the divergence is caused by AWS renewable procurement landing in Scope 2 MBM, not by
  anything the customer did.

**Per-account breakdown** — only when the Step 5.1 `USAGE_ACCOUNT_ID` call (or the CSV's
account column) returned more than one account:

| Account | Total MTCO2e (LBM) | Total MTCO2e (MBM) | Share of total (LBM) | Months present |

Totals cover the same window as the table above. State beneath it that this is a
management-account view: consolidated data for member accounts, each for the time it was in
the organization, so `Months present` can differ between accounts. With one account, omit the
table and state that the data is a member or standalone view of that account.

**3b. Water** — annual only; omit this sub-section entirely if water is unavailable.

| Year | Total water withdrawn (m3) | Top service | Top Region | Water Model Version |

State beneath the water table: the figure is water **withdrawn** (not consumed), covers
**AWS data center operations only** (excluding water embodied in upstream electricity
generation), and is allocated top-down by proportional usage. Never combine it with carbon
into a single score.

Plus hotspot tables by service and by Region, and the Step 8 walkthrough if either figure
changed materially.

### 4. Workload Topology Summary
Resource counts by layer and Region, with the derived footprint per layer. State topology
coverage and any gaps.

### 5. SUS Assessment Scorecard
| Focus Area | Met | Partial | Not Met | N/A | Needs Human Input |
|------------|-----|---------|---------|-----|-------------------|
| SUS01 Region Selection (1 BP) | | | | | |
| SUS02 Alignment to Demand (6 BPs) | | | | | |
| SUS03 Software & Architecture (5 BPs) | | | | | |
| SUS04 Data Patterns (8 BPs) | | | | | |
| SUS05 Hardware & Services (4 BPs) | | | | | |
| SUS06 Development & Deployment (5 BPs) | | | | | |

### 6. Findings by Focus Area
| # | BP | Finding | Severity | Evidence | Recommendation | Est. Footprint Impact |

Express estimated impact in **resource terms** (vCPU-hours/month, weighted GB-months,
GB transferred), never in MTCO2e. For SUS05-BP02, that is vCPU-hours/month moved to Graviton,
plus any provisioned vCPU-hours removed when the target type is smaller.

### 7. Cost vs Carbon Divergence
Which divergence patterns from Step 6.1 were found, or an explicit statement that cost
and resource intensity are tracking each other in this workload.

### 8. Prioritised Actions
- Immediate (CRITICAL/HIGH — 30 days)
- Short-term (MEDIUM — 90 days)
- Long-term (LOW — next planning cycle)
- Needs human input (the practices the agent cannot assess)

Order Graviton actions as `references/graviton-migration.md` sets out: managed services,
then Lambda `.zip` functions, then containers, then self-managed EC2.

### 9. Appendix — References
- [Well-Architected Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html)
  and its [shared responsibility model](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/the-shared-responsibility-model.html)
- [AWS Sustainability User Guide](https://docs.aws.amazon.com/sustainability/latest/userguide/what-is-sustainability.html),
  [API Reference](https://docs.aws.amazon.com/sustainability/latest/APIReference/Welcome.html),
  [calculation methodology](https://docs.aws.amazon.com/sustainability/latest/userguide/methodology.html)
  ([water](https://docs.aws.amazon.com/sustainability/latest/userguide/methodology-water.html))
- When the AI/ML reference was used: [Machine Learning Lens](https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html)
  and [Generative AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html)
- When a SUS05-BP02 Graviton finding appears: [AWS Graviton](https://aws.amazon.com/ec2/graviton/)
  and the [Graviton transition guide](https://github.com/aws/aws-graviton-getting-started/blob/main/transition-guide.md)

## Severity Definitions

| Severity | Definition | Timeline |
|----------|------------|----------|
| CRITICAL | Large, unambiguous waste — significant resource consumption with no business value | 30 days |
| HIGH | Substantial efficiency gap with a clear remediation path | 30 days |
| MEDIUM | Meaningful improvement opportunity, or one requiring design change | 90 days |
| LOW | Minor optimization or governance gap | Next planning cycle |
| INFO | Observation, or outside the agent's visibility | N/A |

Severity reflects **resource-footprint impact and remediation effort**, not operational risk.
A CRITICAL sustainability finding is not an outage risk.
