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

**Every recommendation must be executable as written.** Before emitting one, check that the API and
parameter you name actually accept the change you are asking for. A recommendation naming a parameter
that does not exist, or an API that cannot apply it, fails the moment the operator tries it — and it
discredits the findings that *are* correct. This class has already produced two defects: instructing a
serverless endpoint to attach a `VpcConfig` (Serverless Inference does not support it), and attaching a
notebook `KmsKeyId` via `UpdateNotebookInstance` (no such parameter; the key is immutable after
creation). When the only remediation is disruptive — re-creating a resource rather than updating it —
say so explicitly instead of implying an in-place change.

**What counts as one finding.** A finding is **one non-compliant resource within one check**,
keyed by `(check, region, resource)` — not one row per check. Three notebooks with no
customer-managed key are **three** Medium findings with three recommendations, not one finding
reading "3 notebooks lack a CMK". Never aggregate resources into a single finding or a single recommendation: the
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
| **Medium** | Best-practice gap that should be remediated | No autoscaling (on the dimension that applies to the variant); an Inference Component endpoint whose host instance fleet is fixed while its components autoscale; stale endpoint ≥ 90 days old *and* idle; notebook with no customer-managed KMS key; no VPC config; Savings Plan expired or ≤ 30 days from expiry; Health event with `actionability = ACTION_REQUIRED`; quota 75–90% |
| **Low** | Minor hygiene gap | Missing tags; data capture disabled; Savings Plan 31–90 days from expiry; Health event with `actionability = ACTION_MAY_BE_REQUIRED` |
| **Informational** | Inventory / state, no pass/fail | Inference type, latency, lifecycle configs, projects, pipelines, endpoint instances, domain regions, accelerator adoption, recommender jobs, `INFORMATIONAL` health events, endpoints younger than the 90-day staleness window, accounts with no Savings Plan |

**IAM note.** All APIs except one are covered by the AWS-managed **`AIDevOpsAgentAccessPolicy`**
already attached to the DevOps Agent role: `sagemaker` List/Describe/ListTags, `cloudwatch`
GetMetricData/GetMetricStatistics/ListMetrics, `servicequotas:Get*`,
`application-autoscaling:Describe*`, `ce:GetCostAndUsage`/`GetDimensionValues`, and
`health:DescribeEvents`/`DescribeAffectedEntities`. The one exception —
`savingsplans:DescribeSavingsPlans` (Savings Plan check) — is an **optional add-on** not in the
managed policy. When a check's permission is absent, report it as **"not evaluated — permission
not granted"** and continue; never emit a false "none found" on an AccessDenied.

**Three of these APIs are global — call them once, in `us-east-1`, never per region.** AWS Health,
Cost Explorer, and Savings Plans have no regional endpoints; each has a single global endpoint homed
in `us-east-1` (`health.us-east-1.amazonaws.com`, `ce.us-east-1.amazonaws.com`,
`savingsplans.amazonaws.com`, which resolves to us-east-1).

| API | Call with | Returns |
|---|---|---|
| `health.describe-events` / `describe-affected-entities` | `--region us-east-1` | events for **all** regions — filter client-side to the in-scope regions (see the Lifecycle Events check's Region scope rule) |
| `ce.get-cost-and-usage` | `--region us-east-1` | account-wide cost data, grouped by REGION |
| `savingsplans.describe-savings-plans` | `--region us-east-1` | all Savings Plans in the account |

Looping these three inside the per-region sweep makes them fail in every region other than
`us-east-1` with an endpoint/connection error. Two of those failures are indistinguishable, at a
glance, from the legitimate degradation paths the checks already document — a Health failure reads as
"no Business/Enterprise Support plan" and a Savings Plans failure reads as "permission not granted" —
so the review reports a plausible-looking wrong reason instead of a bug. Call each once and reuse the
result across every in-scope region; if the review is scoped to regions that do not include
`us-east-1`, still make these three calls against `us-east-1`.

Each check emits rows keyed by `Region`, `AccountId`, `Check`, plus the fields listed below.
Empty results produce a single "no resources found" row rather than being dropped.

---

## Security

### Check Encryption
- **APIs**: `sagemaker.list-notebook-instances` → `describe-notebook-instance`
- **Scope**: notebook instances only (training jobs / endpoint configs deliberately excluded to avoid OOM)
- **Logic**: `hasCustomerManagedKey = Boolean(KmsKeyId)`
- **Never report a notebook instance as "not encrypted."** A notebook instance volume is **always**
  encrypted at rest. Per the AWS docs on
  [notebook-instance encryption at rest](https://docs.aws.amazon.com/sagemaker/latest/dg/encryption-at-rest-nbi.html),
  when no `KmsKeyId` is supplied SageMaker AI encrypts both the OS volume and the ML data volume
  with a **system-managed KMS key**. The absent field means "no customer-managed key", not "no
  encryption". Labelling it `encrypted: false` / "Not encrypted" tells the customer their data sits
  in the clear when it does not — a factually wrong statement in a customer-facing report, and the
  kind of finding that destroys trust in every other row. Report the gap as the absence of a CMK.
- **`KmsKeyId` is immutable — never recommend `UpdateNotebookInstance`.** The remediation for this
  finding is **re-creation**, not an update.
  [`UpdateNotebookInstance`](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_UpdateNotebookInstance.html)
  accepts no `KmsKeyId` parameter — the key is settable only at creation, via
  `CreateNotebookInstance --kms-key-id`. Observed 2026-10-01: a run emitted "Enable a customer-managed
  KMS key via `UpdateNotebookInstance` `KmsKeyId`" six times across the Executive Summary and the
  check's Recommendations block. An operator following that gets a parameter-validation error, and a
  recommendation that cannot be executed is worse than none — it is the same failure class as telling
  a serverless endpoint to attach a `VpcConfig`. **Word the recommendation as a replacement**: create a
  new notebook instance with `--kms-key-id` set, migrate the notebook contents (the ML volume does not
  transfer), then delete the original. Say plainly that this is disruptive, so the operator can weigh
  it rather than discovering the cost mid-change. Do **not** name `UpdateNotebookInstance`, and do not
  imply the key can be attached in place.
- **Severity**: notebook with no customer-managed KMS key → **Medium** (a system-managed key gives
  no key-usage audit trail, no rotation control, no grant/deny policy, and no way to revoke access
  by disabling the key); CMK present → Informational (OK). Recommendation on Medium: re-create the
  notebook instance with a customer-managed `KmsKeyId` so key usage is auditable and revocable —
  phrased per the immutability rule above.
- **Fields**: `type` (NotebookInstance), `name`, `customerManagedKey` (bool), `severity`,
  `kmsKeyId` (the key ARN, or **"AWS managed (system-managed key)"** — never "Not encrypted"),
  `encryptionAtRest` (always `"Enabled"`)

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
- **Units: both metrics are published in MICROSECONDS.** Per the
  [SageMaker AI CloudWatch metrics reference](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html),
  `ModelLatency` and `OverheadLatency` both carry `Units: Microseconds`. Every latency figure in the
  report **must** carry its unit in the column header or the value itself. An unlabelled `152340.00`
  reads as milliseconds to almost every reader — a 152-second model, when the true value is 152 ms.
  That is a three-orders-of-magnitude error in the direction that triggers a false performance
  escalation.
- **Logic**: report values (2 dp) or "No data"; no pass/fail. Report **both** the raw microsecond
  value and a milliseconds conversion (`µs / 1000`, 2 dp) so the number is readable without arithmetic.
  Converting is not "inventing a number" — it is a unit change on a value an API returned.
- **Fields**: per endpoint `{endpointName, endpointArn, endpointStatus, region, variants:[{variantName, instanceType, dailyMetrics:[{date, ModelLatencyMicroseconds, ModelLatencyMs, OverheadLatencyMicroseconds, OverheadLatencyMs}]}]}`; `summary.daysAnalyzed=7`. Column headers in the report table must read e.g. `Model Latency (ms)` / `Model Latency (µs)` — never a bare `ModelLatency`.

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
- **APIs**: `sagemaker.list-endpoints` → `describe-endpoint`; `sagemaker.list-inference-components` → `describe-inference-component` (to map IC targets back to their endpoint); `application-autoscaling.describe-scalable-targets` + `describe-scaling-policies` (ServiceNamespace=`sagemaker`) — all in `AIDevOpsAgentAccessPolicy`.
- **Logic (dual-signal, three states — avoids false positives *and* false negatives):** classic
  Application Auto Scaling does not appear on `DescribeEndpoint`, so managed-scaling alone would
  falsely flag it. Evaluate both signals, then resolve to one of three states:

  | Signals present | Mechanism | Verdict |
  |---|---|---|
  | `variant.ManagedInstanceScaling.Status === 'ENABLED'` | `Managed` | autoscaled — Informational |
  | `describe-scalable-targets` returns a target on **any scalable dimension applicable to the variant** (see the dimension table below) **and** `describe-scaling-policies` returns ≥ 1 policy for that same `ResourceId` + `ScalableDimension` | `Application Auto Scaling` | autoscaled — Informational |
  | target present but **no** scaling policy | `Application Auto Scaling (target only — no policy)` | **not effectively autoscaled** — see Severity |
  | neither signal | `None` | not autoscaled — see Severity |

  A registered scalable target only declares min/max capacity bounds; without a target-tracking,
  step, or scheduled policy nothing ever triggers a scaling action, so the endpoint cannot scale
  despite appearing configured. Both `describe-scalable-targets` and `describe-scaling-policies` are
  covered by `AIDevOpsAgentAccessPolicy`, so the second call is free. If `application-autoscaling` is
  denied, fall back to managed-scaling-only and mark the finding lower-confidence. Endpoint status
  badge: InService=green, Failed=red, else blue.

- **Match all three scalable dimensions — not just `DesiredInstanceCount`.** A single
  `describe-scalable-targets` call with `ServiceNamespace=sagemaker` returns targets on **every**
  SageMaker dimension, and the check must consider all of them. Matching only
  `sagemaker:variant:DesiredInstanceCount` discards the dimension that Inference Component endpoints
  actually scale on, so a correctly autoscaled IC endpoint is reported "not autoscaled" **and** gets
  a remediation naming a dimension that does not apply to it — a false Medium plus wrong advice.

  | Variant / endpoint shape | Scalable dimension | `ResourceId` format |
  |---|---|---|
  | Instance-backed variant | `sagemaker:variant:DesiredInstanceCount` | `endpoint/<EndpointName>/variant/<VariantName>` |
  | Inference Component | `sagemaker:inference-component:DesiredCopyCount` | `inference-component/<InferenceComponentName>` |
  | Serverless with Provisioned Concurrency | `sagemaker:variant:DesiredProvisionedConcurrency` | `endpoint/<EndpointName>/variant/<VariantName>` |

  Note the **`ResourceId` for an Inference Component target does not contain the endpoint name**, so
  it cannot be matched by string comparison against the endpoint. Resolve the association the other
  way: `sagemaker.list-inference-components` (filtered by `EndpointNameEquals`) →
  `describe-inference-component` returns `EndpointName` and `VariantName`. Build the IC-name → endpoint
  mapping first, then attribute each `inference-component/<name>` target to its endpoint. An endpoint
  whose ICs all carry a `DesiredCopyCount` target **with** a policy is autoscaled; report
  `Mechanism = Application Auto Scaling (inference component)` and the IC names in `Details`.
  Set `Scalable Dimension` on every row so the reader can see which mechanism was evaluated.
- **Inference Component endpoints have two layers — evaluate both.** An IC endpoint's **host
  variant** supplies the instances; the **inference components** are model copies placed onto them.
  Scaling `DesiredCopyCount` only grows copies into capacity the host fleet already has, so an IC
  endpoint whose components autoscale but whose host variant is fixed hits a hard ceiling: once the
  instances are full, further copies cannot be placed and the endpoint stops scaling despite being
  configured to. Emit **one row per layer** — the host variant keyed `(endpoint, variant)`, and each
  component keyed `(endpoint, inference-component)` — and score them independently:

  | Components autoscaled? | Host variant has managed instance scaling **or** a variant-level target + policy? | Host variant verdict |
  |---|---|---|
  | Yes | Yes | Informational (OK) — both layers scale |
  | **Yes** | **No** | **Medium** — "inference components autoscale but the host instance fleet is fixed; copy count cannot grow beyond current host capacity". Recommendation: enable **managed instance scaling** on the variant so SageMaker AI adds instances as component copies are placed — this is the mechanism AWS documents for IC endpoints, in preference to a variant-level Application Auto Scaling target |
  | No | No | Informational **for the host row** — the component row already carries the Medium for this endpoint. Do not emit both; see below |
  | No | Yes | Informational (OK) for the host row; the component row carries its own finding |

  **Do not double-count one endpoint.** When the components are not autoscaled, the component row's
  Medium is the finding; the host row stays Informational with the note "host scaling not assessed
  separately — see the inference component finding". Emitting a Medium on both layers for the same
  endpoint inflates the severity counts and breaks run-to-run comparability, which is the same failure
  the per-resource granularity rule exists to prevent. Exactly one Medium per endpoint per layer-pair.
- **Serverless variants are out of scope.** A variant with `ServerlessConfig` scales to and from
  zero by design and cannot carry an Application Auto Scaling target on
  `sagemaker:variant:DesiredInstanceCount`. Report it as `Mechanism = Serverless`, `Autoscaling
  Enabled = Yes`, severity **Informational** — never Medium. Only instance-backed variants and
  Inference Components are eligible for a finding. If the serverless variant has
  `ProvisionedConcurrency` set **and** a target on
  `sagemaker:variant:DesiredProvisionedConcurrency`, report
  `Mechanism = Serverless (provisioned concurrency autoscaling)`; still Informational either way.
- **Severity**: for an `InService` variant that is **instance-backed or an Inference Component** —
  - autoscaled by **neither** signal → **Medium**. Recommendation: register an Application Auto
    Scaling target **and attach a scaling policy** on the dimension that matches the variant's shape
    — `sagemaker:variant:DesiredInstanceCount` for an instance-backed variant,
    `sagemaker:inference-component:DesiredCopyCount` for an Inference Component — or enable managed
    instance scaling. **Name the dimension that applies to the variant you are flagging**; quoting
    `DesiredInstanceCount` at an IC endpoint is advice the operator cannot act on.
  - target registered but **no scaling policy** → **Medium**, worded distinctly: "scalable target
    registered but no scaling policy attached — the endpoint will not scale". Recommendation: attach
    a target-tracking policy to the existing target — on
    `SageMakerVariantInvocationsPerInstance` for an instance-backed variant, or
    `SageMakerInferenceComponentConcurrentRequestsPerCopyHighResolution` for an Inference Component.
    Do not report this variant as autoscaled.
  - effectively autoscaled (managed scaling, or target + policy on any applicable dimension), or
    serverless → Informational (OK).
  - **IC host variant** whose components autoscale but which has no managed instance scaling and no
    variant-level target + policy → **Medium**, worded as the capacity ceiling rather than as
    "not autoscaled". Recommendation: enable managed instance scaling on the variant. See the
    two-layer rule above, including the no-double-counting guard.
- **Fields**: `Autoscaling Enabled` (Yes / No / Target only), `severity`, `Layer` (Host variant / Inference component / Variant), `Mechanism` (Managed / Application Auto Scaling / Application Auto Scaling (inference component) / Application Auto Scaling (target only — no policy) / Serverless / Serverless (provisioned concurrency autoscaling) / None), `Scalable Dimension` (the dimension evaluated, or '-'), `Policy Count`, `Enabled Variants`, `Total Variants`, `Details` (name, ARN, status, timestamps, config name, inference component names, failure reason)
- **`Policy Count` is read, never inferred.** Report the number of policies `describe-scaling-policies`
  actually returned for that exact `ResourceId` + `ScalableDimension`. Observed 2026-10-01: a run
  reported `Policy Count 1` and Informational for an endpoint that had a registered target and **zero**
  policies, which silently swallowed a Medium. A target is not a policy — if the policy list for a
  resource is empty, `Policy Count` is `0` and the verdict is the target-only Medium.

### Sagemaker Savings Plan
- **APIs**: `savingsplans.describe-savings-plans` (filter savings-plan-type=`SageMaker`, maxResults 100) — **global API, call in `us-east-1` only** (see the global-API rule above)
- **IAM (optional add-on):** `savingsplans:DescribeSavingsPlans` is **not** in `AIDevOpsAgentAccessPolicy`. If the permission is absent, report this check as **"not evaluated — permission not granted"** and continue — never a false "no Savings Plans found" on an AccessDenied.
- **Scope:** Savings Plans data is meaningful only from the management/payer account; in a linked account it may be empty.
- **Logic**: `remainingDays = round((end − now)/day)`; `status = remainingDays > 0 ? 'Active' : 'Expired'`
- **Severity thresholds (explicit — do not improvise them):** scored **only** from `remainingDays`,
  which this check actually computes from the API response.
  - `remainingDays <= 0` (expired) → **Medium**. Recommendation: the commitment has lapsed; that usage
    is now billed on-demand — review current SageMaker usage in Cost Explorer and repurchase if it is
    still steady.
  - `0 < remainingDays <= 30` → **Medium**, worded as an expiry deadline with the date.
    Recommendation: the plan expires in `<N>` days; decide on renewal before then.
  - `30 < remainingDays <= 90` → **Low** (advance notice, no action yet).
  - `remainingDays > 90` → Informational (OK).
- **Never recommend purchasing a Savings Plan off an unmeasured premise.** "No plan on steady
  inference spend" was previously a Medium, but this check measures **no spend at all** — it reads
  plans, not usage, and neither `ce:GetCostAndUsage` for SageMaker spend nor any commitment-coverage
  API is called here. A multi-year financial commitment recommended from an unverified assumption of
  steady spend is the single most expensive thing a wrong finding in this report can cause. So:
  **zero SageMaker Savings Plans found → Informational, not Medium.** State the observation ("no
  SageMaker Savings Plan covers this account") and point the reader at **Cost Explorer → Savings Plans
  recommendations**, which computes the recommendation from their actual usage. Do not name a
  commitment amount, term, or savings percentage — see the no-invented-numbers rule.
- **Fields**: plan fields + `remainingDays`, `expiryDate`, `status`, `severity`, `region`; `summary`: totalSavingsPlans, sagemakerSavingsPlans, activePlans, expiredPlans, totalCommitment. Report `totalCommitment` only as the API returned it; do **not** derive an estimated saving from it.

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
- **Logic**: take the **most recent** non-zero invocation datapoint (the one with the greatest
  timestamp) → `Last Invoked = "<N> days"` where `N = days between that timestamp and now`. If every
  datapoint is zero or none are returned, `Last Invoked = "Not invoked"`.
- **Read the latest non-zero datapoint, never the "first" one.** "First non-zero datapoint" is
  order-dependent and wrong in the common case: `get-metric-data` returns timestamps ascending by
  default, so the first non-zero point is the **oldest** invocation in the window. An endpoint
  invoked every day for 90 days then reports `Last Invoked: 90 days` and is flagged Medium with a
  "delete the idle endpoint" recommendation — on a busy production endpoint. Sort the datapoints by
  timestamp descending (or set `ScanBy=TimestampDescending`) and take the first non-zero from that,
  which is the same thing as the maximum timestamp with a non-zero `Sum`.
- **Align `startTime` to midnight UTC.** With `period 86400`, CloudWatch anchors the daily buckets to
  the request's `startTime`, **not** to calendar days. A start time of `now − 90 days` taken at
  09:29 produces buckets running 09:29→09:29, so invocations from two different calendar days land in
  one bucket stamped with the earlier date — and `Last Invoked` is then reported a day early. Observed
  2026-10-01: an endpoint invoked on both 09-30 and 10-01 returned a single datapoint
  `2026-09-30 = 51` under an unaligned start time, and two datapoints (`09-30 = 31`, `10-01 = 20`)
  under a different one. Set `startTime` to **00:00:00Z** of the day 90 days back so buckets are
  calendar days and the `<N> days` figure is reproducible between runs. Derive `Last Invoked` from the
  **bucket timestamp** of the latest non-zero datapoint, and state that date in the row alongside the
  day count so the reader can see what it was computed from.
- **Guard on `CreationTime` before flagging "Not invoked".** A newly deployed endpoint has no
  invocation history yet, so absent datapoints mean "too new to judge", not "idle". `describe-endpoint`
  already returns `CreationTime`, so the guard costs nothing. If
  `ageDays = (now − CreationTime) / day` is **< 90**, the endpoint cannot satisfy the 90-day staleness
  test: report `Last Invoked = "Not invoked"`, `Age = "<N> days"`, severity **Informational** with the
  note "endpoint is <N> days old — shorter than the 90-day staleness window", and emit **no**
  recommendation. Without this guard a two-day-old endpoint is scored Medium and the report tells the
  operator to delete something they just deployed.
- **Severity**: for an endpoint with `ageDays ≥ 90` —
  - **instance-backed**, not invoked within the 90-day window (or never invoked) → **Medium**
    (idle instance-hours are billed continuously).
  - **serverless**, not invoked → **Low** (hygiene only — serverless scales to zero, so there is no
    idle compute cost to recover).
  - invoked within the window → Informational (OK).

  Any endpoint with `ageDays < 90` → **Informational**, regardless of invocation data.
  Recommendation on Medium: delete or right-size the idle endpoint. Do not recommend a costly
  remediation on a stale endpoint — prefer deletion over reconfiguring something with no traffic.
- **Fields**: endpoint describe fields + `Last Invoked`, `CreationTime`, `Age` (days), `inferenceType`, `severity`

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
- **APIs**: `health.describe-events` (services=`SAGEMAKER`, maxResults 100) → `health.describe-affected-entities` per event — **global API, call in `us-east-1` only** (see the global-API rule above); it returns events for every region, which the Region scope rule below then filters
- **IAM:** `health:DescribeEvents` and `health:DescribeAffectedEntities` are covered by `AIDevOpsAgentAccessPolicy`, but the Health API requires a Business/Enterprise Support plan. If the permission or support tier is absent, report this check as **"not evaluated — permission not granted"** and continue.
- **Event status scope**: default to **`open` and `upcoming` only**. Do not pull `closed` events —
  they are historical noise that crowds out actionable rows (a single account accumulated 20+
  closed maintenance events). Include `closed` only when the user explicitly asks for event history.
- **Logic**: inventory of AWS Health events, with a severity derived from actionability.
- **Read actionability from `Event.actionability` — and from nowhere else.** The
  [`Event`](https://docs.aws.amazon.com/health/latest/APIReference/API_Event.html) object returned by
  `describe-events` carries a dedicated field:

  | Field | Valid values | Use |
  |---|---|---|
  | `actionability` | `ACTION_REQUIRED` \| `ACTION_MAY_BE_REQUIRED` \| `INFORMATIONAL` | **the severity signal** |
  | `statusCode` | `open` \| `closed` \| `upcoming` | event lifecycle state |
  | `eventScopeCode` | `PUBLIC` \| `ACCOUNT_SPECIFIC` \| `NONE` | public vs account-specific |
  | `eventTypeCategory` | `issue` \| `accountNotification` \| `scheduledChange` \| `investigation` | event kind |
  | entity `statusCode` (from `describe-affected-entities`) | `IMPAIRED` \| `UNIMPAIRED` \| `UNKNOWN` \| `PENDING` \| `RESOLVED` | per-resource state |

  Neither `eventScopeCode` nor the entity `statusCode` can ever equal `ACTION_REQUIRED` — testing
  them for it makes the condition unsatisfiable, so **every** event falls through to Informational and
  the most time-critical items in the whole report never reach the severity-ranked Executive Summary.
  That is exactly the failure this check's severity rule exists to prevent. `describe-events` also
  accepts an `actionabilities` filter; using it is optional — if the runtime's botocore does not
  recognise the parameter, drop the filter and classify client-side from the returned field rather
  than failing the check.
- **Severity**: an event with `actionability == ACTION_REQUIRED` and `statusCode` of `open` or
  `upcoming` → **Medium**; `actionability == ACTION_MAY_BE_REQUIRED` with `statusCode` `open` or
  `upcoming` → **Low** (inspection needed to determine whether action is required); everything else,
  including `INFORMATIONAL` and any event with `actionability` absent → Informational. Recommendation
  on Medium: state the required action and the event's `startTime` as the deadline.
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
  - **Inference cost** — use Inferentia/Trainium where supported, evaluate SageMaker Savings Plans against Cost Explorer's usage-derived recommendations rather than an assumed spend level, and retire stale endpoints (ML Lens: Cost Optimization).
  - **Security & isolation** — CMK encryption on endpoints/notebooks, `VpcOnly` Studio domains, network-isolated models, least-privilege execution roles (ML Lens: Security).
  - **Generative AI hosting** — for FM/LLM endpoints, monitor `ModelLatency`/token throughput, enable data capture for evaluation, and guard against prompt-injection at the application tier (GenAI Lens).
  - **Agentic workloads** — when SageMaker hosts models behind agents, apply tool-access least privilege, observability on agent/tool calls, and human-in-the-loop for high-impact actions (Agentic AI Lens).
- **Fields**: `recommendation`, `pillar`, `lens`, `rationale`
