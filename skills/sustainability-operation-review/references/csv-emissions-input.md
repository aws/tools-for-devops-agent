# Carbon and Water CSV Exports

Read this file at Step 5 when a carbon or water `.csv` export is attached or referenced, when
the customer prefers to supply an export instead of granting API access, or when the water call
fails or returns nothing.

## When to use a CSV export

The AWS Sustainability API is the default source. A CSV export is the supported alternative in
two cases:

| Use | When | What the customer supplies |
|-----|------|----------------------------|
| Customer-supplied data | The customer prefers to supply their own export instead of granting the agent's role the `sustainability:` actions, or attaches one | A carbon or water export from **Reports** in the AWS Sustainability console, or a carbon export from AWS Data Exports delivered as CSV. Neither needs a `sustainability:` action on the agent's role. |
| Water fallback | `GetEstimatedWaterAllocation` fails, or returns no result | A water export from **Reports** in the AWS Sustainability console. Data Exports does not carry water data, so the console is the only export source for water. |

If the customer says they prefer to supply an export but has not attached one, ask for it before
calling the API for that metric. When a carbon call fails, the "no data" table in
`references/emissions-collection.md` also offers this route.

## Step 5: Resolve the route first

Check for an attached export before the first API call, then resolve each metric in this order.
Do not treat a carbon-only attachment as a reason to skip the water call, or the reverse.

| Order | Route | Use when |
|-------|-------|----------|
| 1 | **Attached CSV** (Step 5.0) | A carbon or water `.csv` is attached, or the user references one. Use it for the metric it covers. |
| 2 | **AWS Sustainability API** (Steps 5.1, 5.2) | For every metric no attached CSV covers. |
| 3 | **Requested CSV** (Step 5.0) | The water call failed or returned nothing: ask the user for a console water export. If none is supplied, report water as unavailable. |

If both are available for the same metric, **prefer the attached CSV** — an explicit attachment
is a deliberate choice of input, and overriding it with the API silently discards what the user
supplied. Still call the API for any metric the CSV does not cover. Never merge the two sources
into one figure or table; report whichever you used and say which.

### 5.0 Read and validate the export

Read the file and map its columns rather than assuming a layout. A carbon export has one row per
period × service × Region (and per account, when the export carries an account column) and uses
these column names:

| Column | Meaning | Maps to |
|--------|---------|---------|
| `usage_year` or `usage_month` / `usage_period_start` | Reporting period | Determines granularity — see the granularity rule below |
| `service` or `product_code` | AWS service | `GroupBy: SERVICE` equivalent |
| `region` or `region_code` / `location` | Region (display name or code) | `GroupBy: REGION` equivalent |
| `usage_account_id` / `payer_account_id` | Account scope | Confirms whose data this is — reconcile against Step 1 |
| `total_lbm_emissions_value` | Location-based total, MTCO2e | `TOTAL_LBM_CARBON_EMISSIONS` |
| `total_mbm_emissions_value` | Market-based total, MTCO2e | `TOTAL_MBM_CARBON_EMISSIONS` |
| `total_scope_1_emissions_value` | Scope 1 | `TOTAL_SCOPE_1_CARBON_EMISSIONS` |
| `total_scope_2_lbm_emissions_value` / `total_scope_2_mbm_emissions_value` | Scope 2, both methods | `TOTAL_SCOPE_2_*_CARBON_EMISSIONS` |
| `total_scope_3_lbm_emissions_value` / `total_scope_3_mbm_emissions_value` | Scope 3, both methods | `TOTAL_SCOPE_3_*_CARBON_EMISSIONS` |
| `cfe_savings_value` | Carbon-free-energy benefit, = LBM − MBM | No API equivalent; report as-is, do not add to any total |
| `model_version` | Methodology version | `ModelVersion` — quote it exactly as it appears |
| `*_unit` columns, if present | Unit of the adjacent value | Verify it is `MTCO2e`. If the columns are absent, state that the unit is assumed to be MTCO2e rather than confirmed |

A water export is annual and has no scopes and no LBM/MBM split. Map its columns the same way:
the year, service, Region, account, the withdrawal value, and the water model version. Verify the
unit is `m3`; if no unit column is present, state that the unit is assumed rather than confirmed.
Water carries its own model version line, independent of carbon's.

**State these water caveats every time you report a water figure from an export**, as for the
API: the value is in m3 and annual only; it is water **withdrawn, not consumed**; it covers
AWS data-center operations only, excluding water embodied in upstream electricity generation.
Water is disclosure only: derive no finding, KPI, trend driver or recommendation from it, and
never attribute a year-over-year change to the customer.

**Validate before you use it.** Run all four checks (three for water — check 1 is carbon only)
and state the outcome in the report:

1. **Scope identity** — `scope_1 + scope_2_lbm + scope_3_lbm` must equal `total_lbm`, and the
   MBM triple must equal `total_mbm`, per row. If rows fail, report the file as
   partially unusable and name the failing rows. Do not silently recompute totals.
2. **Model version** — if more than one `model_version` appears, the file mixes
   methodologies. Report the versions separately and do **not** compare across them.
3. **Account scope** — reconcile the account columns against the workload from Step 1. If the
   file is for a different account than the topology you discovered, **stop and say so**:
   the emissions figures and the KPIs describe different systems, and combining them is
   invalid regardless of how plausible the numbers look. **If the file carries no account
   column at all, this check cannot be performed** — record it as unverified, ask the user
   which account and period the export came from, and do not assume it matches the topology.
   An absent column is not a passed check. If the file lists more than one usage account, it is
   a management-account export: report the per-account breakdown, as for the API.
4. **Period completeness** — see the rule below. This is the single most common source of a
   wrong conclusion from a CSV.

**Granularity rule.** A CSV keyed by `usage_year` is **annual**, and a water export is always
annual. Annual data cannot support the 30-day KPI comparison windows in Step 6,
month-over-month trends, or any monthly hotspot series. Report annual figures against annual
periods only, state the granularity explicitly, and omit — do not approximate — the monthly
views. Never divide an annual figure by 12 to manufacture a monthly one.

A CSV keyed by `usage_month` (or `usage_period_start` at month resolution) is **monthly** and
supports the full month-over-month series, per-service and per-Region hotspot ranking, and
like-for-like partial-year comparison. Roll months up to a year only when every month of that
year is present, and say which months you summed.

**Month-length rule — apply to every month-over-month comparison, from a CSV or the API.**
Monthly emissions are a total over the month, not a rate, so a 28-day month carries about
10% less than a 31-day one at identical usage. February will therefore look like an
improvement and any 31-day month following it like a regression, with no change in the
workload. Before reporting any month-over-month delta, divide each month's figure by that
month's day count and compare the per-day values, or state the raw delta alongside the
day counts and the note that the difference is not usage-driven. A delta smaller than the
day-count difference between the two months is **not** a finding.

**Partial-period rule — apply this before any year-over-year statement.** The most recent
period in an export is very often incomplete, because the current year is still accruing. A
CSV carries no flag telling you this. So:

- Compare the latest period's coverage against the publication timing in
  `references/emissions-collection.md`: carbon for month M is published by the 21st of month
  M+1, and water for year Y in Q2 of year Y+1.
- If the latest year is partial, you MUST NOT compare its total against a complete year, or
  describe it as an increase or decrease. Say how many months it covers and either compare
  like-for-like against the same months of the prior year (only if the file has monthly rows)
  or report the two periods side by side with the coverage stated and **no** delta.
- With monthly rows the like-for-like comparison is the one to prefer: sum the same calendar
  months in each year (e.g. Jan–Jun 2025 vs Jan–Jun 2026) and name the months you summed. This
  is a valid comparison; a partial-year total against a full-year total never is.
- A partial current year that totals *more* than a complete prior year is a signal about
  growth in the underlying resources, not a computed trend — hand it to Step 8, do not assert it.

**Provenance.** State in the report header where the data came from, verbatim: the filename,
the metric (carbon or water), the period it covers, the `model_version`, and that it was
**user-provided rather than retrieved from the API**. If the user described the file as sample,
mock, example, or anonymised data, label every figure derived from it as illustrative and add a
line to the Executive Summary saying the environmental impact figures are not this account's
measured emissions. Never present user-supplied numbers as API-sourced.

**The Core Framing Rule (`references/framing-and-attribution.md`) applies unchanged.** A CSV is
the same top-down allocated data as the API returns — arriving by a different route does not
make it attributable to customer action.
