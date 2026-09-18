# Amazon SageMaker AI — Check Definitions

**8 pillars, 20 checks.** The Best Practices pillar's recommendations are grounded in public
AWS Well-Architected lenses (see the Best Practices section); all other checks are read-only
`List*`/`Describe*` inventories.

**Serverless endpoints: never flag a feature serverless does not support.** Per the AWS
[Serverless Inference feature exclusions](https://docs.aws.amazon.com/sagemaker/latest/dg/serverless-endpoints.html#serverless-endpoints-how-it-works-exclusions),
serverless endpoints do **not** support: GPUs, AWS Marketplace model packages, private Docker
registries, Multi-Model Endpoints, **VPC configuration**, **network isolation**, **data capture**,
multiple production variants, Model Monitor, and inference pipelines. A variant with
`ServerlessConfig` must be scored **Informational** — with a note that the feature is not
supported for serverless — in any check evaluating one of these, never Low/Medium/High. Flagging
them produces a recommendation the user cannot act on: observed a run instructing the operator to
"re-create the model with a VpcConfig block" for a serverless endpoint, and flagging the same
endpoint for disabled data capture. An unactionable finding is worse than no finding. Autoscaling
is the one nuance: on-demand serverless scales automatically, and serverless with Provisioned
Concurrency supports Application Auto Scaling on `sagemaker:variant:DesiredProvisionedConcurrency`
— but never on `DesiredInstanceCount`.

**Never state a number the APIs did not return.** Report quotas, limits, instance prices, monthly
costs, and percentage savings **only** when a call in this file returned that value. If a figure was
not read from an API response, omit it — do not estimate, do not recall it from training data, and do
not carry over a "typical" or "default" value. This applies to Guidance, AI Insights, and
Recommendations equally, and it applies even when the number is qualified with "~" or "up to".
Observed fabrications to avoid: a Service Quotas run that substituted AWS default limits for applied
ones and raised a false High; a Project Check claiming "the domain has a limit of 2 projects by
default" (no such quota exists in the `sagemaker` service); per-hour instance prices and derived
monthly idle-cost totals that no pricing API was called to obtain; and blanket "up to 64% savings" /
"10× lower cost" claims with no source. Where a number would help but is unavailable, name the
console page or API the reader can check instead — an unsourced figure that looks authoritative is
worse than no figure, because it gets acted on.

**What counts as one finding.** A finding is **one non-compliant resource within one check**,
keyed by `(check, region, resource)` — not one row per check. Three unencrypted notebooks are
**three** Medium findings with three recommendations, not one finding reading "3 notebooks are
unencrypted". Never aggregate resources into a single finding or a single recommendation: the
severity counts, the Executive Summary ranking, and the one-recommendation-per-High/Medium rule all
depend on per-resource granularity, and aggregation makes run-to-run counts incomparable. Observed
drifting between runs on an identical account (12 Medium findings vs 5) before this was specified.

**Severity model.** Findings that carry a best-practice signal are ranked on a uniform scale.
Checks with no pass/fail signal stay **Informational** (they inventory state). Each check below
states which severity a non-compliant finding earns; the Service Quotas Check derives its tier
from utilization. **Every High or Medium finding carries exactly one recommendation** in the
report; Low and Informational findings do not require one.

| Severity | Meaning | Examples |
|---|---|---|
| **High** | Material risk to security, availability, or spend — act promptly | Studio domain not `VpcOnly`; quota utilization ≥ 90% |
| **Medium** | Best-practice gap that should be remediated | No autoscaling; stale endpoint; unencrypted notebook; no VPC config; no Savings Plan on steady spend; quota 75–90% |
| **Low** | Minor hygiene gap | Missing tags; data capture disabled |
| **Informational** | Inventory / state, no pass/fail | Inference type, latency, lifecycle configs, projects, pipelines, endpoint instances, domain regions, accelerator adoption, recommender jobs, health events |

**IAM note.** All APIs except one are covered by the AWS-managed **`AIDevOpsAgentAccessPolicy`**
already attached to the DevOps Agent role: `sagemaker` List/Describe/ListTags, `cloudwatch`
GetMetricData/GetMetricStatistics/ListMetrics, `servicequotas:Get*`,
`application-autoscaling:Describe*`, `ce:GetCostAndUsage`/`GetDimensionValues`, and
`health:DescribeEvents`/`DescribeAffectedEntities`. The one exception —
`savingsplans:DescribeSavingsPlans` (Savings Plan check) — is an **optional add-on** not in the
managed policy. When a check's permission is absent, report it as **"not evaluated — permission
not granted"** and continue; never emit a false "none found" on an AccessDenied.

Each check emits rows keyed by `Region`, `AccountId`, `Check`, plus the fields listed below.
Empty results produce a single "no resources found" row rather than being dropped.

---

## Security

### Check Encryption
- **APIs**: `sagemaker.list-notebook-instances` → `describe-notebook-instance`
- **Scope**: notebook instances only (training jobs / endpoint configs deliberately excluded to avoid OOM)
- **Logic**: `encrypted = Boolean(KmsKeyId)`
- **Severity**: notebook without a KMS key → **Medium**; encrypted → Informational (OK). Recommendation on Medium: attach a customer-managed KMS key.
- **Fields**: `type` (NotebookInstance), `name`, `encrypted` (bool), `severity`, `kmsKeyId` (or "Not encrypted")

### SageMaker VPC Check
- **APIs**: `sagemaker.list-domains` → `describe-domain`
- **Pagination**: **list all domains** (no resource cap) — paginate on `NextToken` until exhausted.
- **Logic**: reports network posture; evaluates isolation
- **Severity**: `appNetworkAccessType != VpcOnly` (i.e. `PublicInternetOnly`) → **High**; `VpcOnly` → Informational (OK). Recommendation on High: switch the domain to `VpcOnly` and route through VPC endpoints.
- **Fields**: `domainId`, `domainName`, `domainArn`, `status`, `appNetworkAccessType` (VpcOnly vs PublicInternetOnly), `severity`, `vpcId`, `subnetIds`, `securityGroupIds`; `summary.totalDomains`

### VPC Configuration Check
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint` → `describe-endpoint-config` → `describe-model`
- **Logic** (per production + shadow variant): compliant if the variant has `VpcConfig` OR its model has `VpcConfig`; non-compliant if neither. VpcConfig is a property of the model / endpoint config, so evaluate it **regardless of Inference Component usage**: when a variant has no `ModelName` (Inference Component endpoint), resolve the associated model(s) via `sagemaker.list-inference-components` → `describe-inference-component` → `describe-model` and evaluate their `VpcConfig` rather than emitting a "not supported" Warning. Compliant endpoints emit one "All variants have VPC configuration" row.
- **Serverless variants are out of scope.** Serverless Inference does not support VPC configuration
  or network isolation at all, so a serverless variant can never be compliant and can never be
  remediated. Score it **Informational** with the note "VPC configuration not supported for
  Serverless Inference" and emit no recommendation. Only instance-backed variants are eligible for a
  finding.
- **Severity**: an **instance-backed** variant with neither variant nor model `VpcConfig` → **Medium**; compliant, or serverless → Informational (OK). Recommendation on Medium: attach `VpcConfig` (subnets + security groups) to the model / endpoint config.
- **Fields**: `isCompliant` (true / false), `severity`, `endpointName`, `variantName`, `instanceType`, `status`, `endpointConfigName`, `modelName`, `variantType` (production/shadow), `hasVariantVpcConfig`, `hasModelVpcConfig`, `isInferenceComponent`

---

## Performance

### SageMaker Endpoint Inference Type
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint` → `describe-endpoint-config`
- **Logic**: `serverless` if any variant has `ServerlessConfig`; else `Asynchronous` if `AsyncInferenceConfig`; else `Real-Time`
- **Fields**: `name`, `status`, `inferenceType`

### SageMaker Endpoint Latency
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint` → `describe-endpoint-config`; `cloudwatch.get-metric-statistics`
- **Metrics**: `ModelLatency`, `OverheadLatency` (namespace `AWS/SageMaker`, dims `EndpointName`+`VariantName`, stat `Average`, period 86400, **last 7 days**, one datapoint/day)
- **Logic**: report values (2 dp) or "No data"; no pass/fail
- **Fields**: per endpoint `{endpointName, endpointArn, endpointStatus, region, variants:[{variantName, instanceType, dailyMetrics:[{date, ModelLatency, OverheadLatency}]}]}`; `summary.daysAnalyzed=7`

---

## Cost Optimization

### SageMaker Resource Tagging Check
- **APIs**: `sagemaker.list-models`, `list-endpoints`, `list-training-jobs`, `list-processing-jobs`, `list-transform-jobs`; `sagemaker.list-tags` per resource ARN
- **Exclude SageMaker-generated Model Monitor processing jobs** — those whose name begins
  `model-monitoring-`. They are created automatically by a monitoring schedule, cannot be tagged by
  the operator after the fact, and accumulate without limit: one account held 240+ of them, which
  swamped the check and forced the report to collapse them into a single aggregate row, breaking
  per-resource granularity. Tag the *monitoring schedule* instead. Note the count of excluded jobs in
  the check's summary so the omission is visible.
- **Logic**: `isCompliant = hasUserDefinedTag` — at least one tag whose key does **not** begin with
  a reserved AWS prefix (`sagemaker:`, `aws:`). SageMaker auto-injects `sagemaker:domain-arn`,
  `sagemaker:user-profile-arn`, and `sagemaker:space-arn` on every Studio-created resource, so
  counting any tag at all marks nearly the whole estate compliant and defeats the check. Cost
  Explorer group-by-tag and ownership attribution both require business tags, which is what this
  check is for. Report system tags in `existingTags` for context, but do not let them satisfy
  compliance.
- **Severity**: resource with no user-defined tag → **Low**; has one → Informational (OK). Recommendation is optional at Low (add cost-allocation / ownership tags).
- **Fields**: `resourceType` (Model / Endpoint / TrainingJob / ProcessingJob / BatchTransformJob), `resourceName`, `resourceArn`, `isCompliant` (bool), `severity`, `existingTags` (array), `userDefinedTags` (array — the subset that determined compliance)

### Trainium and Inferentia Usage
- **APIs**: `sagemaker.list-notebook-instances`; `list-training-jobs` → `describe-training-job`; `list-endpoint-configs` → `describe-endpoint-config`; `list-apps`
- **Logic**: instance-type prefix match — `ml.inf*` → Inferentia, `ml.trn*` → Trainium. Only matching resources reported.
- **Fields**: `resourceType` (NotebookInstance / TrainingJob / EndpointConfig / App), `resourceName`, `instanceType`, `acceleratorType`

### Autoscaling Endpoint Check
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint`; `application-autoscaling.describe-scalable-targets` + `describe-scaling-policies` (ServiceNamespace=`sagemaker`) — both in `AIDevOpsAgentAccessPolicy`.
- **Logic (dual-signal, three states — avoids false positives *and* false negatives):** classic
  Application Auto Scaling does not appear on `DescribeEndpoint`, so managed-scaling alone would
  falsely flag it. Evaluate both signals, then resolve to one of three states:

  | Signals present | Mechanism | Verdict |
  |---|---|---|
  | `variant.ManagedInstanceScaling.Status === 'ENABLED'` | `Managed` | autoscaled — Informational |
  | `describe-scalable-targets` returns a target on `sagemaker:variant:DesiredInstanceCount` **and** `describe-scaling-policies` returns ≥ 1 policy for that resource | `Application Auto Scaling` | autoscaled — Informational |
  | target present but **no** scaling policy | `Application Auto Scaling (target only — no policy)` | **not effectively autoscaled** — see Severity |
  | neither signal | `None` | not autoscaled — see Severity |

  A registered scalable target only declares min/max capacity bounds; without a target-tracking,
  step, or scheduled policy nothing ever triggers a scaling action, so the endpoint cannot scale
  despite appearing configured. Both `describe-scalable-targets` and `describe-scaling-policies` are
  covered by `AIDevOpsAgentAccessPolicy`, so the second call is free. If `application-autoscaling` is
  denied, fall back to managed-scaling-only and mark the finding lower-confidence. Endpoint status
  badge: InService=green, Failed=red, else blue.
- **Serverless variants are out of scope.** A variant with `ServerlessConfig` scales to and from
  zero by design and cannot carry an Application Auto Scaling target on
  `sagemaker:variant:DesiredInstanceCount`. Report it as `Mechanism = Serverless`, `Autoscaling
  Enabled = Yes`, severity **Informational** — never Medium. Only instance-backed variants are
  eligible for a finding.
- **Severity**: for an `InService` **instance-backed** variant —
  - autoscaled by **neither** signal → **Medium**. Recommendation: register an Application Auto
    Scaling target on `sagemaker:variant:DesiredInstanceCount` **and attach a scaling policy**, or
    enable managed instance scaling.
  - target registered but **no scaling policy** → **Medium**, worded distinctly: "scalable target
    registered but no scaling policy attached — the endpoint will not scale". Recommendation: attach
    a target-tracking policy (e.g. on `SageMakerVariantInvocationsPerInstance`) to the existing
    target. Do not report this variant as autoscaled.
  - effectively autoscaled (managed scaling, or target + policy), or serverless → Informational (OK).
- **Fields**: `Autoscaling Enabled` (Yes / No / Target only), `severity`, `Mechanism` (Managed / Application Auto Scaling / Application Auto Scaling (target only — no policy) / Serverless / None), `Policy Count`, `Enabled Variants`, `Total Variants`, `Details` (name, ARN, status, timestamps, config name, failure reason)

### Sagemaker Savings Plan
- **APIs**: `savingsplans.describe-savings-plans` (filter savings-plan-type=`SageMaker`, maxResults 100)
- **IAM (optional add-on):** `savingsplans:DescribeSavingsPlans` is **not** in `AIDevOpsAgentAccessPolicy`. If the permission is absent, report this check as **"not evaluated — permission not granted"** and continue — never a false "no Savings Plans found" on an AccessDenied.
- **Scope:** Savings Plans data is meaningful only from the management/payer account; in a linked account it may be empty.
- **Logic**: `remainingDays = round((end − now)/day)`; `status = remainingDays > 0 ? 'Active' : 'Expired'`
- **Severity**: a plan expiring soon (`remainingDays` low) **or** no SageMaker Savings Plan on steady inference spend → **Medium**; healthy active coverage → Informational (OK). Recommendation on Medium: renew/purchase a SageMaker Savings Plan sized to steady spend.
- **Fields**: plan fields + `remainingDays`, `status`, `severity`, `utilizationEstimate`, `region`; `summary`: totalSavingsPlans, sagemakerSavingsPlans, activePlans, expiredPlans, totalCommitment

### Sagemaker Lifecycle Configurations
- **APIs**: `sagemaker.list-notebook-instance-lifecycle-configs` + `sagemaker.list-studio-lifecycle-configs` (concatenated; list only)
- **Logic**: inventory; no pass/fail
- **Fields**: `ConfigName`, `ConfigType`, `ConfigArn`, `CreationTime`, `LastModifiedTime`, `Details`, `RawData.codeString`
- **ConfigType** is `Notebook Instance` for notebook LCCs, or the Studio LCC's `StudioLifecycleConfigAppType` for Studio LCCs — which includes **JupyterServer, KernelGateway, CodeEditor, JupyterLab** (and any future app types). Surface the actual app type per config, not just "Studio".

### Sagemaker Inference Recommender Jobs Check
- **APIs**: `sagemaker.list-inference-recommendations-jobs` → `describe-inference-recommendations-job`
- **Logic**: inventory of recommender jobs; no pass/fail
- **Fields**: described job fields. Empty → "No Recommendation jobs found"

### Sagemaker Stale Endpoints Check
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint`; `cloudwatch.get-metric-data`
- **Metrics**: `Invocations` (namespace `AWS/SageMaker`, dims `EndpointName`+`VariantName`, stat `Sum`, period 86400, **last 90 days**)
- **Logic**: find first non-zero invocation datapoint → `Last Invoked = "<N> days"`; default "Not invoked" if no data
- **Severity**: **instance-backed** endpoint not invoked in ≥ 90 days (or never) → **Medium**
  (idle instance-hours are billed continuously); **serverless** endpoint not invoked → **Low**
  (hygiene only — serverless scales to zero, so there is no idle compute cost to recover).
  Recently invoked → Informational (OK). Recommendation on Medium: delete or right-size the idle
  endpoint. Do not recommend a costly remediation on a stale endpoint — prefer deletion over
  reconfiguring something with no traffic.
- **Fields**: endpoint describe fields + `Last Invoked`, `inferenceType`, `severity`

---

## Service Quotas

### Service Quotas Check
- **APIs**: `servicequotas.get-service-quota` (serviceCode `sagemaker`, per quota code); `cloudwatch.get-metric-data` (usage metrics, period 3600, stat Maximum, **trailing 24 hours**)
- **Do NOT apply `FILL(usage,0)`** or any other gap-filling expression. Filling absent datapoints
  with zero converts "no usage data" into a confident 0% utilization and scores the quota **Low**
  when the correct answer is **Unknown**. Distinguish the two: datapoints returned → compute
  utilization; no datapoints → `Max Usage` = "No data", `Risk Level` = **Unknown**.
- **If the Service Quotas API appears unavailable, retry once before degrading.** Availability of
  `servicequotas` through `use_aws` has been observed to be **intermittent** — the same account
  returned all seven applied limits in one run and "service unavailable" in the next. Retry the
  `get-service-quota` calls once, and if the check runs in a subagent, have the parent retry before
  accepting the degraded result. Only after a retry fails should the check degrade.
- **If the Service Quotas API is genuinely unavailable** (the `use_aws` tool does not expose
  `servicequotas` in the runtime, or the call returns AccessDenied), report the whole check as
  **"not evaluated — Service Quotas API unavailable"** with severity Unknown, and continue. Do not emit quota rows
  with invented limits, and do not report CloudWatch usage without a limit to score it against —
  usage without a denominator is not a utilization finding.
- **Window**: the usage window is fixed at **trailing 24 hours** (`startTime = now − 24 h`, `period 3600`, stat `Maximum`). Keep it fixed for consistent utilization scoring.
  **Do not shorten this window.** SageMaker publishes `AWS/Usage` `ResourceCount` roughly **every
  20 minutes**, not per minute, and with ingestion lag — a trailing-60-minute window at `period 60`
  returns zero datapoints even when resources are plainly running, which scores every quota as
  `Unknown` and silently disables the whole check. Verified 2026-09-18: over 60 min / `period 60`
  the endpoint-instance metric returned 0 datapoints, while the same metric over 24 h /
  `period 3600` returned the correct maximum of 4 against 4 running instances.
- **Quota codes and usage metrics**: all seven codes below were verified against the live
  `sagemaker` service in us-east-1. Usage comes from CloudWatch namespace **`AWS/Usage`**, metric
  **`ResourceCount`**, with dimensions `Service=SageMaker`, `Class=None`, `Type=Resource`, and
  `Resource` set per row. Do **not** use `AWS/SageMaker` for quota usage — no quota usage metrics
  exist in that namespace.

  | Quota code | Quota name | `Resource` dimension |
  |---|---|---|
  | L-00C91CB5 | Number of instances across all training jobs | `training-job/total_instance_count` |
  | L-F311B08F | Number of instances across all processing jobs | `processing-job/total_instance_count` |
  | L-60D2A6F0 | Number of instances across all transform jobs | `transform-job/total_instance_count` |
  | L-7A3DF611 | Number of instances across active endpoints | `endpoint/total_instance_count` |
  | L-04CE2E67 | Total number of notebook instances | `notebook-instance/total_count` |
  | L-B683BCB0 | Total domains | `studio/total_domains` |
  | L-AC46C40F | Maximum number of Studio user profiles allowed per account | `studio/max_user_profiles_per_domain` |

  If `get-service-quota` returns `NoSuchResourceException` for a code in a given region, skip that
  row and continue — quota availability varies by region.
- **Use `get-service-quota` only. Never `get-aws-default-service-quota`.** The former returns this
  account's **applied** limit; the latter returns the AWS default, which is dramatically lower once
  any increase has been approved. Substituting defaults inverts the utilization maths and
  manufactures false High findings. Observed 2026-09-18: a run that fell back to the default API
  reported the endpoint-instance limit as **4** and raised a High "quota at 100%, new deployments
  will fail" finding, when the applied limit was **200** and true utilization was **2% (Low)**.
  Other defaults it reported were equally wrong — training 4 vs 30 applied, notebooks 8 vs 30,
  domains 2 vs 500, user profiles 2 vs 6000.
- **Never score a quota from an unverified limit.** If `get-service-quota` does not return an applied
  value for a code, emit `Current Value` = "Not retrieved" and `Risk Level` = **Unknown**. Do not
  substitute a default, do not guess, and do not raise a High or Medium finding on a limit the check
  did not actually read. A quota finding is only as trustworthy as its denominator.
- **Risk thresholds**: `utilization% = maxUsage / currentValue × 100`; **≥ 90 → High** (red), **≥ 75 → Medium** (warning), else **Low** (success); **Unknown** if no usage data
- **Fields**: `Quota Name`, `Account ID`, `Region`, `Current Value`, `Max Usage`, `Current Usage`, `Max Utilization %`, `Risk Level`, `Usage` (time series vs quota limit)

---

## Resiliency

### SageMaker Endpoint Instances
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint`
- **Logic**: one row per production variant; no pass/fail
- **Fields**: `Endpoint Name`, `Variant Name`, `Current Instance Count` (or '-'), `Desired Instance Count` (or '-'), `Max Concurrency` (serverless, or '-')

### SageMaker Lifecycle Events
- **APIs**: `health.describe-events` (services=`SAGEMAKER`, maxResults 100) → `health.describe-affected-entities` per event
- **IAM:** `health:DescribeEvents` and `health:DescribeAffectedEntities` are covered by `AIDevOpsAgentAccessPolicy`, but the Health API requires a Business/Enterprise Support plan. If the permission or support tier is absent, report this check as **"not evaluated — permission not granted"** and continue.
- **Event status scope**: default to **`open` and `upcoming` only**. Do not pull `closed` events —
  they are historical noise that crowds out actionable rows (a single account accumulated 20+
  closed maintenance events). Include `closed` only when the user explicitly asks for event history.
- **Logic**: inventory of AWS Health events, with a severity derived from actionability.
- **Severity**: an event with `eventScopeCode`/entity status indicating **ACTION_REQUIRED** and a
  status of `open` or `upcoming` → **Medium**; all other events → Informational. Recommendation on
  Medium: state the required action and the event's `startTime` as the deadline.
  Rationale: these events carry hard externally-imposed deadlines (scheduled notebook maintenance,
  platform end-of-support). Leaving them Informational keeps them out of the severity-ranked
  Executive Summary, so the most time-critical items in the whole report go unranked — observed in
  a live run where maintenance windows 36 and 52 hours out were invisible to the summary.
- **Fields**: `eventArn`, `eventTypeCode`, `eventDescription`, `startTime`, `endTime`, `statusCode`, `actionability`, `severity`, `affectedResources`, `EventDetails`, `ImpactedResources`, `Actions` (console links). Empty → Status "OK" row
- **Row granularity**: one row and one finding **per affected entity**, not per event. An event
  returning three affected notebook instances is **three** Medium findings with three
  recommendations, because each instance needs stopping individually. Observed a run emitting one
  finding covering "test-trn1, test-with-encryption, test", which under-counted Medium by two. Do not
  collapse multiple events into an aggregate "(N additional events)" row either.
- **Region scope**: filter events to the **in-scope regions only**. AWS Health returns events across
  all regions regardless of the review scope, so a us-east-1-scoped review will otherwise surface
  us-west-2 resources — observed a run reporting two us-west-2 notebook findings under a header
  reading `Regions: us-east-1`. Either drop out-of-scope events or add their region to the review
  scope and header; never report findings for a region the report claims not to cover. Global
  (non-regional) SageMaker events may be included, labelled `global`.

---

## Operational Excellence

### Sagemaker Project Check
- **APIs**: `sagemaker.list-projects` (key `ProjectSummaryList`) → `describe-project`
- **Logic**: inventory; no pass/fail. Empty → "No project found"
- **No project quota exists.** Do not claim projects consume a per-domain or per-account limit —
  there is no SageMaker Projects quota, and a `CreateFailed` project occupies no capacity. Report
  status and `FailureReason` as returned and stop there.
- **Fields**: described project fields

### Sagemaker Pipeline Check
- **APIs**: `sagemaker.list-pipelines` (key `PipelineSummaries`) → `describe-pipeline`
- **Logic**: inventory; no pass/fail. Empty → "No Pipeline found"
- **Fields**: described pipeline fields

### SageMaker Endpoint Datacapture Enabled Check
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint`
- **Logic**: `Data Capture Enabled = Boolean(DataCaptureConfig.EnableCapture)` (false if config null)
- **Serverless variants are out of scope.** Serverless Inference does not support data capture, so a
  serverless endpoint cannot enable it. Score it **Informational** with the note "data capture not
  supported for Serverless Inference" — never Low.
- **Severity**: **instance-backed** endpoint with data capture disabled → **Low**; enabled, or serverless → Informational (OK). Recommendation is optional at Low (enable data capture to support model-quality monitoring / evaluation).
- **Fields**: endpoint describe fields + `Data Capture Enabled` (bool), `severity`

---

## Sustainability

### Domain Region Check
- **APIs**: `sagemaker.list-domains` → `describe-domain`
- **Logic**: inventory of domains and their regions; no pass/fail. Empty → "No Domains Found"
- **Do not assert a region's carbon intensity or renewable-energy mix.** The skill has no data
  source for this, and unsourced claims have flipped between runs on the same account — one run
  called us-east-1 low-renewable and recommended migrating away, the next called it "strong
  renewable energy coverage". State where domains run and, if the user is pursuing a sustainability
  goal, point them at the AWS [customer carbon footprint tool](https://aws.amazon.com/aws-cost-management/aws-customer-carbon-footprint-tool/)
  and AWS's published regional renewable-energy data rather than ranking regions in the report.
- **Fields**: `domainId`, `domainName`, `region`, `status`

---

## Best Practices

### Well-Architected Recommendations (SageMaker AI)
- **APIs**: none — advisory content grounded in the public AWS Well-Architected lenses below.
- **Logic**: emit a concise set of SageMaker-AI-specific recommendations, scoped to what the other checks observed where possible. Cite the lens each recommendation draws from. Do not fabricate resource findings — this section is guidance, not per-resource data.
- **Sources** (public):
  - Machine Learning Lens — https://docs.aws.amazon.com/wellarchitected/latest/machine-learning-lens/machine-learning-lens.html
  - Generative AI Lens — https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html
  - Agentic AI Lens — https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentic-ai-lens.html
- **Recommendation themes** (SageMaker AI only; tailor to observed resources):
  - **Model lifecycle & MLOps** — version models in the SageMaker Model Registry, automate build/train/deploy with SageMaker Pipelines, and gate promotions with approval status (ML Lens: MLOps).
  - **Endpoint efficiency & scaling** — right-size instances, enable autoscaling, and prefer serverless/async for spiky or latency-tolerant traffic (ML Lens: Performance/Cost).
  - **Inference cost** — use Inferentia/Trainium where supported, adopt SageMaker Savings Plans on steady inference spend, and retire stale endpoints (ML Lens: Cost Optimization).
  - **Security & isolation** — CMK encryption on endpoints/notebooks, `VpcOnly` Studio domains, network-isolated models, least-privilege execution roles (ML Lens: Security).
  - **Generative AI hosting** — for FM/LLM endpoints, monitor `ModelLatency`/token throughput, enable data capture for evaluation, and guard against prompt-injection at the application tier (GenAI Lens).
  - **Agentic workloads** — when SageMaker hosts models behind agents, apply tool-access least privilege, observability on agent/tool calls, and human-in-the-loop for high-impact actions (Agentic AI Lens).
- **Fields**: `recommendation`, `pillar`, `lens`, `rationale`
