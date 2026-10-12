---
name: sagemaker-ai-ops-review
description: Amazon SageMaker AI Operational Review. Use this skill when a user asks to
  review, audit, or assess Amazon SageMaker AI workloads (endpoints, training jobs,
  pipelines, notebooks, Studio domains) for best-practices posture across Security,
  Performance, Cost Optimization, Service Quotas, Resiliency, Operational Excellence,
  Sustainability, and Best Practices — including as an Operational Readiness Review (ORR)
  before a workload goes to production. Triggers on requests like "SageMaker AI review",
  "SageMaker ops review", "SageMaker best practices audit", "ML ops assessment", "review
  my SageMaker account", "SageMaker health check", "pre-production readiness check for
  SageMaker", or "Operational Readiness Review (ORR) for SageMaker".
metadata:
  author: jacklunn
  version: "1.1.2"
  aws-devops-agent-skills.agent-types: "Chat tasks, Evaluation"
  aws-devops-agent-skills.aws-services: "Amazon SageMaker AI, Amazon CloudWatch, AWS Service Quotas"
  aws-devops-agent-skills.technical-domains: "AI/ML"
---

# Amazon SageMaker AI Operational Review

Run the Amazon SageMaker AI operational review checks against a customer's Amazon SageMaker AI
resources and produce an **Amazon SageMaker AI Operational Review** report. It evaluates
**8 pillars, 20 checks** using native AWS APIs (via `use_aws`). The Best Practices pillar's
recommendations are grounded in the public AWS Well-Architected lenses — see `pillar-checks.md`.

This is a strict **READ-ONLY** review: data is collected through native AWS `List*` /
`Describe*` control-plane APIs, CloudWatch metric reads, `servicequotas:GetServiceQuota`,
`health:DescribeEvents`, and `savingsplans:DescribeSavingsPlans`. It performs no model
invocations, launches no jobs, and reads no inference payloads.

## When to Use

Activate this skill when the user asks to review, audit, or assess an Amazon SageMaker AI
workload, check SageMaker AI best-practices posture, or run an **Operational Readiness Review
(ORR)** for SageMaker AI — for one pillar, a subset of checks, or the full set.

The **ORR** use case is the primary one: run this review **before a team deploys a SageMaker AI
workload to production**, as the readiness gate. Because every finding is severity-ranked and
carries a concrete remediation, the report doubles as the pre-production punch list — clear the
High and Medium findings, then launch. It is equally suited to a recurring cadence afterwards
(weekly or monthly posture review) and to an ad-hoc audit of a newly inherited account.

## Pillars and Checks

Run checks grouped by pillar in the order below. **Load `references/pillar-checks.md`** for
each check's APIs, logic, thresholds, and output fields.

| Pillar | Checks |
|--------|--------|
| **Security** | Check Encryption · SageMaker VPC Check · VPC Configuration Check |
| **Performance** | SageMaker Endpoint Inference Type · SageMaker Endpoint Latency |
| **Cost Optimization** | SageMaker Resource Tagging Check · Trainium and Inferentia Usage · Autoscaling Endpoint Check · Sagemaker Savings Plan · Sagemaker Lifecycle Configurations · Sagemaker Inference Recommender Jobs Check · Sagemaker Stale Endpoints Check |
| **Service Quotas** | Service Quotas Check |
| **Resiliency** | SageMaker Endpoint Instances · SageMaker Lifecycle Events |
| **Operational Excellence** | Sagemaker Project Check · Sagemaker Pipeline Check · SageMaker Endpoint Datacapture Enabled Check |
| **Sustainability** | Domain Region Check |
| **Best Practices** | Well-Architected Recommendations (SageMaker AI) |

## Step 1: Identify Scope

Confirm with the user:
- **Account IDs** and **regions** to review (default: current account via `sts:GetCallerIdentity`). If regions are unspecified, discover active regions with `ce:GetCostAndUsage` (SERVICE = "Amazon SageMaker", grouped by REGION); Cost Explorer is payer-scoped, so if it returns nothing, **fall back** to sweeping a default region set with `sagemaker.list-endpoints`/`list-domains`/`list-notebook-instances`. Conclude "no activity" only after both come back empty.
- **Pillars or individual checks** to run (default: all 8 pillars / 20 checks).
- **Date range** for time-windowed checks (Latency = last 7 days, Stale Endpoints = last 90 days, Service Quotas usage = **trailing 24 hours** — these windows are fixed by the checks and must not be shortened; `references/pillar-checks.md` is authoritative on each).

## Step 2: Run the Checks

For each in-scope check, call the APIs listed in `references/pillar-checks.md` via `use_aws`
and build the check's result rows. Follow this behavior:

- **Read-only.** `List*` then `Describe*`; paginate every call that returns a token.
- **Per-check isolation.** Catch and record errors per check as a `{ error }` row — a failed
  check never aborts the review.
- **Three APIs are global — call them once in `us-east-1`, never inside the per-region loop:**
  `health` (`describe-events`, `describe-affected-entities`), `ce` (`get-cost-and-usage`), and
  `savingsplans` (`describe-savings-plans`). They have no regional endpoints. Looping them per
  region fails everywhere but `us-east-1`, and the failure mimics the checks' legitimate
  degradation paths — a Health error looks like "no Business/Enterprise Support plan", a Savings
  Plans error looks like "permission not granted" — so the report states a plausible wrong reason
  instead of surfacing a bug. Health returns events for all regions; filter to the in-scope
  regions client-side.
- **Units are part of every number.** Where a metric has a unit, the report carries it. In
  particular `ModelLatency` / `OverheadLatency` are published in **microseconds** — label the
  column and also give the millisecond conversion. An unlabelled six-figure latency reads as
  milliseconds and manufactures a false performance escalation.
- **Permissions / graceful degradation.** Nearly all APIs are covered by the AWS-managed
  `AIDevOpsAgentAccessPolicy` on the DevOps Agent role. The one exception —
  `savingsplans:DescribeSavingsPlans` (Savings Plan check) — is an optional add-on. The AWS
  Health APIs used by the Lifecycle Events check are covered by the managed policy but
  additionally require a Business/Enterprise Support plan. On AccessDenied for a check, report it
  as **"not evaluated — permission not granted"** and continue; never emit a false "none found"
  from an access error.
- **Empty results** (permission present, nothing there) produce a single "No <resource> found"
  row, not a dropped section.
- **Severity-ranked findings.** Assign each finding a severity per `references/pillar-checks.md`:
  **High**, **Medium**, **Low**, or **Informational** (inventory checks with no pass/fail signal).
  Checks with a compliance signal set severity as defined there — e.g. Studio domain not `VpcOnly`
  → High; no autoscaling / an Inference Component endpoint whose host instance fleet is fixed while its
  components autoscale / idle endpoint at least 90 days old / notebook with no customer-managed
  KMS key / no VPC config / Savings Plan expired or within 30 days of expiry / AWS Health event with
  `actionability = ACTION_REQUIRED` → Medium; missing tags / data capture disabled → Low. The Service
  Quotas Check derives its tier from utilization (≥ 90% High, ≥ 75% Medium, else Low; Unknown if no
  usage data).
- **One finding = one non-compliant resource in one check**, keyed by `(check, region, resource)`.
  Do **not** aggregate resources into a single finding — three notebooks with no customer-managed
  key are three Medium findings, not one. Aggregation breaks the severity counts and makes runs incomparable.
- **One recommendation per High or Medium finding.** Emit exactly one concrete, SageMaker-specific
  recommendation for every High and Medium finding. Low and Informational findings do not require one.
- Use only the severities each check defines; do **not** invent thresholds a check does not define.

## Step 3: Generate the Report

Produce a single Markdown report titled **"Amazon SageMaker AI Operational Review"**, with the
structure below.

```markdown
# Amazon SageMaker AI Operational Review

**Account IDs:** <comma-separated account IDs>
**Regions:** <comma-separated regions>
**Date Range:** <range or "Not specified">

> **AI Disclaimer:** The AI-generated insights in this report are provided for informational purposes only. They should be reviewed and validated by qualified personnel before taking any action. AWS is not responsible for any decisions made based on AI-generated content.

## Executive Summary

<severity-ranked roll-up of findings across all pillars: count by severity (High / Medium /
Low), then the High and Medium findings listed most-severe first, each with its one-line
recommendation. Omit only if there are no High/Medium/Low findings at all.>

## <Pillar Name>

### <Check Name>

**Guidance**

<what the check evaluates and the relevant SageMaker best practice>

**AI Insights**

<optional per-check analysis of the gathered data; prefix with a note that it is AI-generated and must be verified. Omit if not generated.>

**Data**

<a Markdown table of the check's result rows (fields per references/pillar-checks.md, including a `severity` column for checks that define one), or "No data available for this check.">

**Recommendations**

<one concrete SageMaker-specific recommendation per High or Medium finding in this check, each labelled with its severity. Omit this block entirely if the check has no High/Medium findings.>
```

Rules:
- Emit the **AI Disclaimer blockquote verbatim**, immediately after the header.
- **Date Range** is a single short value — the review timestamp, or a date range when the user
  scoped one (e.g. `2026-09-18 (point-in-time)`). Do **not** inline every check's window into it;
  per-check windows are fixed by the checks and belong in each check's own section.
- One `##` section per **in-scope pillar**, in the table order above; one `###` sub-section per
  check in that pillar. Include every in-scope check even when it found nothing (render its
  empty-state row).
- The **Executive Summary** ranks findings by severity (High → Medium → Low). Include it whenever
  any finding carries a severity; it is what makes the report prioritized and actionable.
- **The Executive Summary must contain every High and Medium finding from every pillar**, and its
  severity counts must reconcile exactly with the per-check sections: if the pillar sections contain
  12 Medium findings, the summary says 12 and lists 12 rows. Before emitting the report, count the
  High/Medium findings per pillar and check the totals match. Findings from pillars other than
  Security and Cost Optimization are the ones most often dropped — Resiliency Health events in
  particular. A finding that is scored Medium in its check but missing from the summary is invisible
  to the reader, which defeats the point of ranking at all.
- The **AI Insights** block per check is optional; when included, carry the AI-generated /
  verify-before-use caveat.
- Render each check's **Data** as a table of the fields defined in `references/pillar-checks.md`,
  including the `severity` field for checks that define one.
- Emit a **Recommendations** block for every check that has at least one High or Medium finding —
  exactly one recommendation per such finding. Skip the block for checks with only Low or
  Informational findings.

## Constraints

- READ-ONLY — no resource mutation, no endpoint invocation, no job launches, no payload reads.
- Report only what the APIs return. Do NOT fabricate data or assume unobserved configuration.
- **No invented numbers.** State a quota, limit, instance price, monthly cost, or percentage saving
  only if an API call returned it. Never substitute a default limit for an applied one, never
  estimate spend from remembered pricing, and never attach "~" or "up to" to a figure you did not
  read. If a number would help but was not retrieved, point the reader at the console page or API
  that has it. See the "Never state a number the APIs did not return" rule in
  `references/pillar-checks.md`.
- Paginate ALL calls that return a pagination token.
- Empty-scope precedence: if **every** in-scope check across **all** in-scope accounts/regions
  returns no resources, skip the per-pillar report and instead report the single line
  "No SageMaker AI activity detected." Otherwise render the full report — each check that found
  nothing gets its own empty-state row (Step 2), never the terse message.
- Keep all guidance and recommendations specific to Amazon SageMaker AI.

## Scope Limitations — state these in the report, do not overclaim past them

These bound what the review can honestly conclude. The skill's README is **not** packaged into the
uploaded skill, so these are restated here where the runtime can actually read them. Where a
limitation applies to a check you ran, say so in that check's **Guidance** rather than letting the
reader assume wider coverage.

- **`Check Encryption` covers notebook instances only.** Training jobs, processing jobs, endpoint
  configs, S3 model artifacts, and Feature Store stores are **not** assessed for encryption. Never
  present the Security pillar as a complete encryption audit — name the gap. Note also that a
  notebook without a `KmsKeyId` is still encrypted (system-managed key); the finding is the absence
  of a **customer-managed** key, never "not encrypted". The remediation is **re-creation**, not an
  update — `UpdateNotebookInstance` has no `KmsKeyId` parameter, so never name it; the key is settable
  only at creation.
- **No Feature Store or Model Registry checks.** Neither is inventoried or assessed. If a user asks
  about feature groups or model packages, say plainly that this review does not cover them rather
  than returning a clean report that implies they passed.
- **Control-plane and metrics only.** Configuration and CloudWatch signals. The review cannot assess
  model quality, training convergence, data drift, bias, or anything needing inference payloads or
  job artifacts.
- **No cost figures.** Cost Explorer is used for region discovery only, never spend attribution. The
  Savings Plan check reports coverage and expiry — not dollar savings, and it measures no spend at
  all, so it never recommends a purchase off an assumed spend level.
- **Point-in-time.** Findings reflect state at run time. Service Quotas utilization is scored over a
  fixed trailing 24-hour window, so a spike outside it is invisible.
- **Best Practices pillar is advisory.** Well-Architected-grounded guidance, no per-resource findings,
  no API calls.
- **Large estates may need scoping.** Many endpoints across many regions can exhaust the run budget;
  if a run is at risk of truncating, tell the user to scope to fewer regions or pillars rather than
  silently dropping checks.

## Data Source Boundaries

Native AWS APIs only: `sagemaker`, `cloudwatch` (`get-metric-statistics`, `get-metric-data`,
`list-metrics`), `application-autoscaling` (`describe-scalable-targets`,
`describe-scaling-policies`), `servicequotas` (`get-service-quota`), `ce` (`get-cost-and-usage`
for region discovery), `health` (`describe-events`, `describe-affected-entities`), plus the one
optional add-on `savingsplans` (`describe-savings-plans`). All but that add-on are covered by
the AWS-managed `AIDevOpsAgentAccessPolicy`. `health`, `ce`, and `savingsplans` are **global** —
call each once against `us-east-1`, outside the per-region loop. No data-plane calls and no
non-AWS tooling — the skill is self-contained on the DevOps Agent's cloud-source IAM role.
