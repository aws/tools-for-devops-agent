# AWS Sustainability API Reference

Operational notes for the carbon and water operations as used by this skill, plus the
methodology background needed to interpret the numbers correctly.

Official docs:
- [AWS Sustainability API Reference](https://docs.aws.amazon.com/sustainability/latest/APIReference/Welcome.html)
- [AWS Sustainability User Guide](https://docs.aws.amazon.com/sustainability/latest/userguide/what-is-sustainability.html)
- [Calculation methodology](https://docs.aws.amazon.com/sustainability/latest/userguide/methodology.html)
- [Water withdrawals methodology](https://docs.aws.amazon.com/sustainability/latest/userguide/methodology-water.html)

## IAM Permissions

Actions the agent's role may need beyond its managed policy. All are read-only.

| Action | Need | Used for |
|---|---|---|
| `sustainability:GetEstimatedCarbonEmissions` | Required for carbon | Step 5.1. Without it, use a CSV export (`references/csv-emissions-input.md`) |
| `sustainability:GetEstimatedCarbonEmissionsDimensionValues` | Optional | Lists values for `FilterBy`; the review continues without it |
| `sustainability:GetEstimatedWaterAllocation`, `sustainability:GetEstimatedWaterAllocationDimensionValues` | Water | Step 5.2. Without them, ask for a console water export |
| `dlm:GetLifecyclePolicies` | Required for SUS04-BP03 snapshot evidence | Neither managed policy below grants it |
| `ce:GetCostAndUsage` | Required for the Step 6 divergence check | Already granted by `AIDevOpsAgentAccessPolicy` via `ce:Get*`; not by `AIOpsAssistantPolicy` |
| `compute-optimizer:GetEnrollmentStatus`, `compute-optimizer:GetEC2InstanceRecommendations`, `compute-optimizer:GetAutoScalingGroupRecommendations`, `compute-optimizer:GetRDSDatabaseRecommendations` | Optional, Graviton assessment | Migration-effort ratings in `references/graviton-migration.md`; the account must also be opted in |
| `ecr:BatchGetImage` | Optional, Graviton assessment | Confirms that an image index includes arm64 |

```json
{
  "Effect": "Allow",
  "Action": [
    "sustainability:GetEstimatedCarbonEmissions",
    "sustainability:GetEstimatedCarbonEmissionsDimensionValues",
    "sustainability:GetEstimatedWaterAllocation",
    "sustainability:GetEstimatedWaterAllocationDimensionValues",
    "dlm:GetLifecyclePolicies",
    "ce:GetCostAndUsage",
    "compute-optimizer:GetEnrollmentStatus",
    "compute-optimizer:GetEC2InstanceRecommendations",
    "compute-optimizer:GetAutoScalingGroupRecommendations",
    "compute-optimizer:GetRDSDatabaseRecommendations",
    "ecr:BatchGetImage"
  ],
  "Resource": "*"
}
```

The four `sustainability:` actions are the service's only API operations. None supports
resource-level scoping or condition keys — `Resource` must be `*`. Granting an action the role
already has is harmless.

None of the `sustainability:` actions is granted by `AIDevOpsAgentAccessPolicy` or
`AIOpsAssistantPolicy` — neither policy document contains any `sustainability:` action, and all
four return `implicitDeny` when simulated against a live Agent Space role.
`AIOpsAssistantPolicy` enumerates only `ce:Describe*`, `ce:GetAnomalyMonitors`,
`ce:GetAnomalySubscriptions` and `ce:List*`, none of which covers `GetCostAndUsage`. Neither
policy contains any `dlm:` action.

S3 bucket lifecycle needs no grant. Both policies already enumerate `s3:GetLifecycleConfiguration`,
which is the IAM action authorizing the `GetBucketLifecycleConfiguration` API call — the action
name drops the `Bucket` the operation name carries, and `s3:GetBucketLifecycleConfiguration` is
not a valid IAM action at all.

Water and carbon are separately authorized. A role granted only the carbon pair gets
`AccessDeniedException` on water and vice versa, so handle the two failures
independently — one missing permission must not suppress the other's data.

### Only `AccessDeniedException` means a permissions gap

`AccessDeniedException` returned **by the service** is the one failure that indicates a missing
IAM action, and the only one for which recommending a policy change is correct.

If the call fails with anything other than `AccessDeniedException` — another service error
such as `ThrottlingException`, `ValidationException` or `InternalServerException`, or a message
that is not an AWS API error at all — then IAM is not the cause, and telling the customer to add
a permission sends them to audit a policy that already grants the action. Instead:

- Record the failure message **verbatim** in the report's `unavailable:` field. Do not
  paraphrase it into "access denied" and do not infer a cause it does not state.
- Do **not** recommend an IAM change, and do not name a missing action.
- Offer the CSV route (Step 5.0), which needs no `sustainability:` permission at all.

The distinction matters because a skill given only "denied" as failure vocabulary will map any
failure onto the nearest available explanation, and a confident wrong claim about the customer's
IAM is worse than reporting the data as unavailable.

## GetEstimatedCarbonEmissions

### Request

```
TimePeriod:              { Start: <ISO-8601>, End: <ISO-8601> }     # required
Granularity:             MONTHLY | QUARTERLY_CALENDAR | QUARTERLY_FISCAL
                         | YEARLY_CALENDAR | YEARLY_FISCAL
GranularityConfiguration: { FiscalYearStartMonth: <1-12> }          # for *_FISCAL only
GroupBy:                 [ USAGE_ACCOUNT_ID | REGION | SERVICE ]
FilterBy:                { Dimensions: { <dimension>: [<values>] } }
EmissionsTypes:          [ ... see below ... ]
NextToken / MaxResults                                              # paginate
```

### Emissions Types

| Type | Meaning |
|------|---------|
| `TOTAL_LBM_CARBON_EMISSIONS` | Total, location-based method |
| `TOTAL_MBM_CARBON_EMISSIONS` | Total, market-based method |
| `TOTAL_SCOPE_1_CARBON_EMISSIONS` | Direct emissions (on-site fuel combustion, refrigerants) |
| `TOTAL_SCOPE_2_LBM_CARBON_EMISSIONS` | Purchased electricity, at actual grid intensity |
| `TOTAL_SCOPE_2_MBM_CARBON_EMISSIONS` | Purchased electricity, net of AWS renewable energy purchases |
| `TOTAL_SCOPE_3_LBM_CARBON_EMISSIONS` | Value chain (chiefly embodied hardware carbon), LBM |
| `TOTAL_SCOPE_3_MBM_CARBON_EMISSIONS` | Value chain, MBM |

**LBM vs MBM is the single most common source of customer confusion.**

- **LBM (location-based)** uses the actual carbon intensity of the grid serving the data
  center. It moves with the local grid mix — seasonally, and year over year as the grid
  decarbonizes.
- **MBM (market-based)** accounts for AWS's renewable energy contracts. Because AWS
  matches its electricity consumption with renewable energy purchases, Scope 2 MBM is
  typically at or near zero.

Consequences the report must handle:
- LBM and MBM frequently move in **opposite** directions. A customer comparing the wrong
  pair across periods will reach the wrong conclusion.
- A customer whose sustainability reporting uses MBM will see near-zero Scope 2 and may
  conclude their compute has no footprint. Scope 3 (embodied hardware) is where their
  consumption still shows up.
- Always state which method a figure uses. Never mix them in one comparison.

Units are **MTCO2e** (metric tons CO2 equivalent). Resolution is 0.000001 MTCO2e (1 gram).

### Response

Each result carries a `TimePeriod` and a **`ModelVersion`**. Record the model version
every time — see "Methodology changes" below.

### Pagination

AWS explicitly recommends pagination for this operation. Always paginate; on an
organization with many accounts an unpaginated call will be slow or fail.

## Critical Quirks

### 1. Month selection is half-open — `Start` inclusive, `End` exclusive

The docs state:

> "The range must include the start date of a month for that month's data to be included
> in the response."

and the `TimePeriod` shape documents `End` as "the end (exclusive)". Together the precise
rule is:

> Month `M` is returned if and only if `Start <= M-01T00:00:00Z < End`.

Verified against a live account:

| `Start` | `End` | Months returned |
|---|---|---|
| `2026-05-01T00:00:00Z` | `2026-06-01T00:00:00Z` | May only — **June excluded** |
| `2026-05-01T00:00:00Z` | `2026-06-01T00:00:00.001Z` | May **and** June |
| `2026-05-01T00:00:00.001Z` | `2026-07-01T00:00:00Z` | June only — **May dropped** |
| `2025-01-01T00:00:00Z` | `2026-01-01T00:00:00Z` | Jan–Dec 2025, exactly 12 — **not** Jan 2026 |

Both boundaries bite. A `Start` one millisecond past midnight loses that whole month, and an
`End` exactly on a month boundary excludes the month that begins there.

Two safe forms for "all of calendar 2025":

```
Start: 2025-01-01T00:00:00Z, End: 2025-12-31T23:59:59.999Z   # AWS's example form
Start: 2025-01-01T00:00:00Z, End: 2026-01-01T00:00:00Z       # equivalent — Jan 2026 is excluded
```

To include the current month, set `End` past that month's first instant — `now` works, since
it is strictly greater. Always read the `TimePeriod` on each returned result rather than
inferring which months the request covered.

Returned results use the same half-open representation — a January result carries
`Start: 2025-01-01T00:00:00Z, End: 2025-02-01T00:00:00Z`.

### 2. Data publishes one month in arrears

Data for month M is published by the 21st of month M+1 (January data by 21 February). The
current month is always absent, and before the 21st the previous month can be too, so the
latest month available can be two months back. That is the normal one-month lag, not missing
data and not a "two-month lag". Never report an unpublished month as zero — inspect the
`TimePeriod` of the returned results to establish the real availability window, and state that
window in the report.

### 3. Absent ≠ zero

Impact below 0.5 g CO2e (0.0000005 MTCO2e) is not reported. Neither is data for an
account too new to have published data. Both appear as absence. Distinguish:
- "No data available for this period (publication lag)"
- "Impact below the reporting threshold"
- "Zero measured impact"

### 4. Organization scope depends on the calling identity

- **Management account** → consolidated data for all member accounts, for the periods
  those accounts were in the organization. Membership changes therefore shift history.
- **Member account** → its own data only.

Establish the view from evidence: group a call by `USAGE_ACCOUNT_ID` (Step 5.1). More than one
account in the results means a management-account view; report per account. Only the caller's
own account means a member or standalone view. Never assert either without that call. An
account that joined the org mid-year will show a discontinuity that is purely organizational.

### 5. Global service — not regional

The endpoint is global. A region-restriction IAM policy (`aws:RequestedRegion` deny) on the
agent's role must exempt this service, or the calls will fail.

### 6. `GroupBy` supports at most the three listed dimensions

`USAGE_ACCOUNT_ID`, `REGION`, `SERVICE`. There is **no** resource-level or tag-level
grouping. You cannot get per-workload emissions from this API — which is exactly why this
skill derives workload attribution from topology and treats emissions as
account/service/Region-level context.

Only Amazon EC2, Amazon S3 and Amazon CloudFront are broken out by `SERVICE`; every other
service is reported as "Other". Global services such as CloudFront are reported under the
Region "Global".

## GetEstimatedWaterAllocation

**Reporting only.** Water exists so a customer can cite an AWS-sourced figure in their own
disclosure (the definitions align with the
[CDP water accounting note](https://cdn.cdp.net/cdp-production/cms/guidance_docs/pdfs/000/001/561/original/CDP-technical-note-water-accounting-definitions.pdf)
and [GRI 303:2018](https://globalreporting.org/pdf.ashx?id=12488), which is what makes it
usable there). No Pillar best practice is water-specific, water has no KPI, and no
recommendation should be derived from it. Report it accurately and move on.

```
TimePeriod:       { Start: <YYYY>-01-01T00:00:00Z, End: <ISO-8601> }   # required
AllocationTypes:  [ TOTAL_WATER_WITHDRAWALS ]                          # only value; default
Granularity:      YEARLY_CALENDAR                                      # only one supported
GroupBy:          [ USAGE_ACCOUNT_ID | REGION | SERVICE ]              # same as carbon
FilterBy:         { Dimensions: { <dimension>: [<values>] } }
NextToken / MaxResults                                                 # default 1000, max 5000
```

Differences from carbon:

| | Carbon | Water |
|---|---|---|
| Selection unit | Half-open on **month** starts | Half-open on **year** starts |
| Granularity | `MONTHLY` and 4 others work | **Only `YEARLY_CALENDAR`** — anything else is a hard `ValidationException` |
| Value field | `EmissionsValues`, `Unit: MTCO2e` | `AllocationValues`, `Unit: m3` |
| Model version | `v3.0.1` (observed) | Independent line, `v1.0.0` — a *different* number |
| Reporting threshold | 0.5 g CO2e | 0.5 millilitres |
| History depth | Back to January 2022. The console limits how many records it displays; the API and Data Exports return the full history | Back to 2023, published annually: year Y in Q2 of Y+1 (2025 data in Q2 2026); current year absent |

The same half-open rule applies, on years: year `Y` is returned iff
`Start <= Y-01-01T00:00:00Z < End`.

Granularity is the one asymmetry that errors loudly rather than silently — `MONTHLY`,
`QUARTERLY_CALENDAR`, `YEARLY_FISCAL` and `QUARTERLY_FISCAL` all return
`ValidationException: Invalid input: invalid granularity: only YEARLY_CALENDAR can be requested`.
Omitting `Granularity` entirely also works and yields annual results.

The genuine silent trap is the range. The docs say: "If requesting partial time periods, data
will be returned based on the smallest supported granularity. For example, requesting
`2025-04-01T00:00:00Z` to `2026-04-01T00:00:00Z` with `YEARLY_CALENDAR` will return all the
data for 2026 only." **Live, that request returns zero results** — the range contains
`2026-01-01` but 2026 has no published water data yet, and 2025 is excluded because the range
does not contain `2025-01-01`. Either way the lesson holds and is stronger than the docs
suggest: a range that looks like 12 months can return the wrong year *or nothing at all*.
Always send a January 1st `Start` and read the `TimePeriod` on every result.

### Two things to state whenever you report the figure

> "The methodology allocates total water withdrawal from AWS data center operations to
> individual customer accounts based on their proportional cloud service usage. Total water
> withdrawal is defined as the total volume of water taken from any source ... regardless of
> whether it is eventually returned to the environment."

1. **Withdrawal, not consumption.** Water returned to the environment still counts. Calling
   it water "used up" or "consumed" is a different metric and overstates impact.
2. **Data center operations only.** Water embodied in upstream electricity generation is
   excluded, and for most grids that is the larger share. Without this caveat the customer
   reads the number as a total water footprint.

Same top-down allocation as carbon, so the same non-attributability caveats apply in full.

## Methodology Background

### Top-down allocation

CCFT does not meter each customer's energy consumption. AWS computes total infrastructure
emissions, then allocates a share to each customer based on proportional usage, flowing
through cluster → rack → service → account.

Two consequences that customers find counter-intuitive, and that the skill must be able
to explain:

1. **Your allocated share can change because other customers' usage changed**, with no
   change on your side.
2. **AWS-side improvements reduce your reported emissions with no action from you** —
   hardware refresh, PUE improvements, additional renewable procurement.

Both mean reported emissions are not a clean feedback signal for your architecture work.

### Methodology changes

The model version is revisioned (`v3.0.1` observed live for carbon; the user guide documents
the `v3.0.x` line). A revision can move reported figures substantially with **zero** change in
usage. Report the version the API actually returns — never a version quoted from documentation.

**The API always restates history under the current model.** Per the
[`EstimatedCarbonEmissions`](https://docs.aws.amazon.com/sustainability/latest/APIReference/API_EstimatedCarbonEmissions.html)
docs:

> "The AWS Sustainability service reflects the most recent model version for every month.
> You will not see two entries for the same month with different `ModelVersion` values."

Two consequences, and they are the opposite of what you might expect:

1. **You cannot detect a methodology change from this API.** Every month in a single
   response carries the same `ModelVersion`, so a cross-period comparison of `ModelVersion`
   will never differ. Do not build a check on it. There is no in-API signal that a revision
   occurred.
2. **Figures you reported previously may no longer match what the API returns today.** If a
   revision landed since a customer published a number, re-querying the same month returns a
   different value. This is the real methodology risk — not invalid internal comparison, but
   *external* figures going stale.

Rules for the skill:

- **Within one response, period-over-period comparison is methodologically consistent** —
  all months share one model version. Comparison is valid on that axis.
- **Always record and report the `ModelVersion`** so the report is reproducible and a reader
  can tell whether it matches a previously published figure.
- **When a customer says a number changed and they didn't act**, a silent restatement under a
  new model version is a live candidate cause — check the version against whatever they
  published before.
- To see the same month under different model versions, you need
  [Data Exports](https://docs.aws.amazon.com/cur/latest/userguide/what-is-data-exports.html),
  which partitions carbon exports by `model_version`. Earlier versions remain available only in
  an export that existed before the revision, so AWS recommends creating one in advance to
  track methodology changes. The API cannot do it. Water is not available in Data Exports.

**This applies to water identically.** Per the methodology overview: "When AWS releases a new
version of the methodology, historical data is recalculated using the updated version to
ensure accurate comparisons over time." Water carries its own version line, so a water
revision and a carbon revision are independent events — one can move while the other does not.

### Shared responsibility

Sustainability follows a shared responsibility split:

- **AWS is responsible for sustainability OF the cloud** — data center efficiency, PUE,
  renewable energy procurement, hardware efficiency and lifecycle. In short, the *efficiency
  of the infrastructure*: the emissions per unit of usage.
- **The customer is responsible for sustainability IN the cloud** — what they provision,
  how well utilized it is, Region choice, storage tiering, data movement, architecture. In
  short, *how much of that infrastructure they consume*.

AWS publishes no split of the reported figure between the two sides, and this skill must not
assert one. The Pillar states only that the amount "varies per workload and depends on several
factors" — services used, energy consumed, grid carbon intensity, and AWS renewable
procurement. Any specific percentage is unsourced; do not quote one.

Both sides genuinely move the number. Emissions are allocated by proportional usage, so what
the customer provisions determines how much AWS infrastructure is attributed to them —
embodied hardware carbon (often the largest scope) scales almost directly with provisioned
capacity. Region choice is a customer decision that acts on grid intensity, and is an explicit
best practice (SUS01-BP01).

The reason the skill leads with resource intensity KPIs is therefore **not** that the
customer's share is small. It is that the KPIs are unconfounded: they isolate the customer's
decisions from the methodology revisions, grid variation, and allocation-share shifts that
move the emissions figure on their own.

Ref: [Shared responsibility model](https://docs.aws.amazon.com/wellarchitected/latest/sustainability-pillar/the-shared-responsibility-model.html)

## Explaining an Emissions Increase

Work through the ordered causes in `references/framing-and-attribution.md` (Step 8) before
treating any change in reported emissions as a regression or an improvement.

## Alternative Data Path — Data Exports

The AWS Sustainability console also supports an ongoing carbon export to S3 through Data
Exports (CSV or Parquet, partitioned by `model_version` and `usage_period`), queryable with
Athena. This is a Data Exports feature, not a Sustainability API operation — it is provisioned
through `bcm-data-exports` and read from S3, so it needs a different permission set entirely
(`bcm-data-exports:*`, plus S3 and Athena) rather than any `sustainability:` action. It carries
carbon only; water is not available in Data Exports.

| | API (this skill) | Data Export |
|---|---|---|
| Setup | None beyond IAM | Customer must configure the export |
| Latency | Same monthly cadence | Same monthly cadence |
| Granularity | Service × Region × account × month | Same, plus full history in one place |
| History | Back to January 2022 | Back to January 2022, delivered within 24 hours of setup |
| Fit for an agent | Direct API call | Requires Athena access and a configured export |

This skill uses the API because it needs no customer-side setup. If a customer already
has the export configured and wants long-history trend analysis, the export is the better
substrate — but that's an analytics workflow, not an agent workflow. A carbon export file
delivered as CSV can be attached to the review instead of granting API access; read it with
`references/csv-emissions-input.md`.
