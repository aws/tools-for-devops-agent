# Report Format

The report is the authoritative output of this skill. Render it verbatim,
substituting only placeholder values. Do not reorder sections, drop sections, or
replace the report with a summary.

## Structure

````markdown
# DynamoDB Data Health Inspection — `<table>`

**Account** `<account_id>` · **Region** `<region>` · **Inspected** `<YYYY-MM-DD HH:MM UTC>`
**Health rating: `<High|Medium|Low|Indeterminate>`**

<one-paragraph summary: the highest-severity finding in plain language, what it
costs or risks, and the single next action. Lead with the dimension the user asked
about. No preamble.>

## Table Profile

| | |
|---|---|
| Status | `<table_status>` |
| Capacity mode | `<billing_mode>` |
| Items | `<item_count>` (approximate) |
| Size | `<table_size>` (approximate) |
| Mean item size | `<mean_item_size>` (approximate) |
| Partition key | `<partition_key>` |
| Sort key | `<sort_key or "none">` |
| GSIs | `<n>` · LSIs | `<n>` |
| TTL | `<ENABLED on `attr` | DISABLED>` |
| Contributor Insights | `<ENABLED (mode) | DISABLED>` |

> `ItemCount` and `TableSizeBytes` are refreshed by DynamoDB approximately every six
> hours and are approximations.

## Dimensions

| Dimension | Result | Assessed via |
|---|---|---|
| Hot keys | `<emoji> <one-line verdict>` | `<Contributor Insights + CloudWatch | not determinable>` |
| Item size | `<emoji> <one-line verdict>` | `<sample of N | table metadata only>` |
| TTL effectiveness | `<emoji> <one-line verdict>` | `<CloudWatch + sample of N | CloudWatch only | not configured>` |
| Index utilization | `<emoji> <one-line verdict>` | `<CloudWatch 30 d | no indexes>` |

Emoji: ✅ healthy · ⚠️ finding at Medium or Low · ❌ finding at High · ➖ not
applicable · ❓ not assessed.

A dimension with any `AccessDenied` or `ToolingFailure` input is ❓, never ✅.

## Sampling Provenance

| | |
|---|---|
| Status | `<completed | declined | skipped | aborted>` |
| Reason | `<reason>` *(omit when completed)* |
| Mode | `<shape | minimal-exposure>` |
| Items sampled | `<N>` (`<pct>`% of table) |
| Segments / pages | `<S>` / `<P>` |
| Read units consumed | `<consumed_rcu>` (estimated `<estimated_rcu>`) |
| Elapsed | `<elapsed>`s |
| Size accuracy | `<drift>`% computed-vs-billed drift |
| Confidence | `<confidence>` |

A `Scan` sample is ordered by partition layout, not randomly. Sampled findings are
corroborating evidence about how data is **stored**; they are not measurements of
how traffic is **distributed**. Item values were not recorded.

*(When `status` is `declined`, `skipped`, or `aborted`, replace the table's lower
rows with a single line naming which findings were therefore not assessed.)*

## Findings

<Ordered by severity — High, then Medium, then Low, then Info. Within a severity,
by dimension in the order hot keys, item size, TTL, index utilization.>

### `<SEVERITY>` · `<RULE_ID>` · `<short title>`

<verbatim body template from finding-logic.md, placeholders substituted>

**Evidence:** `<the metric name and value, API field, or sample statistic that
proves this — with the window and the target it was measured on>`

<repeat per finding>

## Not Assessed

| Dimension / check | Why | To assess it |
|---|---|---|
| `<check>` | `<AccessDenied on <action> | sampling declined | metric NoData | LSI metrics do not exist>` | `<action>` |

Omit this section only when every check returned `OK`.

## Recommended Actions

| # | Action | Addresses | Effort | Reversible |
|---|---|---|---|---|
| 1 | `<imperative action>` | `<RULE_IDs>` | `<Low|Medium|High>` | `<Yes|No>` |

Ordered by severity addressed, then ascending effort. Every High finding must appear
here. Mark projection changes and LSI changes as **not reversible in place** — both
require creating a replacement index.

## References

- Best practices for partition keys and write sharding — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html
- Write sharding to distribute workloads evenly — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-sharding.html
- Contributor Insights for DynamoDB — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/contributorinsights_HowItWorks.html
- Using time to live (TTL) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
- Service, account, and table quotas — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ServiceQuotas.html
- Constraints (item size, item collections) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html
- Best practices for secondary indexes — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes.html
- Best practices for large items and attributes — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html
- Metrics and dimensions — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/metrics-dimensions.html
````

## Health rating

Assign from the highest-severity finding, then apply the caps.

The rating describes the table's **health**, so it runs opposite to finding
severity: a High-severity finding produces a Low health rating. Always write the
rating with its meaning attached so the direction cannot be misread —
`Health rating: Low — needs attention`.

| Rating | Means | Criteria |
|---|---|---|
| **High** | Good health | Only Low or Info findings across all four dimensions |
| **Medium** | Some concerns | No High finding, at least one Medium |
| **Low** | Needs attention | Any High finding |
| **Indeterminate** | Cannot assess | Two or more dimensions are ❓ |

### Caps

- Any `AccessDenied` or `ToolingFailure` input → cap at **Medium**, and say why.
- `sampling.status != "completed"` → cap at **Medium**. Item-size distribution and
  per-item TTL state are unknown, so a clean bill of health is not supportable.
- Two or more dimensions ❓ → **Indeterminate** regardless of findings.

A cap can only lower a rating, never raise it.

## Multi-table reports

For 2–10 tables, keep one report but replace **Findings** with:

1. A summary matrix — one row per table, one column per dimension, emoji per cell,
   plus a rating column.
2. A common-gaps table, sorted by how many tables share each rule id.
3. Full per-table detail for every table rated **Low**, and for any table the user
   named specifically.

Sort by rating, worst first; alphabetical within a rating. Honor "keep order" if the
user asks. Sampling consent is still per table — the matrix must show each table's
sampling status, since some may be sampled and others declined.

## Pre-render validation

Run all 14 checks before delivering. If any fails, fix the report — do not ship it
with a note.

1. Every dimension has a row in the Dimensions table.
2. No dimension shows ✅ while a finding for it appears in Findings.
3. No dimension shows ✅ if any of its inputs was `AccessDenied`, `ToolingFailure`,
   or `NoData` for the signal that dimension depends on. In particular the hot-key
   dimension is ❓ whenever HK-01, HK-04, or HK-06 fired.
4. Every finding body matches its `finding-logic.md` template, with only
   placeholders substituted.
5. Every finding has an Evidence line naming a metric, API field, or sample
   statistic — plus the window and target.
6. No `[B]` finding appears unless a sample completed or aborted with usable data.
7. Every `[B]` finding carries a confidence annotation.
8. The confidence downgrade rule was applied wherever `n < 100` or
   `pct_of_table < 0.01`.
9. Every cross-reference consistency rule in `finding-logic.md` passes.
10. **No item attribute value appears anywhere in the report** — no example items, no
    excerpts. Partition keys appear only as digests or truncations.
11. The health rating matches the criteria, and every applicable cap was applied.
12. Sampling Provenance is present and its status matches what actually happened.
13. Every High finding appears in Recommended Actions.
14. The Not Assessed section lists every non-`OK` check, or is omitted because all
    checks were `OK`.

## Tone

- Lead with what is wrong and what it costs. No preamble, no restating the request.
- Quantify. "GSI `orders-by-status` consumed 4.2 M write units and zero read units
  over 30 days" beats "an index appears unused".
- Name the limit a finding approaches — 400 KB, 10 GB, 1,000 WCU/s, 3,000 RCU/s —
  and whether it is a hard limit or a soft one.
- Distinguish measured from estimated from extrapolated, every time.
- Do not hedge a measured finding, and do not present an estimate as measured.
