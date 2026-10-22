# Output template (mandatory)

Read this file in Step 7 of SKILL.md, before writing the output.

You MUST produce the output in exactly this structure: the same nine sections, in the same order, with the same headings and the same table columns. Do not replace any table with prose or bullet points, and do not drop, rename, or reorder columns. Never summarize the cost in a sentence or in a short "Metric / Value" table outside this dashboard; the dashboard is the only accepted cost output, including when nothing could be priced.

## Formatting rules

- **One row per price line.** A resource with several fixed components (for example instance hours and storage) gets one row per component, labeled `<LogicalId> · <component>`, and the same `#` with a letter suffix (`A1`, `A1b`).
- **Money:** `$` with two decimals. Round each row to cents first; every total is the sum of the rounded rows shown. Sign every amount in the Monthly, Delta, Effect, and Net columns: `+` for an increase, `−` for a decrease.
- **Traceability:** every dollar amount in the Added, Removed, Resized, and Topology adjustments tables points to a `P` row in the Pricing trace. Every `P` row shows the lookup or filters sent; the Summary's Price source row says how many lines came from each source. The Usage-dependent and Not determinable tables never contain a dollar amount.
- **Topology results:** per-resource findings from the second check go in the Topology adjustments table only; the Added and Removed tables don't carry a topology column.
- **Empty sections:** keep the heading and write `_None._` under it.
  - If the topology check wasn't needed, write `_Topology check not needed: <why the repo comparison was enough>. Net change equals the repo-based net._` under that heading.
  - If it was needed but skipped, write `_Topology check skipped: needed because <reason>; <error>. Net change equals the repo-based net._` under that heading.
- **Placeholders:** replace every `<…>` with a real value from this run. Never output a placeholder, and never copy a value from this template.
- **When no price line could be priced (Step 5), put one of these two banners directly under the `##` heading.** Pick by what actually happened; a source you never called is "not attempted", not "failed".
  - **Every source was called and failed:** `> ⛔ **Pricing not available in this run.** verify_aws_claim: <exact error or reason> · Price List API <endpoint>: <exact error> · <endpoint>: <exact error> · <endpoint>: <exact error> · offer files: <exact HTTP or network error>. **Fix:** <one specific action matching the errors: enable verify_aws_claim for this agent type · add pricing:GetProducts, pricing:GetAttributeValues, and pricing:DescribeServices to the Agent Space role · allow the pricing endpoint Region in the AWS tool's Region policy · enable an AWS tool for this agent type · allow outbound HTTPS to pricing.us-east-1.amazonaws.com>.`
  - **This phase lacks the tools to call a source:** `> ⏭️ **Not priced in this phase.** verify_aws_claim: <exact error, or not available> · Price List API: not attempted (no AWS tool) · offer files: not attempted (no shell or HTTP tool). **If verification testing ran the "IaC cost estimate" test, its dashboard is the priced result; otherwise re-run with pricing access.**` No Fix line: nothing is broken, the environment was never tested. Never write that the price files or the API are unreachable when you did not call them.
  - In both cases, still fill the Added, Removed, and Resized tables completely, with sizing and quantity. Write `not priced` in every Rate, Monthly, Before monthly, After monthly, and Delta cell, and `—` in Price ref.
  - In the Summary, write `**not priced (see banner)**` for Net monthly change, and `<n> resources · not priced` for Added, Removed, and Resized.
  - Write `_None._` under Pricing trace. Don't repeat the pricing failure as a reason on each row of the Not determinable table; that table is only for resources that failed individually. Skip the arithmetic check.
- **When verification testing already priced the change** (its "IaC cost estimate" test result is in your context): if that result is already a full dashboard, don't produce a second one; reference it (one dashboard per diff). If it is only a list of priced lines, build the dashboard from those numbers, keep its rates and units in the Pricing trace, and set the Summary's Price source row to `verification testing ("IaC cost estimate" test) · offer files: <n> lines · …`. Do not re-derive or round its figures.

## Template

```markdown
## 💰 IaC cost impact · <repo> · <PR number or branch>

### 📊 Summary
| Metric | Value |
|---|---|
| **Net monthly change** | **≈ <+/−>$<amount> / month** |
| Repo-based net (first check) | <+/−>$<amount> |
| Topology adjustment (second check) | <+/−>$<amount> · <n> resources |
| ➕ Added | <n> resources · +$<amount> |
| ➖ Removed | <n> resources · −$<amount> |
| 🔁 Resized | <n> resources · <+/−>$<amount> |
| Unchanged for cost | <n> resources |
| 📈 Usage-dependent (not in total) | <n> items |
| ❔ Not determinable / conditional (not in total) | <n> items |
| Pricing Region | <region code> · <how it was determined> |
| Baseline | <base branch> · topology check: <not needed / done (<reason>) / skipped (<reason>; <error>)> |
| Price source | AWS pricing docs: <n> lines · Price List API: <n> lines · offer files: <n> lines · on-demand list price · queried <YYYY-MM-DD> |

### ➕ Added resources
| # | Logical ID | Type | Sizing | Qty | Rate | Monthly | Price ref |
|---|---|---|---|---:|---|---:|---|
| A<n> | <LogicalId> | <AWS::Service::Type> | <key attributes> | <n> | $<rate> / <unit> | +$<amount> | P<n> |
| | **Total added** | | | | | **+$<amount>** | |

### ➖ Removed resources
| # | Logical ID | Type | Sizing | Qty | Rate | Monthly | Price ref |
|---|---|---|---|---:|---|---:|---|
| R<n> | <LogicalId> | <AWS::Service::Type> | <key attributes> | <n> | $<rate> / <unit> | −$<amount> | P<n> |
| | **Total removed** | | | | | **−$<amount>** | |

### 🔁 Resized resources
| # | Logical ID | Type | Change (before → after) | Before monthly | After monthly | Delta | Topology check | Price refs |
|---|---|---|---|---:|---:|---:|---|---|
| Z<n> | <LogicalId> | <AWS::Service::Type> | <property>: <before> → <after> | $<amount> | $<amount> | <+/−>$<amount> | <➖ not needed · ✅ matches repo · ⚠️ deployed value differs · ⏭️ skipped> | P<n>, P<n> |
| | **Total resized** | | | | | **<+/−>$<amount>** | | |

### 🔎 Topology adjustments (second check)
| Ref | Logical ID | First-check class | Finding | Effect on total |
|---|---|---|---|---:|
| <A/R/Z><n> | <LogicalId> | <Added / Removed / Resized> | <already deployed: exact match `<physical id>` (create fails unless imported) · never deployed · deployed <property> is <value>> | <+/−>$<amount> |
| | **Total adjustment** | | | **<+/−>$<amount>** |

### 🧾 Pricing trace
| Ref | Used by | Query or filters sent | Rate (USD) | Unit | Monthly |
|---|---|---|---:|---|---:|
| P<n> | <A/R/Z refs> | <docs: the lookup sent · API or offer file: ServiceCode · filter=value · …> | <rate> | <unit> | $<amount> |

### 📈 Usage-dependent (not in total)
| Logical ID | Type | Billed on | Fixed part priced in |
|---|---|---|---|
| <LogicalId> | <AWS::Service::Type> | <what drives the charge: requests, GB processed, GB-month stored, LCU-hours, …> | <A/R/Z ref, or —> |

### ❔ Not determinable / conditional (not in total)
| Logical ID | Type | Reason | Candidates seen |
|---|---|---|---|
| <LogicalId> | <AWS::Service::Type> | <no usable rate: docs: <reason> · API: <no matching SKU after retry, last filters sent / only $0.00 match / exact error> · condition `<Name>` false at defaults (created when `<Parameter>=<value>`)> | <SKU or URL: rate / unit, … or —> |

### ⚠️ Caveats
- <every item from "Important Caveats to Always Include" in SKILL.md, applied to this run>
```
