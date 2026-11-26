# Changelog

## 1.0.0

First release in [aws/tools-for-devops-agent](https://github.com/aws/tools-for-devops-agent).
The repository requires a new skill to start at 1.0.0, so numbering restarts here. The skill
was developed in aws-samples/sample-code-for-devops-agent-skills, where it reached 1.1.0; that
history is kept below.

- Workload review against all 29 Well-Architected Sustainability best practices, with resource
  intensity KPIs as the assessment and carbon emissions from the AWS Sustainability API as context
- AI/ML coverage for Amazon SageMaker AI and Amazon Bedrock (`references/ai-ml-workloads.md`)
- Graviton migration assessment for SUS05-BP02 (`references/graviton-migration.md`)
- `metadata.aws-devops-agent-skills.agent-types` set to the API values `CHAT, PREVENTION`
  (the Chat tasks and Improvement agents), replacing the console labels the repository's
  publishing check rejects
- SKILL.md cut from 54,563 to about 10,400 characters (793 to 169 lines). In test runs the
  agent loaded only part of the old file, so rules that lived only in SKILL.md were missed — notably the emissions-versus-topology
  sanity check, the 29-practice scorecard and the report artifact. SKILL.md now holds a
  "Critical — read first" block, a nine-step checklist, and a load point per step. Content
  moved verbatim into `references/workload-model.md`, `references/framing-and-attribution.md`,
  `references/emissions-collection.md`, `references/csv-emissions-input.md`,
  `assets/report-template.md`, and a new Step 6 section in `references/proxy-metrics.md`.
  The Step 4 formulas, the Step 7 severity table and the API quirks that duplicated
  `proxy-metrics.md`, the checklist and `emissions-api-reference.md` were removed rather than
  moved. Every load point now has a failure rule: say so at the top of the report and mark the
  dependent practices NEEDS HUMAN INPUT
- `emissions-api-reference.md`: the older change-explanation table, which contradicted the
  current Step 8 ladder, now points to `framing-and-attribution.md`
- The CSV export route is a supported fallback, no longer a test-only path. It accepts a
  carbon or water export from the AWS Sustainability console, or a Data Exports carbon export,
  and is the fallback for water when the water call fails or returns nothing
- Accuracy fixes from the AWS documentation:
  - carbon history goes back to January 2022, not 2023; water back to 2023, published annually
  - monthly data for month M is published by the 21st of month M+1; the skill no longer reads
    the normal one-month lag as a two-month lag or as missing data
  - `GetEstimatedCarbonEmissionsDimensionValues` is optional: it only lists filter values, and
    `GroupBy` results carry the values present
  - a second carbon call grouped by `USAGE_ACCOUNT_ID` is now made by default; more than one
    account in the result means a management (consolidated) view with a per-account breakdown
  - only Amazon EC2, Amazon S3 and Amazon CloudFront are broken out by service; the rest is "Other"
  - the Data Exports partition column is `model_version`
  - IAM actions are listed directly in `emissions-api-reference.md`
- Emissions sanity check made relative: zero emissions against a sizeable fleet, and emissions
  shares by account or Region that don't match the provisioned footprint. The absolute
  grams-per-vCPU-hour band, which no AWS source publishes, is removed
- Two rules added to "Critical — read first": the report artifact is the deliverable even when
  the user asks specific questions, and Steps 7–9 stay in the main conversation when data
  collection is delegated. In a test run that delegated everything, the agent answered in chat
  without the template, the scorecard or the artifact
- After the first functional evaluation: the severity scale and the water reporting caveats
  (m3, annual, withdrawn not consumed, data-center operations only) added to SKILL.md; the
  description gains a trigger for emissions by linked account, service or Region; five eval
  prompts that read as general questions reworded as review requests
- After the second evaluation: reference and asset paths in SKILL.md are markdown links; Step 9
  ends with a self-check before the report is presented; water is disclosure only, with no
  finding, KPI, trend driver, recommendation or customer attribution derived from it, and
  water embodied in upstream electricity is excluded; a non-`AccessDeniedException` failure
  names no permission, not even as a conditional
- `csv-emissions-input.md` states the water caveats (m3, annual, withdrawn not consumed, AWS
  data-center operations only) for exports too; in testing, CSV-sourced water figures were
  reported without them
- Frontmatter: `metadata.summary` added; `aws-services` limited to approved values plus
  `AWS Sustainability`
- README rewritten for aws/tools-for-devops-agent: non-production disclaimer, inline IAM
  policy, import-from-repository and zip-upload instructions
- Evals: `evals.json` in the repository's format with 21 positive and 6 negative cases, adding
  the emissions sanity check, methodology restatement, water CSV fallback, account and service
  breakdown, and reference-load failure. Files used only by the previous evaluation framework
  were removed

## Development history (aws-samples)

### Unreleased

- Rebuilt the SUS05-BP02 Graviton assessment. New `references/graviton-migration.md`, read
  before assessing x86 compute or managed instance classes, replaces the blanket "x86 where
  Graviton is supported" test with:
  - a per-service eligibility check — RDS, Aurora, DocumentDB and Neptune via
    `DescribeOrderableDBInstanceOptions`; ElastiCache, OpenSearch and MSK engine-version
    minimums; EMR release support; Lambda runtime and layer architectures; ECS
    `runtimePlatform`; EKS `amiType`; and whether an ECR image index actually includes arm64
  - optional AWS Compute Optimizer `migrationEffort` ratings for EC2, Auto Scaling groups and
    RDS, requested with `cpuVendorArchitectures: AWS_ARM64`, with fallbacks for opt-in, access
    denied and unrated resources
  - effort bands that set severity: quick win (MEDIUM), build change and assessment needed
    (LOW), engine upgrade first (LOW), and no Graviton option (N/A — Windows, SQL Server,
    Oracle, Db2), with MET / PARTIAL / NOT MET rules
  - a migration order for Prioritised Actions: managed services, Lambda `.zip` functions,
    containers, then self-managed EC2
- Graviton claim rules. AWS's energy statement is quoted only as AWS's. The skill never
  estimates a CO2e or percentage emissions saving, never applies "up to 60%" to a fleet, and
  never predicts a change in the reported figure: under methodology 3.0 the EC2 emissions of a
  cluster are pooled across rack types and split by normalized instance-hours (Eq 38, 40–41).
  Impact is reported as vCPU-hours/month moved to Graviton, plus any vCPU-hours removed by a
  smaller target type. Added to the Core Framing Rule's "Never say" table
- Step 6: the "modern hardware ratio" is split into Graviton share, Graviton-eligible x86
  share, and current-generation share, so current-generation x86 and previous-generation
  Graviton no longer read as the same thing. Step 4.1 records each resource's architecture
- IAM: five optional Read actions for the Graviton assessment
  (`compute-optimizer:GetEnrollmentStatus`, `GetEC2InstanceRecommendations`,
  `GetAutoScalingGroupRecommendations`, `GetRDSDatabaseRecommendations`, and
  `ecr:BatchGetImage`), absent from both managed policies but inside the agent's permission
  guardrail. Added to the README and the CloudFormation template
- Frontmatter: Graviton activation trigger; dropped the redundant "how much water does our
  workload use" example to stay within the 1024-character limit
- New eval `sustainability-review-graviton-claims`

- Added AI/ML workload coverage. New `references/ai-ml-workloads.md`, loaded only when Step 3
  detects the ML / accelerated shape or Amazon Bedrock usage. It adds SageMaker and Bedrock
  inputs, accelerator and token KPIs, and maps the 16 Machine Learning Lens (MLSUS) and 4
  Generative AI Lens (GENSUS) sustainability practices to the SUS best practices they grade
  under. The scorecard stays at 29; lens IDs are cited as evidence
- AI/ML guards: no CO2 per token, inference, or training run; no lens "up to" percentages as
  impact estimates; SageMaker `GPUUtilization` and `CPUUtilization` normalized by device count;
  accelerator-hours reported per family; Bedrock and SageMaker emissions stated as part of
  "Other"
- SKILL.md: AI/ML activation in the description, an AI / ML topology layer, the Step 3 trigger,
  Step 4.5, AI KPIs in Steps 6 and 9, lens grading in Step 7, data sources, and a SageMaker
  metrics quirk
- Step 5.1 now points to `references/emissions-api-reference.md`, which shipped in the upload
  but was never referenced, so its IAM, request-parameter, and Data Exports guidance was
  unreachable. The `AccessDeniedException` row no longer points to the README, which is not
  part of the upload, and names the required actions instead

- Removed an unsourced claim about the share of a reported footprint that is outside customer
  control. Neither the CCFT Methodology nor the Well-Architected Sustainability Pillar states
  any such figure, and the cited shared responsibility model page attaches no number to either
  side of the split. The Pillar says only that the amount "varies per workload"
- Replaced it with the confounder argument: a reported figure is confounded by methodology
  revisions, grid intensity variation, AWS renewable procurement, data center efficiency
  changes, allocation-share shifts caused by other customers' usage, and reporting lag — all of
  which move at the same time as the customer's own changes. The limit is therefore on
  *attribution*, not on the magnitude of customer influence
- Corrected a category error the old framing introduced. Grid intensity was listed as
  uncontrollable while Region choice (SUS01-BP01) is an explicit customer best practice acting
  on it, and embodied hardware carbon was listed as uncontrollable while it scales with
  provisioned capacity. The skill now states plainly that provisioning determines how much AWS
  infrastructure is allocated to an account, and must never tell a customer that rightsizing or
  decommissioning is immaterial to their footprint
- Step 8: reaching step 6 (actual usage change) is now described as a normal outcome and a
  potentially substantial cause rather than a residual; the ladder's order reflects which causes
  are invisible in the figure, not their size
- Replaced eval `sustainability-review-shared-responsibility` with
  `sustainability-review-confounded-emissions`, whose prompt no longer presupposes a proportion,
  plus negative assertions guarding against a percentage claim or dismissing customer action
- Failure handling: only an `AccessDeniedException` returned by the service indicates a missing
  IAM action. Any other failure is recorded verbatim with no IAM recommendation and no named
  missing permission, and the CSV route is offered instead. Added as a row in the "no data"
  table, since that is where the agent acts
- Corrected the IAM prerequisites again, after inspecting both managed policy documents rather
  than relying on `simulate-principal-policy`. The 1.1.0 entry below claimed seven required
  actions; it is six, and one of the seven was not a real IAM action:
  - `s3:GetBucketLifecycleConfiguration` **is not a valid IAM action.** The IAM action drops the
    `Bucket` the API operation name carries — it is `s3:GetLifecycleConfiguration`, which both
    managed policies already enumerate. The CloudFormation statement granting the `GetBucket*`
    spelling was therefore inert: syntactically accepted, matching no request, and granting
    nothing. Statement removed, since nothing needs granting
  - `ce:GetCostAndUsage` is conditional, not universally missing. `AIDevOpsAgentAccessPolicy`
    covers it via `ce:Get*`; `AIOpsAssistantPolicy` enumerates only `ce:Describe*`,
    `ce:GetAnomalyMonitors`, `ce:GetAnomalySubscriptions` and `ce:List*`, and does not. The
    README now shows per-policy coverage rather than a single verdict
  - `dlm:GetLifecyclePolicies` (plural — the list operation) is confirmed real and confirmed
    absent from both policies. Still granted
  - Root cause of the original error: `simulate-custom-policy` and `simulate-principal-policy`
    return `allowed` for an action name that does not exist whenever a matching wildcard is in
    scope, so a simulator `allowed` cannot validate spelling. Both the README and the template
    now say to cross-check the Service Authorization Reference instead
- New month-length rule for every month-over-month comparison, from the API as well as a CSV.
  Monthly emissions are a total over the month rather than a rate, so a 28-day month carries
  roughly 10% less than a 31-day one at identical usage — February reads as an improvement and
  the next 31-day month as a regression. Comparisons must be made per-day, and a delta smaller
  than the two months' day-count difference is explicitly not a finding. The report's carbon
  table gains a `Days` column

### Unreleased — CSV export input

Added a user-provided CSV export path as an alternative source to the Sustainability API.

- New Step 5.0: reads an attached carbon/water CSV export as an alternative source to the API,
  with a column map, four validation checks (scope identity, model version, account scope,
  period completeness), an annual-vs-monthly granularity rule, and a partial-period rule
  forbidding year-over-year deltas against an incomplete period
- Monthly-CSV handling: `usage_month` recognised as monthly, roll-up to a year permitted only
  when all twelve months are present, and like-for-like same-calendar-months comparison
  preferred over any partial-vs-complete year total. Report section 3a gains a hotspot ranking
  for the latest complete month, a whole-window scope split, and an explicit callout of any
  month where LBM and MBM moved in opposite directions
- Step 5 now resolves its data route before calling the API, and prefers an attached CSV over the
  API when both cover the same metric: preferring the API would discard an attachment the user
  deliberately supplied. The API is still called for any metric the CSV does not cover
- Step 6: emissions-vs-topology magnitude sanity check (g CO2e per vCPU-hour) with instructions
  to report a scope mismatch as a finding rather than reconciling the two inputs
- Step 8: new step 0 — verify the comparison is valid before explaining a change
- Report header gains an `Impact source:` line, including an illustrative-data label for
  sample exports; Step 9 section 3 gains annual/coverage handling
- Frontmatter description gains a CSV-attachment activation trigger

### 1.1.0

- Added estimated water withdrawals via `sustainability:GetEstimatedWaterAllocation` (Step 5.2) — annual `TOTAL_WATER_WITHDRAWALS` in cubic metres, grouped by service and Region, with its own report sub-section
- Documented the four ways the water operation differs from carbon: year-based (not month-based) range selection, `YEARLY_CALENDAR`-only granularity, `m3` units in `AllocationValues`, and an independent `ModelVersion` line
- Water reported as withdrawal (not consumption) and scoped to AWS data center operations, excluding water embodied in upstream electricity generation
- Carbon and water treated as separately authorized IAM actions — one returning `AccessDenied` no longer suppresses the other
- Corrected `TimePeriod` semantics against live API behaviour: selection is **half-open** — month `M` is returned iff `Start <= M-01T00:00:00Z < End`. Both boundaries bite, so an `End` landing exactly on a month's first instant excludes that month. The earlier "month-start containment applies to both ends" wording was wrong
- Corrected the water partial-range note: the AWS docs' own example (`2025-04-01` → `2026-04-01`) returns **zero** results live, not "2026 only"
- Water granularity errors loudly rather than silently — non-`YEARLY_CALENDAR` values return `ValidationException`
- Model versions now quoted as observed from the API (`v3.0.1` carbon, `v1.0.0` water) with instruction to report the returned version rather than a documented one
- Corrected `ModelVersion` guidance — the API restates all history under the current version, so a cross-period version-drift check can never fire; compare against the customer's previously published figure instead
- Removed a reference to `GetCarbonFootprintSummary`, which is not an operation of this service
- Corrected the IAM prerequisites after simulating them against a live Agent Space role: `ce:GetCostAndUsage`, `s3:GetBucketLifecycleConfiguration` and `dlm:GetLifecyclePolicies` are **not** granted by `AIDevOpsAgentAccessPolicy` or `AIOpsAssistantPolicy`, contrary to the previous README claim that they were typically already covered. All three are now provisioned by the CloudFormation template alongside the four sustainability actions (seven in total). *(Superseded — see the Unreleased entry above: it is six actions, `s3:GetBucketLifecycleConfiguration` is not a valid IAM action, and `ce:GetCostAndUsage` depends on which managed policy the role carries.)*
- Step 6.1 now names `ce:GetCostAndUsage` as its data source and degrades explicitly on `AccessDeniedException` instead of failing silently
- `ce:*` added to the `AllowedRegions` carve-out — Cost Explorer is reachable only via `us-east-1`, so a region deny omitting it would break the divergence check
- The report header's `unavailable:` fields now require the verbatim error rather than a free-text reason
- Corrected the agent type names to the labels the Operator Web App actually presents: **Chat tasks** and **Improvement**. The previous "Evaluation" and "Prevention" labels no longer exist in the UI — `Improvement` is the current label for the `PREVENTION` API enum. Agent types are now recorded with their API enum alongside the UI label, since the enums are stable and the labels drift

### 1.0.0

- Initial version
- Full Well-Architected Sustainability Pillar assessment across SUS01–SUS06 (29 best practices) with per-practice evidence sources and severity rules
- Real carbon emissions data via `sustainability:GetEstimatedCarbonEmissions` — 14-month window, Scope 1/2/3, LBM and MBM, grouped by service and Region
- Topology-derived resource intensity KPIs: provisioned vs utilized vCPU-hours, weighted GB-months by storage class, weighted GB transferred by network distance, all normalized against business output
- Workload shape detection (request-response, batch, streaming, storage-heavy, ML/accelerated, mixed) driving KPI selection
- Cost-vs-carbon divergence check covering five known patterns cost tooling cannot see
- Ordered causal ladder for explaining emissions changes before attributing them to architecture
- Graceful degradation — the review completes and produces a full report when the emissions API is unavailable
