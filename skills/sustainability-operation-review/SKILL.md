---
name: sustainability-operation-review
description: Workload sustainability review aligned with the AWS Well-Architected
  Sustainability Pillar (SUS01-SUS06), combining carbon emissions and water
  withdrawal data from the AWS Sustainability API with topology-derived resource
  intensity KPIs. Use this skill when a user asks to review or audit a workload's
  sustainability posture, carbon footprint, emissions, water usage, environmental
  impact, or resource efficiency. Activate on requests like "sustainability
  review", "carbon footprint analysis", "Well-Architected sustainability
  assessment", "why did my emissions increase", "reduce our carbon footprint",
  "sustainability KPIs", "green IT review", or "SUS pillar audit". Also activate
  when emissions rose despite optimization work, when a user asks for emissions by
  linked account, service or Region, or about Graviton for sustainability, attaches
  a carbon or water CSV export from the AWS Sustainability console, or asks
  about AI/ML workloads on Amazon SageMaker AI, Amazon Bedrock, or GPU,
  Inferentia or Trainium instances.
metadata:
  author: rrrazvan
  version: "1.0.0"
  summary: "Well-Architected Sustainability review: resource-intensity KPIs as the assessment, carbon emissions as context, plus Graviton and AI/ML checks."
  aws-devops-agent-skills.agent-types: "CHAT, PREVENTION"
  aws-devops-agent-skills.aws-services: "AWS Sustainability, Amazon EC2, Amazon S3, AWS Lambda, Amazon RDS, Amazon SageMaker AI, Amazon Bedrock"
  aws-devops-agent-skills.technical-domains: "Sustainability, Cost Optimization"
---

# Workload Sustainability Review

Review a workload against the 29 best practices of the
[AWS Well-Architected Sustainability Pillar](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/sustainability-pillar.html).
Resource intensity KPIs derived from the topology are the assessment; emissions from the
[AWS Sustainability API](https://docs.aws.amazon.com/sustainability/latest/APIReference/Welcome.html)
are context.

## ⚠️ Critical — read first

- **Load each named file in full, at the step that names it**, with `read_skill_resource`.
  Never `distill` or summarize this skill or its files in their place, and never grade from memory.
- **If a load fails, say so.** Start the report with `⚠️ <file> could not be loaded: <verbatim
  error>`, do not replace its rules with general knowledge, and mark the practices that depend
  on it NEEDS HUMAN INPUT.
- **Emissions are context; resource intensity KPIs are the assessment.** Never attribute a
  change in reported emissions to a customer action, and never state a recommendation's impact
  in MTCO2e. Use vCPU-hours, weighted GB-months, GB transferred, accelerator-hours or tokens.
- **Never estimate CO2e** for a Graviton migration, AI/ML workload, token, inference or training
  run. Quote AWS's Graviton energy statement only as AWS's.
- **Sanity-check emissions against the topology** (Step 6). Zero or near-zero emissions next
  to a sizeable fleet, or emissions shares that don't match where the resources are, mean the
  two inputs cover different scopes. Report that as a finding; never explain it away.
- **Only a service-returned `AccessDeniedException` is a permissions gap**; name the missing
  action. For any other failure, record the message verbatim, recommend no IAM change, and
  name no permission, not even as a conditional.
- **Absent or zero emissions are below the reporting threshold** (0.5 g CO2e, 0.5 mL water),
  not zero impact. Carbon for month M publishes by the 21st of M+1, so before the 21st the
  latest month can be two back. That is the normal one-month lag, not missing data.
- **Never invent a business output metric.** Use the Step 1 fallback and say which.
- **Grade all 29 practices.** Never mark one MET without evidence; use NEEDS HUMAN INPUT.
- **Read-only.** Never call `Modify*`, `Delete*`, `Terminate*` or `Create*`. Every
  recommendation is for a human to action.
- **Never call efficiency work immaterial.** Provisioning decides how much AWS infrastructure
  is allocated to the account; rightsizing and decommissioning reduce it.
- **Compare months per day.** A 28-day month carries about 10% less than a 31-day one at the
  same usage; a delta smaller than the day-count difference is not a finding.
- **Always finish.** Produce the full report even when emissions data is unavailable.
- **The report artifact is the deliverable.** Create it with [assets/report-template.md](assets/report-template.md) at
  Step 9 even when the user asks specific questions; answer them in its Executive Summary, then
  summarize in chat.
- **Keep Steps 7–9 in this conversation.** If you delegate data collection, still load the
  checklist and the template yourself, grade all 29 practices, and write the report here.

## When to use

For architecture-level sustainability reviews. Not for per-instance rightsizing (point to
[AWS Compute Optimizer](https://docs.aws.amazon.com/compute-optimizer/latest/ug/what-is-compute-optimizer.html)),
cost reduction as the main goal, or incident-time analysis: there is no live carbon signal.

## Workflow checklist

- [ ] Step 1: Scope and business output metric
- [ ] Step 2: Topology — load [references/workload-model.md](references/workload-model.md)
- [ ] Step 3: Workload shape and triggers
- [ ] Step 4: Resource intensity inputs — load [references/proxy-metrics.md](references/proxy-metrics.md)
- [ ] Step 5: Environmental impact data — load [references/framing-and-attribution.md](references/framing-and-attribution.md),
  [references/emissions-collection.md](references/emissions-collection.md) and [references/emissions-api-reference.md](references/emissions-api-reference.md)
- [ ] Step 6: KPIs, emissions sanity check, cost–carbon divergence
- [ ] Step 7: Assess all 29 practices — load [references/sus-best-practices-checklist.md](references/sus-best-practices-checklist.md)
- [ ] Step 8: Explain emissions changes
- [ ] Step 9: Report — load [assets/report-template.md](assets/report-template.md)

Do not start a step before the previous one is done. Do not start Step 7 or Step 9 until its
file is loaded.

### Step 1 — Scope and business output metric

Ask for the scope (an entry point, application, set of accounts, or "everything in this
account"; default: all configured Regions) and the business output metric — the unit of work
the workload produces. It is the denominator of every intensity KPI. If there is none, use the
first available fallback and state its caveat:

1. Request count — ALB `RequestCount`, API Gateway `Count`, CloudFront `Requests`
2. Invocation count — Lambda `Invocations`, SQS `NumberOfMessagesDeleted`
3. Data processed — S3 `BytesDownloaded`, Kinesis `IncomingRecords`
4. None — report absolute footprint only, and make SUS06-BP01 the top recommendation

### Step 2 — Topology

Load [references/workload-model.md](references/workload-model.md). Walk the Agent Space topology from the entry point,
classify every resource into a layer, and record each resource's Region. Fill gaps with
`tag:GetResources` and service `Describe*` calls, and state any coverage gap.

### Step 3 — Shape and triggers

Detect the workload shape with the table in `workload-model.md` and state the evidence.
- ML / accelerated shape, or `Invocations` in the `AWS/Bedrock` namespace → load
  [references/ai-ml-workloads.md](references/ai-ml-workloads.md).
- Any x86 compute or managed instance class → load [references/graviton-migration.md](references/graviton-migration.md).

### Step 4 — Resource intensity inputs

Load [references/proxy-metrics.md](references/proxy-metrics.md). Over 30 days at `Period: 3600`, derive provisioned and
utilized vCPU-hours (vCPU × hours × utilization, never instance counts), weighted GB-months
and weighted GB transferred, and the business output for the same window. Record each
resource's architecture (`x86_64` or `arm64`) and instance generation. The storage and
network weights are directional, not a carbon model; say so in the report. For AI/ML, collect
the inputs listed in `ai-ml-workloads.md`.

### Step 5 — Environmental impact data

Load [references/framing-and-attribution.md](references/framing-and-attribution.md) and [references/emissions-collection.md](references/emissions-collection.md), and
read [references/emissions-api-reference.md](references/emissions-api-reference.md) before the first call. If a carbon or water `.csv`
export is attached, or the customer prefers to supply one instead of granting API access, load
[references/csv-emissions-input.md](references/csv-emissions-input.md) first; an attached export wins over the API for its metric.
- Carbon: `GetEstimatedCarbonEmissions`, 14 months, `MONTHLY`, paginated — one call grouped by
  `SERVICE` and `REGION`, one by `USAGE_ACCOUNT_ID`. More than one account returned is a
  management-account view: report per account and say so. Only this account is a member or
  standalone view. Never assert either without that evidence. Only EC2, S3 and CloudFront are
  broken out by service; the rest is "Other". `GetEstimatedCarbonEmissionsDimensionValues` is
  optional; if it fails, continue.
- Water: `GetEstimatedWaterAllocation`, `YEARLY_CALENDAR`, `Start` on 1 January. Whatever the
  source, API or export, always state: m3, annual only, water **withdrawn (not consumed)**, AWS
  data-center operations only, excluding water embodied in upstream electricity. It is
  disclosure only: no Well-Architected practice or KPI is water-specific, so derive no finding,
  KPI, trend driver or recommendation from it, and never attribute a change in it to the
  customer. If asked how to reduce it, say in one sentence that the review's resource-efficiency
  findings are the only levers; list no water actions.
  If the call fails or returns nothing, ask for a water export from the Sustainability console
  and load [references/csv-emissions-input.md](references/csv-emissions-input.md).
- Attempt carbon and water independently, record the `ModelVersion`, and handle every failure
  with the "no data" table in `emissions-collection.md`.

### Step 6 — KPIs and checks

Use the KPI set in `proxy-metrics.md` that fits the shape: current value, 30 days prior,
change, direction. Add the Graviton KPIs from `graviton-migration.md`, and report AI/ML KPIs
from `ai-ml-workloads.md` in a separate table. Then:
- **Emissions sanity check** — compare emissions with the provisioned footprint using the
  tests in `proxy-metrics.md`. If one fails, report the scope mismatch as a finding.
- **Cost vs carbon divergence** — `ce:GetCostAndUsage` over the same window; test the five
  patterns in `proxy-metrics.md`. On `AccessDeniedException`, skip and say so. If none applies,
  say so plainly.

### Step 7 — Assess all 29 practices

Load [references/sus-best-practices-checklist.md](references/sus-best-practices-checklist.md). For every practice, apply its evidence,
NOT MET / PARTIAL criteria, severity and guard, and record status and evidence. Use
`graviton-migration.md` for SUS05-BP02 and the lens mapping in `ai-ml-workloads.md`, citing the
lens ID after the SUS ID, as in `SUS05-BP04 (MLSUS05-BP02)`. Never recommend a Region move
without confirmed residency, latency and service availability; report SUS05-BP01 at fleet
level only. Severity, from most to least urgent: CRITICAL, HIGH, MEDIUM, LOW, INFO. It reflects
resource-footprint impact and remediation effort, not operational risk; definitions are in
[assets/report-template.md](assets/report-template.md).

### Step 8 — Explain emissions changes

If reported emissions changed, work through the ordered causes in
`framing-and-attribution.md` before naming an architecture cause: comparison validity,
methodology version, grid intensity, AWS infrastructure, allocation share, scope and method,
then actual usage. A storage reduction that does not show in reported emissions is expected.

### Step 9 — Report

Load [assets/report-template.md](assets/report-template.md). Create one report artifact per workload, named
`sustainability-review-<workload-name>-<YYYY-MM-DD>.md`, with every section in order. State
impact in resource terms, and put failed file loads and unavailable data at the top.

Before presenting the report, check the draft and fix any failure:
- [ ] All 29 practices have a status, and every MET cites evidence.
- [ ] Every KPI and delta matches the collected data and the same 30-day window.
- [ ] No recommendation states impact in MTCO2e, and no CO2e estimate appears.
- [ ] Failed file loads and unavailable data are listed at the top, with verbatim errors.
- [ ] The emissions sanity check result is stated.
