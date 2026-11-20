# Emissions Collection — Calls, Failure Handling, and Comparison Rules

Read this file in full at Step 5, before the first Sustainability API call. Request parameters,
emissions types, IAM permissions and verified API behaviour are in
`references/emissions-api-reference.md`; this file says how the review collects the data and
what to report when it is missing. A carbon or water CSV export is handled in
`references/csv-emissions-input.md`.

### Publication timing

| Metric | Published | Available from |
|--------|-----------|----------------|
| Carbon | Monthly: month M by the 21st of month M+1 (January data by 21 February) | January 2022 |
| Water | Annually: year Y in Q2 of year Y+1 (2025 data in Q2 2026) | 2023 |

Before the 21st, the latest carbon month available can be two months back — on 10 March it can
be January, because February data is published by 21 March. That is still the normal one-month
lag, not missing data. Never describe it as a "two-month lag", as a gap, or as zero emissions;
state the latest month returned and this rule. Likewise, before Q2 the latest water year
available can be two years back.

### 5.1 Carbon emissions

Call the AWS Sustainability API and **paginate** every call — AWS recommends it, and
unpaginated calls on large organizations will be slow or fail. Full request parameters, the
meaning of each emissions type, IAM permissions, verified quirks, and the Data Exports
alternative are in `references/emissions-api-reference.md` — read it before the first call.

```
sustainability.GetEstimatedCarbonEmissions        # call 1 — by service and Region
    TimePeriod:     Start = 14 months ago (1st of month), End = now
    Granularity:    MONTHLY
    GroupBy:        [SERVICE, REGION]
    EmissionsTypes: [TOTAL_LBM_CARBON_EMISSIONS, TOTAL_MBM_CARBON_EMISSIONS,
                     TOTAL_SCOPE_1_CARBON_EMISSIONS,
                     TOTAL_SCOPE_2_LBM_CARBON_EMISSIONS, TOTAL_SCOPE_2_MBM_CARBON_EMISSIONS,
                     TOTAL_SCOPE_3_LBM_CARBON_EMISSIONS, TOTAL_SCOPE_3_MBM_CARBON_EMISSIONS]

sustainability.GetEstimatedCarbonEmissions        # call 2 — by account; always make it
    TimePeriod, Granularity, EmissionsTypes: same as call 1
    GroupBy:        [USAGE_ACCOUNT_ID]            # or [USAGE_ACCOUNT_ID, SERVICE]

sustainability.GetEstimatedCarbonEmissionsDimensionValues   # optional
```

14 months gives you a full year plus one month of year-over-year comparison.

**`GetEstimatedCarbonEmissionsDimensionValues` is optional.** It only lists the values that can
be passed in `FilterBy`, and this review does not filter. If it fails, continue:
`GetEstimatedCarbonEmissions` with `GroupBy` returns the dimension values present in each
result's `DimensionsValues`. Its failure never makes emissions unavailable.

**Linked accounts.** Read the accounts in the call 2 results:

- **More than one account** — the caller is a management account and sees consolidated data for
  its member accounts, for the time each was in the organization. Report a per-account
  breakdown and say that it is a management-account view.
- **Only the caller's own account** — state that the data is a member or standalone view of that
  one account.

Never state that the caller is a management or member account without this evidence.

**Services and Regions.** Only Amazon EC2, Amazon S3 and Amazon CloudFront are broken out by
service; every other service is reported as "Other". Global services such as CloudFront are
reported under the Region "Global". Never attribute an "Other" figure to a named service.

### 5.2 Water withdrawals

```
sustainability.GetEstimatedWaterAllocation
    TimePeriod:      Start = <YYYY>-01-01T00:00:00Z (1st of a YEAR), End = now
                     # 2 calendar years back for a year-over-year comparison
    Granularity:     YEARLY_CALENDAR          # the only supported value
    GroupBy:         [SERVICE, REGION]
    AllocationTypes: [TOTAL_WATER_WITHDRAWALS]   # the only supported value
```

**Water is for reporting only.** It exists so a customer can cite an AWS-sourced figure in
their own disclosure. There is no water-specific best practice in the Pillar, water has no
KPI, and no recommendation should be derived from it. Report it and move on.

**A CSV export is the fallback for water.** If the water call fails or returns no result, ask
the user for a water export from **Reports** in the AWS Sustainability console and read it with
`references/csv-emissions-input.md`. Data Exports does not carry water data.

Four mechanics that will produce wrong data if you assume symmetry with carbon:

| Trap | Rule |
|------|------|
| Selection is **year**-based and half-open | Year `Y` is returned iff `Start <= Y-01-01T00:00:00Z < End`. `Start` must be `<YYYY>-01-01T00:00:00Z`, or that year vanishes. A partial range can return the wrong year **or nothing at all** — read the `TimePeriod` on every result. |
| Annual only | `YEARLY_CALENDAR` is the only accepted value; anything else is a `ValidationException`. No monthly series, so no month-over-month trend and no counterpart to the 30-day KPI window. Do not attempt one. |
| Units are `m3`, not MTCO2e | Never add, average, or combine water and carbon into one figure or score. |
| Withdrawn ≠ consumed; data centers only | Water returned to the environment still counts, and water embodied in upstream electricity generation is **excluded**. State this boundary whenever you report the figure — otherwise the customer reads it as a total water footprint. |

Water carries its own `ModelVersion` (`v1.0.0`-series, independent of carbon's `v3.0.x`) and
uses the same top-down allocation, so the Core Framing Rule (`references/framing-and-attribution.md`) applies unchanged. Water data
is available from calendar 2023. The in-progress year is absent, and so is the previous year
until it is published in Q2.

**Record the `ModelVersion` returned with every result** and state it in the report. Every
period in a response carries the *same* version — the API restates history under the current
methodology — so comparison within one response is methodologically consistent, and a check
for `ModelVersion` differing across periods **cannot** fire. Its value is reproducibility: it
tells a reader whether a figure still matches one the customer published earlier. See Step 8.

### Handle the "no data" cases explicitly

| Symptom | Cause | What to report |
|---------|-------|----------------|
| Carbon call fails for any reason **and** no CSV was attached | See the rows below for the specific cause | Continue the review without emissions data, and tell the user they can supply a carbon export from the Sustainability console (Reports) or Data Exports instead — Step 5.0 accepts it and needs no `sustainability:` action on the agent's role. |
| `AccessDeniedException` on carbon | Missing `sustainability:GetEstimatedCarbonEmissions` | Continue the review without emissions data. Report the SUS assessment and intensity KPIs in full, and state that emissions enrichment requires `sustainability:GetEstimatedCarbonEmissions` on the agent's role (see IAM Permissions in `references/emissions-api-reference.md`), or a CSV export. |
| `GetEstimatedCarbonEmissionsDimensionValues` fails | Optional call | Continue. Do not report emissions as unavailable and do not recommend an IAM change for it. |
| Carbon or water call fails with anything **other than** `AccessDeniedException` | Not a permissions gap | **Do not recommend an IAM change and do not name a missing permission.** Record the message verbatim in the `unavailable:` field, report the metric as unavailable, and offer the CSV route (Step 5.0), which needs no `sustainability:` action. Only a service-returned `AccessDeniedException` indicates a permissions gap. |
| Attached CSV fails a Step 5.0 validation check | Malformed, mixed-methodology, or wrong-account export | Report emissions as unavailable and name the specific check that failed. Do **not** fall back to using the file anyway. |
| Attached CSV covers carbon but not water (or vice versa) | Console exports are generated per metric; Data Exports carries carbon only | Use the CSV for the metric it covers and attempt the API for the other. State the two different sources. |
| `AccessDeniedException` on water only | Water is authorized separately from carbon | Report carbon normally, note that water needs `sustainability:GetEstimatedWaterAllocation`, and ask for a console water export. **Never let one of the two failing suppress the other** — attempt both independently. |
| Water call returns no result for any year | Range missed a 1 January start, no published year in range, or impact below the threshold | Check the `TimePeriod` rule in Step 5.2, then ask for a console water export. If the export is empty too, report water as below the reporting threshold or not yet published, and say which year was requested. |
| Empty result for recent months | Month M publishes by the 21st of month M+1 | State the latest month returned and the publication rule. Before the 21st the latest month can be two back; that is the normal lag. Never report an unpublished month as zero emissions or call it a two-month lag. |
| Empty water result for the current or previous year | Year Y publishes in Q2 of year Y+1 | Report the most recent published year and say which year the figure covers. |
| Zero / absent values | Below the reporting threshold (0.5 g CO2e for carbon, **0.5 mL** for water), or account too new | State that impact is below the reporting threshold — this is not the same as no impact. |
| Management vs member view | Management accounts see consolidated data for member accounts; member accounts see only their own | Decide from the call 2 results in Step 5.1: more than one account is a management-account view, only the caller's account is a member or standalone view. State which, and never assert either without that evidence. |

The review MUST complete and produce a full report even when the Sustainability API is
unavailable in whole or in part. Emissions and water data are enrichment, not prerequisites.

### Month-length rule

Monthly emissions are a total over the month, not a rate, so a 28-day month carries about
10% less than a 31-day one at identical usage. February will therefore look like an
improvement and any 31-day month following it like a regression, with no change in the
workload. Before reporting any month-over-month delta, divide each month's figure by that
month's day count and compare the per-day values, or state the raw delta alongside the
day counts and the note that the difference is not usage-driven. A delta smaller than the
day-count difference between the two months is **not** a finding.

## Known API Quirks

- `sustainability.GetEstimatedCarbonEmissions` selects months on a **half-open** window:
  month `M` is returned iff `Start <= M-01T00:00:00Z < End`. Both boundaries bite — a `Start`
  of `2026-03-15` (or even `2026-03-01T00:00:00.001Z`) silently drops March, and an `End` of
  exactly `2026-06-01T00:00:00Z` excludes June. Normalise `Start` to `YYYY-MM-01T00:00:00Z`,
  and set `End` past the first instant of the last month you want. Read the `TimePeriod` on
  each result rather than assuming which months a request covered.
- `sustainability.GetEstimatedWaterAllocation` applies the same half-open rule on **year**
  boundaries, accepts only `YEARLY_CALENDAR` (anything else is a `ValidationException`), and
  is a **separately authorized** IAM action — see the Step 5.2 trap table.
- Carbon for month M publishes by the 21st of month M+1, so the current month is always absent
  and, before the 21st, the previous month can be too. That is the normal lag, not missing data.
- Values below 0.5 g CO2e (carbon) or 0.5 mL (water) are not reported. Absent ≠ zero.
- Granularity supports fiscal-year variants (`YEARLY_FISCAL`, `QUARTERLY_FISCAL`) with
  `GranularityConfiguration.FiscalYearStartMonth` — use these when the customer reports
  on a fiscal calendar, otherwise `MONTHLY`.
- The API is global; the endpoint is not regional. `AllowedRegions`-style region
  restriction policies must not deny it.
- Management accounts see consolidated org data for the period member accounts belonged
  to the org; member accounts see only their own. Establish which from the `USAGE_ACCOUNT_ID`
  call, never from assumption.
- `s3.GetBucketSizeBytes` via CloudWatch needs the `StorageType` dimension to split by
  storage class — without it you cannot apply the Step 4.2 weights.
- `ec2.DescribeInstanceTypes` is the authoritative vCPU source. Do not hardcode vCPU
  counts from instance-name arithmetic. It is also the accelerator-count source
  (`GpuInfo`, `NeuronInfo`); for SageMaker types, strip the `ml.` prefix first.
- SageMaker endpoint and job metrics sum utilization across devices: `GPUUtilization` and
  `CPUUtilization` run to 100 × the device count, unlike EC2's 0–100. Only inference
  components publish `*Normalized` variants.
- Compute Optimizer returns Graviton options only when the request sets
  `recommendationPreferences.cpuVendorArchitectures: ["AWS_ARM64"]`; every `Get*Recommendations`
  call fails with `OptInRequiredException` until the account opts in. It never recommends an
  architecture change for Lambda or ECS.
- An ECR image index (`imageManifestMediaType` of an OCI index or Docker manifest list) does not
  prove the image includes arm64 — single-architecture images with attestations also use one.
