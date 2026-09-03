---
name: analytics-dataops-expertise
description: "Amazon DataOps maturity assessment. Performs read-only, API-driven scoring of a customer's data platform across five fixed dimensions: Architecture, Security & Governance, Incident Management & Observability, Automation & Testing, and Cost. Activate this skill for requests about DataOps maturity, data-platform assessment, analytics maturity, data architecture review, data governance posture, pipeline/orchestration maturity, real-time/streaming data, or data cost optimization. Given an account ID and region, it scores 26 questions 1-5 from live account signals, rolls them up into those five dimensions, and produces a structured scorecard with prioritized recommendations. All checks use read-only AWS control-plane APIs (glue, kinesis, dms, rds, cloudwatch, kms, s3, iam, config, backup, mwaa, sfn, macie2, resourcegroupstaggingapi, costexplorer, costoptimizationhub) — no data-plane access required."
metadata:
  version: "1.1.0"
  author: prasadnu
---

# DataOps Maturity Assessment

## Overview

This skill performs a read-only DataOps maturity assessment of a customer's AWS
data platform using control-plane APIs available through the account's AWS
profile. It scores each dimension on a **1-5 maturity scale** and produces a
structured scorecard with findings and actionable recommendations.

> **Scope:** CLI-agent compatible. Account-scoped, read-only, control-plane only.
> No external packages, no IDE workspace, no data-plane access (no queries
> against catalogs, tables, or indices).

## Trigger Keywords

`dataops`, `dataops maturity`, `data platform assessment`, `analytics maturity`,
`data architecture review`, `data governance`, `data platform health`,
`data maturity`, `data pipeline maturity`, `data cost optimization`,
`data observability`

## Prerequisites

- AWS CLI profile configured with read-only access to the target account
- **Account ID and region** for the assessment (the scorer is account + region scoped)
- IAM permissions required (all read-only). Most are covered by a read-only /
  ViewOnly managed policy; attach the supplemental permissions for any gaps:
  - `glue:GetDatabases`, `glue:GetJobs`, `glue:GetCrawlers`, `glue:ListRegistries`, `glue:ListSchemas`, `glue:ListDataQualityRulesets`, `glue:ListDataQualityResults`, `glue:ListWorkflows`, `glue:GetJob`
  - `lakeformation:GetDataLakeSettings`, `lakeformation:ListPermissions`, `lakeformation:ListDataCellsFilter`
  - `kinesis:ListStreams`, `firehose:ListDeliveryStreams`, `kinesisanalyticsv2:ListApplications`, `kafka:ListClustersV2`
  - `dms:DescribeReplicationTasks`, `dms:DescribeReplicationInstances`, `dms:DescribeEndpoints`, `dms:DescribeEventSubscriptions`
  - `dynamodb:ListTables`, `dynamodb:DescribeTable`, `dynamodb:DescribeContinuousBackups`
  - `application-autoscaling:DescribeScalableTargets`, `autoscaling:DescribeAutoScalingGroups`
  - `rds:DescribeDBInstances`, `rds:DescribeDBEngineVersions`
  - `es:DescribeDomain`, `es:ListDomainNames`, `redshift:DescribeClusters`
  - `backup:ListBackupPlans`
  - `cloudwatch:DescribeAlarms`, `cloudwatch:ListDashboards`, `cloudwatch:GetMetricData`
  - `sns:ListTopics`, `events:ListRules`
  - `xray:GetSamplingRules`, `xray:GetGroups`, `rum:ListAppMonitors`, `quicksight:ListDashboards`
  - `cloudformation:ListStacks`, `codepipeline:ListPipelines`, `codecommit:ListRepositories`
  - `mwaa:ListEnvironments`, `states:ListStateMachines`, `ssm:DescribePatchBaselines`
  - `lambda:ListFunctions`
  - `macie2:GetMacieSession`, `macie2:ListClassificationJobs`
  - `kms:ListKeys`, `s3:ListAllMyBuckets`, `s3:GetBucketLifecycleConfiguration`
  - `iam:ListPolicies`, `config:DescribeConfigRules`, `config:DescribeComplianceByConfigRule`
  - `resourcegroupstaggingapi:GetResources`
  - `ce:GetCostAndUsage`, `ce:GetTags` (Cost Explorer must be enabled; call in `us-east-1`)
  - `cost-optimization-hub:ListRecommendations`

**AWS resources:** one or more analytics/data services in the target
account/region (Glue, Kinesis, MSK, DMS, DynamoDB, RDS, OpenSearch, Redshift,
EMR, MWAA, etc.). Absence of a service is itself a valid (low-maturity) signal.

## Execution Flow

### Input

**Required:** account ID + region (e.g., `123456789012` / `eu-west-1`).

If the account or region is missing, ask for it — do not assume. The assessment
runs against exactly the account + region provided.

### Steps

```
1. Confirm target account ID + region with the user.
2. For each question, call its control-plane APIs (see Checks below). Any API
   that errors or is not available in the region → treat as "not present"
   (a score-1 signal), never as a blocker.
3. Score each question 1-5 using the rating scale + logic in its section.
   Respect per-question auto-score ceilings (some questions cap at 3 — see below).
4. Roll up to per-section and overall averages.
5. Load the Remediation Reference — read_skill_resource(skill_id='analytics-dataops-expertise',
   path='references/remediation-reference.md') — MANDATORY before writing recommendations.
6. Generate the scorecard with prioritized recommendations, following the Output
   Format section EXACTLY. Write the full report content literally — the header,
   Summary table, all findings, all recommendations, and all 26 matrix rows must
   contain real computed values, never placeholder labels or a promise of content
   (see the LITERAL-CONTENT RULE). If saving an artifact, verify it holds the same
   fully-expanded content before finishing.
```

## Scoring model

- Every question is scored **1 (lowest) to 5 (highest)** against the rating scale
  in its section. Pick the highest rating whose conditions are fully met by the
  observed signals; if signals fall between two ratings, choose the lower.
- **Auto-score ceiling (apply exactly).** Some questions cannot be fully
  confirmed from control-plane signals alone (existence of a resource ≠ mature
  use of it). These are capped — never score them above the cap from API signals;
  state that ratings above the cap require conversational confirmation:
  - **Cap = 3:** Q6, Q8, Q11, Q13, Q14, Q19, Q20, Q23, Q24, Q26, Q30, Q37, Q38, Q39
  - **No cap (score 1-5 from signals):** Q3, Q4, Q5, Q7, Q12, Q25, Q29, Q31, Q32, Q33, Q36, Q40
- **API errors / missing services are score-1 signals**, not SKIPPED. A region
  with no Kinesis/MSK/Flink is genuinely "no real-time processing" (Q4 = 1). Only
  mark a question SKIPPED if EVERY API it needs is denied by IAM (state which).
- **No internal data.** This skill uses only account control-plane APIs. It does
  NOT use support-case history, internal customer records, or any AWS-internal
  data source. Do not infer or fabricate such signals.

## Checks & Decision Logic

Each check names the AWS API(s), the field(s) to read, and how observed signals
map to the 1-5 rating. All CloudWatch metrics use namespace as noted with the
account ID as the `ClientId`/account dimension where applicable.

### Category 1: Architecture

#### Q3 — Data Architecture Patterns (no cap)
- **APIs:** `glue.GetDatabases`, `glue.GetJobs`, `glue.GetCrawlers`, `lakeformation.GetDataLakeSettings`
- **Signals:** database/table count; active crawlers; Lake Formation governance (LF-Tags, non-`IAM_ALLOWED_PRINCIPALS` default perms); open-table-format indicators.
- **Rating:**
  - 1: No catalog structure/governance; ad-hoc storage; no crawlers.
  - 2: Basic catalog; few tables; no open formats; limited governance.
  - 3: Structured catalog (≥3 databases, active crawlers); some governance; open formats emerging.
  - 4: Well-organized catalog with clear domains; regular maintenance; comprehensive governance (LF-Tags in use).
  - 5: Federated governance; automated maintenance + health alerting; self-serve discovery.

#### Q4 — Real-time Data Processing (no cap)
- **APIs:** `kinesis.ListStreams`, `firehose.ListDeliveryStreams`, `kinesisanalyticsv2.ListApplications`, `kafka.ListClustersV2`
- **Signals:** count of streams / firehoses / running Flink apps / ACTIVE MSK clusters.
- **Rating:**
  - 1: No streaming resources — all batch.
  - 2: Basic streaming ingestion only (e.g., a stream or firehose), no stream processing.
  - 3: Streaming ingestion + some real-time transforms (Flink/Kinesis Analytics present).
  - 4: Comprehensive streaming pipelines with real-time transformations.
  - 5: End-to-end streaming architecture with real-time analytics across critical data.

#### Q5 — Change Data Capture (no cap)
- **APIs:** `dms.DescribeReplicationTasks/Instances/Endpoints/EventSubscriptions`, `dynamodb.ListTables` + `DescribeTable` (Streams)
- **Signals:** CDC-type DMS tasks (`cdc` / `full-load-and-cdc`); DMS event subscriptions; DynamoDB Streams enabled.
- **Rating:**
  - 1: No CDC; full refreshes only.
  - 2: Basic/manual CDC; limited validation; no monitoring.
  - 3: Automated delta loads (DMS CDC tasks present); basic integrity validation.
  - 4: Real-time CDC + automated integrity checks + monitoring/alerting (event subscriptions).
  - 5: Intelligent change detection + automated recovery + cross-platform sync with audit trails.

#### Q6 — Capacity Planning (cap 3)
- **APIs:** `application-autoscaling.DescribeScalableTargets` (dynamodb/ecs/kafka/lambda), `autoscaling.DescribeAutoScalingGroups`
- **Signals:** presence of auto-scaling policies; scheduled scaling.
- **Rating:**
  - 1: No auto-scaling; purely manual.
  - 2: Basic target tracking on some services; reactive.
  - 3: Multiple services auto-scaled; some scheduled scaling. **(Max from signals.)**
  - 4-5: Predictive/ML-based scaling + forecasting — requires conversation to confirm.

#### Q7 — Fault Tolerance & High Availability (no cap)
- **APIs:** `rds.DescribeDBInstances` (MultiAZ, read replicas), `es.DescribeDomain` (ZoneAwareness), `kafka.ListClustersV2` (broker count/AZ), `redshift.DescribeClusters`
- **Signals:** Multi-AZ coverage across stateful services; read replicas; MSK multi-broker.
- **Rating:**
  - 1: Single-AZ; no replicas/redundancy.
  - 2: Multi-AZ on 1-2 services; no replicas.
  - 3: Multi-AZ on primary data services; some read replicas.
  - 4: Multi-AZ everywhere + automated failover + read replicas on critical DBs; MSK multi-broker.
  - 5: All Rating 4 + cross-region replicas; full redundancy on all stateful services.

#### Q8 — Disaster Recovery (cap 3)
- **APIs:** `backup.ListBackupPlans`, `rds.DescribeDBInstances` (PITR/`latestRestorableTime`)
- **Signals:** backup plans with recent `lastExecutionDate`; PITR coverage; cross-region backup copies.
- **Rating:**
  - 1: No backup plans; no DR capability.
  - 2: Backup plans exist; some PITR; no cross-region; no formal RPO/RTO.
  - 3: Backup plans + cross-region/backup replication; long retention; PITR on critical DBs. **(Max from signals.)**
  - 4-5: Defined/tested RPO-RTO, automated failover, DR drills — requires conversation to confirm.

### Category 2: Security & Governance

#### Q29 — Metadata Management & Catalog (no cap)
- **APIs:** `glue.GetDatabases`, `glue.GetCrawlers`, `lakeformation.GetDataLakeSettings`
- **Signals:** total tables; table description coverage; active crawlers; Lake Formation governed mode + LF-Tags.
- **Rating:**
  - 1: No centralized catalog; manual discovery.
  - 2: Basic/manual catalog (<50 tables, no crawlers); inconsistent metadata.
  - 3: Automated metadata (≥50 tables OR active crawlers with ≥20 tables); standardized cataloging.
  - 4: Comprehensive catalog + lineage + business context; integrated governance.
  - 5: ML-powered classification/recommendations; self-maintaining metadata.

#### Q30 — Lineage (cap 3)
- **APIs:** `glue.ListWorkflows`, `glue.GetJobs` (job bookmarks / dependencies)
- **Signals:** Glue Workflows (implicit lineage); job dependency graphs. Lineage is largely a data-plane/tooling property — do not over-credit from control-plane signals.
- **Rating:**
  - 1: No lineage tracking.
  - 2: Ad-hoc dependency mapping.
  - 3: Lineage for select pipelines (Glue Workflows present), manual/inconsistent. **(Max from signals — 4-5 require confirmation of automated end-to-end lineage tooling.)**

#### Q31 — Data Classification (no cap)
- **APIs:** `macie2.GetMacieSession`, `macie2.ListClassificationJobs`, `lakeformation.ListDataCellsFilter`
- **Signals:** Macie enabled + active classification jobs; LF cell-level filters.
- **Rating:**
  - 1: No classification; Macie disabled.
  - 2: Macie enabled but no active jobs.
  - 3: Active Macie scanning + regular jobs; some LF cell filters; documented policy.
  - 4: Comprehensive automated classification + LF-Tag-based policy enforcement.
  - 5: ML-driven classification with predictive insights; automated remediation.

#### Q32 — Data Protection (no cap)
- **APIs:** `kms.ListKeys`, `s3.ListAllMyBuckets` (+ per-bucket encryption), `rds.DescribeDBInstances` (`StorageEncrypted`, PITR), `dynamodb.DescribeContinuousBackups`
- **Signals:** customer-managed KMS keys; S3 default encryption; RDS storage encryption + PITR; DynamoDB PITR.
- **Rating:**
  - 1: No/minimal encryption; no PITR.
  - 2: Default encryption on some services; inconsistent.
  - 3: Encryption at rest across most data services; PITR on critical stores.
  - 4: CMK encryption + PITR everywhere + key rotation.
  - 5: All Rating 4 + automated key management + cross-account/region protection controls.

#### Q33 — Access Control (no cap)
- **APIs:** `lakeformation.ListPermissions`, `iam.ListPolicies`, `config.DescribeConfigRules`, `config.DescribeComplianceByConfigRule`
- **Signals:** Lake Formation permissions (fine-grained data access); least-privilege IAM; Config rules for governance + compliance status.
- **Rating:**
  - 1: No fine-grained access control; broad IAM; no Config rules.
  - 2: Basic IAM; no LF permissions; few/no Config rules.
  - 3: LF permissions in use; Config rules present; some compliance tracking.
  - 4: Comprehensive fine-grained access + Config compliance largely COMPLIANT.
  - 5: Automated least-privilege + continuous compliance enforcement + attribute-based access.

### Category 3: Incident Management & Observability

#### Q11 — Workload Analytics (cap 3)
- **APIs:** `cloudwatch.ListDashboards`
- **Signals:** dashboards covering data-service namespaces; custom metrics.
- **Rating:**
  - 1: No dashboards/custom metrics.
  - 2: Some dashboards; default service metrics only.
  - 3: Dedicated data dashboards; custom metrics; multiple data namespaces. **(Max — dashboard existence ≠ active KPI-driven ops; 4-5 need confirmation.)**

#### Q12 — Monitoring & Optimization (no cap)
- **APIs:** `cloudwatch.DescribeAlarms`, `sns.ListTopics`, `events.ListRules`
- **Signals:** alarm coverage by data-service namespace; composite alarms; SNS topics; EventBridge rules (esp. → Lambda/SSM auto-remediation).
- **Rating:**
  - 1: No alarms on data services.
  - 2: Alarms on 1-2 data services; SNS linked; no EventBridge automation.
  - 3: Alarms on ≥3 data services; SNS subscriptions; some EventBridge rules targeting data services.
  - 4: Full alarm coverage across active data services; composite alarms; EventBridge → Lambda auto-remediation.
  - 5: All Rating 4 + anomaly detectors on data metrics; confirmed auto-remediation; Contributor Insights.

#### Q13 — Application Monitoring (cap 3)
- **APIs:** `xray.GetSamplingRules`, `xray.GetGroups`, `rum.ListAppMonitors`
- **Signals:** X-Ray sampling rules/groups; RUM monitors.
- **Rating:**
  - 1: No X-Ray/RUM/tracing.
  - 2: X-Ray on some services; default sampling.
  - 3: Custom sampling + X-Ray groups; some RUM monitors. **(Max — 4-5 need ServiceLens/OTel confirmation.)**

#### Q14 — Drift Detection (cap 3)
- **APIs:** `glue.ListRegistries`, `glue.ListSchemas`, `glue.ListDataQualityRulesets`
- **Signals:** Glue Schema Registry (schemas AVAILABLE); DQ rulesets.
- **Rating:**
  - 1: No Schema Registry; no DQ rulesets.
  - 2: One drift signal (a registry OR a ruleset).
  - 3: Active schemas + DQ rulesets (multiple drift signals). **(Max — 4-5 need enforced-on-producers confirmation.)**

#### Q19 — SLA Management (cap 3)
- **APIs:** `cloudwatch.DescribeAlarms` (treat-missing-data config, SLO-style alarms)
- **Signals:** alarms configured as SLIs/SLOs (latency/availability with sensible treat-missing-data).
- **Rating:**
  - 1: No SLI/SLO alarms.
  - 2: Basic availability alarms.
  - 3: Multiple SLI/SLO-style alarms with proper treat-missing-data. **(Max — formal SLA program needs confirmation.)**

#### Q20 — User Experience (cap 3)
- **APIs:** `rum.ListAppMonitors`, `quicksight.ListDashboards`
- **Signals:** RUM monitors; recently-published QuickSight dashboards.
- **Rating:**
  - 1: No UX monitoring.
  - 2: Some QuickSight dashboards; basic refresh visibility.
  - 3: RUM + dashboards; multiple UX signals active. **(Max — staleness alerting/SLIs need confirmation.)**

### Category 4: Automation & Testing

#### Q23 — Infrastructure Pipeline (cap 3)
- **APIs:** `cloudformation.ListStacks`, `codepipeline.ListPipelines`, `codecommit.ListRepositories`
- **Signals:** active CFN stacks (IaC); CodePipeline pipelines; repos.
- **Rating:**
  - 1: No IaC/pipelines; manual provisioning.
  - 2: Some CFN stacks OR one pipeline.
  - 3: IaC (active stacks) + CI/CD pipeline(s) present. **(Max — full GitOps/policy-as-code needs confirmation.)**

#### Q24 — Orchestration (cap 3)
- **APIs:** `mwaa.ListEnvironments`, `states.ListStateMachines`, `glue.ListWorkflows`
- **Signals:** count of orchestration tools present (MWAA / Step Functions / Glue Workflows).
- **Rating:**
  - 1: No orchestration; manual/cron.
  - 2: One orchestration tool; basic scheduling.
  - 3: Multiple orchestration tools; comprehensive coordination. **(Max — cross-pipeline SLA/self-healing needs confirmation.)**

#### Q25 — Version Management (no cap)
- **APIs:** `rds.DescribeDBInstances` + `rds.DescribeDBEngineVersions`, `lambda.ListFunctions` (runtimes), `ssm.DescribePatchBaselines`, `es.DescribeDomain` (engine version)
- **Signals:** engine/runtime currency vs latest; deprecated Lambda runtimes; patch baselines.
- **Rating:**
  - 1: No patch management; outdated versions; deprecated Lambda runtimes in use.
  - 2: Some patched; 2+ minor version lag; no scheduled windows.
  - 3: Most within 1-2 minor versions; some patch baselines; periodic upgrades.
  - 4: Automated patching + within 1 minor version + scheduled windows.
  - 5: All current; enforced patch baselines; zero deprecated runtimes; proactive cadence.

#### Q26 — Data Quality Testing (cap 3)
- **APIs:** `glue.ListDataQualityRulesets`, `glue.ListDataQualityResults`
- **Signals:** DQ rulesets; recent DQ results (active execution).
- **Rating:**
  - 1: No DQ rulesets.
  - 2: Rulesets defined but no recent results.
  - 3: Multiple rulesets + active execution (results present). **(Max — alerting-on-failure/coverage needs confirmation.)**

### Category 5: Cost

#### Q36 — Resource Tagging (no cap)
- **APIs:** `resourcegroupstaggingapi.GetResources`
- **Signals:** % of data resources tagged; presence of cost-allocation tags (Environment, Owner, CostCenter).
- **Rating:**
  - 1: <30% tagged; no cost-allocation tags.
  - 2: 30-60% tagged; ad-hoc tags.
  - 3: 60-80% tagged; cost-allocation tags active; standard tags used.
  - 4: >80% tagged; enforced tagging policy; periodic audits.
  - 5: Near-100% tagged; automated tag enforcement (Config/SCP); tag-driven cost governance.

#### Q37 — Chargeback / Showback (cap 3)
- **APIs:** `ce.GetCostAndUsage`, `ce.GetTags` *(Cost Explorer — enable it; call in `us-east-1`)*
- **Signals:** cost allocation tags active in CE; cost grouped by tag/service.
- **Rating:**
  - 1: No cost allocation; no CE tag usage.
  - 2: Some cost-allocation tags; basic CE reports; manual allocation.
  - 3: Cost-allocation tags active + used for allocation across services. **(Max — automated chargeback needs confirmation.)**
- If CE is not enabled / AccessDenied → score from tagging signals and note the CE gap; do not SKIP unless no signal at all.

#### Q38 — Storage Management (cap 3)
- **APIs:** `s3.ListAllMyBuckets` + `s3.GetBucketLifecycleConfiguration`
- **Signals:** buckets with lifecycle rules (tiering/expiration); Intelligent-Tiering.
- **Rating:**
  - 1: No lifecycle rules; no tiering.
  - 2: Lifecycle on some buckets; reactive cleanup.
  - 3: Lifecycle/tiering on most data buckets; standard retention. **(Max — automated optimization needs confirmation.)**

#### Q39 — Data Processing Cost (cap 3)
- **APIs:** `ce.GetCostAndUsage` (service filter), `emr.ListClusters`, `glue.GetJobs`
- **Signals:** EMR right-sizing/Spot; Glue worker sizing; processing cost trend from CE.
- **Rating:**
  - 1: No processing-cost management; on-demand only.
  - 2: Some cost awareness; manual reviews.
  - 3: Cost allocation tags + some optimization (Spot/right-sizing evident). **(Max — ML-based/zero-waste needs confirmation.)**

#### Q40 — Unused Resources (no cap)
- **APIs:** `cost-optimization-hub.ListRecommendations`
- **Signals:** count/value of idle/unused-resource recommendations; whether COH is active.
- **Rating:**
  - 1: COH inactive / many unaddressed idle-resource recommendations; no cleanup cadence.
  - 2: Manual periodic reviews; some Trusted Advisor checks; reactive cleanup.
  - 3: COH active; recommendations generated; some cleanup cadence.
  - 4: Regular recommendation review + remediation; low idle-resource footprint.
  - 5: Automated detection + remediation; near-zero unused resources.

### Remediation Reference rule (apply exactly)

For EVERY question scored **≤ 3**, the Prioritized Recommendations section MUST
include that question's entry from `references/remediation-reference.md` (loaded
in Execution Flow step 5 via read_skill_resource): copy the "Why it matters" line
and "Resolve" steps verbatim, and include the "Dive deeper" link(s) EXACTLY as
written. NEVER emit a documentation link that is not present in the Remediation
Reference — do not construct, recall, or infer URLs from any other source.
Questions scored 4-5 get no remediation entry.

## Output Format

> **MANDATORY COVERAGE RULE:** The scorecard MUST evaluate and account for EVERY
> question (26 total: Q3, Q4, Q5, Q6, Q7, Q8, Q11, Q12, Q13, Q14, Q19, Q20, Q23,
> Q24, Q25, Q26, Q29, Q30, Q31, Q32, Q33, Q36, Q37, Q38, Q39, Q40). No question
> may be silently omitted. Before finishing, count the matrix rows: if not exactly
> 26, the report is incomplete — fix it before responding.
> **SECTION ROLL-UP:** each section's average = mean of its question scores.
> Overall = mean of all 26. Apply each question's rating scale and auto-score cap
> verbatim — never round a score up based on judgment.
> **EXACTLY FIVE DIMENSIONS (do not add, split, rename, or reorder).** The Summary
> table has EXACTLY these five sections with EXACTLY this question membership — this
> is fixed and must match the "Checks & Decision Logic" categories verbatim:
> - **Architecture** = Q3, Q4, Q5, Q6, Q7, Q8
> - **Security & Governance** = Q29, Q30, Q31, Q32, Q33
> - **Incident Mgmt & Observability** = Q11, Q12, Q13, Q14, Q19, Q20
> - **Automation & Testing** = Q23, Q24, Q25, Q26
> - **Cost** = Q36, Q37, Q38, Q39, Q40
>
> Real-time processing (Q4), CDC (Q5), capacity planning (Q6), fault tolerance (Q7),
> and disaster recovery (Q8) are QUESTIONS INSIDE the Architecture dimension — they
> are NEVER promoted to their own top-level dimensions. Reporting "7 dimensions", a
> "Real-time Processing" dimension, or a "Resilience" dimension is a SPEC VIOLATION —
> the scorecard must show five dimensions and five only.
>
> **LITERAL-CONTENT RULE (apply exactly — no placeholders).** Every section and
> every table row MUST contain the actual computed content, fully written out.
> This is the single most important rule for the report:
> - NEVER write a description, label, summary, or promise of content in place of
>   the content itself. Text like "full 3-tier content", "…included as persisted",
>   "see full artifact", "25 recommendations here", or a matrix row of the form
>   `{"q":"Q3"}` with empty columns is a FAILED report — it must be regenerated.
> - The Score Matrix MUST have 26 fully-populated rows: every row states the actual
>   Dimension, the numeric Score, the Cap, the real Observed signal (actual counts /
>   config values from the API calls), and the Rating rule applied. No empty cells.
> - The Dimensions section MUST contain, for all 26 questions, a per-question detail
>   block with the real score, confidence badge, one-line rationale, observed metrics
>   (real values), optional ⚠️ warning, and 💬 discussion-ask prompt(s) — never a
>   placeholder or a promise. Prioritized Recommendations + Remediation Detail MUST
>   contain the actual verbatim "Why it matters" + "Resolve" + "Dive deeper" text
>   (see rule above) for every question scored ≤ 3 — not a count of them.
> - The report's FIRST content MUST be the `# DataOps Maturity Assessment` header
>   and the Summary table, rendered literally with the real account ID, region,
>   timestamp, and scores — not a description of the header.
>
> **RENDERING METHOD (avoid truncation on large output).** This report is long
> (26 questions + up to 25 remediation entries). Do NOT try to emit it in one
> oversized write that gets summarized or truncated. Build it incrementally and
> in full: write the header + Summary table first, then append Detailed Findings,
> then append each Prioritized Recommendation, then append the 26 matrix rows.
> If you save the report as an artifact, the artifact MUST contain this same fully
> expanded content — re-open/verify it after writing and, if any section shows a
> placeholder label or the matrix has fewer than 26 populated rows, rewrite it with
> the real content before telling the user it is done.

**Load the report layout before writing the scorecard.** Call
`read_skill_resource(skill_id='analytics-dataops-expertise', path='references/report-format.md')`
— MANDATORY — and render the report in exactly that structure. It defines: the Executive
Summary with an overall + per-dimension score-card row and a maturity tier; the scoring
caveat banner; per-dimension RAG summary bands (Strengths ≥3.0 / Watch 2.0–2.9 / Gaps <2.0);
a per-question detail block for all 26 questions (score, `HIGH`/`MEDIUM` confidence badge,
one-line rationale, real observed metrics, optional ⚠️ warning, 💬 discussion-ask prompts);
the prioritized Recommendations; the verbatim Remediation Detail; and the 26-row Score Matrix.

Confidence badge: **HIGH** when every API the question needs returned data; **MEDIUM** when
the question is auto-score-capped or an API was denied/blocked/empty (capped questions are at
most MEDIUM). Observed-metric values MUST be real numbers from the API calls — NEVER paste a
raw dict/list/JSON structure (e.g. `{'postgres': ['unknown', ...]}`); summarize it in words.

### Output artifacts — Markdown always; HTML only on request

There are two report templates under `assets/templates/` — both are STRUCTURE/CSS/JS only
(placeholder `{{tokens}}`) and contain NO example data; never copy sample values out of them:
- `assets/templates/dataops-maturity-report.md` — the in-chat Markdown report. ALWAYS produce
  this. Fill every `{{token}}` from data collected in this run and post it as the chat response.
- `assets/templates/dataops-maturity-report.html` — a downloadable, self-contained styled HTML
  report (executive score-card tiles, per-dimension cards + RAG summary, per-question
  `<details>` blocks with confidence badges / observed-metric tiles / ⚠️/💬 callouts, the
  26-row matrix, and a self-download button). Produce this ONLY if the user asks for a
  downloadable/HTML report.

Rules for the HTML report:
1. Ask (or honor the user's request) whether they want the downloadable HTML in addition to
   the in-chat Markdown. If yes, load the HTML template via
   `read_skill_resource(skill_id='analytics-dataops-expertise', path='assets/templates/dataops-maturity-report.html')`,
   fill every `{{token}}`, and repeat the marked `<!-- REPEAT -->` blocks once per dimension /
   per question / per matrix row. Do not alter the template's structure, CSS, or JS — only
   substitute content.
2. **HTML-escape every substituted value** (`<`→`&lt;`, `>`→`&gt;`, `&`→`&amp;`, `"`→`&quot;`,
   `'`→`&#39;`) — especially observed values, resource names, and any quoted error text, which
   come from the account and are untrusted. (This does NOT apply to the Markdown template.)
3. Save the filled HTML as an artifact named `{account_id}-{region}-dataops-maturity.html`,
   set the template's `{{report_filename}}` to that same name, and tell the user it is in the
   chat's **Artifacts** panel (self-contained, works offline). Never paste raw HTML into the
   chat body — it renders as inert code; the Markdown report is the in-chat output.
4. The HTML and Markdown MUST carry identical data — same scores, same 26 questions, same
   findings. The template is never a source of values; every value comes from this run.

## Error Handling

- If an API returns `AccessDeniedException` → if the question has other signals,
  score from those and note the gap; only mark a question SKIPPED if EVERY API it
  needs is denied (state which permission is missing).
- If an API is not available in the region or returns empty → treat as "resource
  not present" (a score-1 signal), not an error.
- Cost Explorer (`ce.*`) must be enabled and is called in `us-east-1`; if it is
  unavailable, score Q37/Q39 from tagging/other signals and note the CE gap.
- This skill never uses AWS-internal data sources; if a signal cannot be obtained
  from account control-plane APIs, say so — do not fabricate it.
