# LLMOps Capacity & Cost Report

Fill in every `<placeholder>`. Delete a row only when it genuinely does not apply, and when you
do, say why in **Scope not covered**. Never leave a placeholder unresolved in a delivered report.
**Every dollar figure is marked `(billed)` with its Cost Explorer grouping, or `(estimated)` with its derivation.**

## Scope

- **Region(s) examined:** `<region>`
- **Time window examined:** `<start-date>` → `<end-date>` (UTC, `End` exclusive: last day included `<end-date − 1>`; computed from run date `<today UTC>`)
- **Coverage check:** `<passed — no billed cost or tokens outside the window / spend outside the window: <model, day, amount> — extended or reported separately / not run — figures may understate spend: <reason>>`
- **Models / inference profiles in scope:** `<model-ids-or-profile-ids>`
- **Defaults chosen (if any):** `<e.g. defaulted to caller's current region and trailing 30-day window>`

## Cost model (billed vs estimated)

> **(billed)** figures come from Cost Explorer, grouped by the Bedrock product attribute `model` or by
> `USAGE_TYPE`, with no `SERVICE = "Amazon Bedrock"` filter. **(estimated)** figures come from
> `AWS/Bedrock` token metrics × current published prices, covering all four token types.

- **Billed source:** `ce:GetCostAndUsage` grouped by `<PRODUCT_ATTRIBUTE model / USAGE_TYPE>`, window
  `<start>` → `<end>`. Service names included: `<names from GetDimensionValues / SERVICE filter omitted>`.
- **Token-model derivation:** `InputTokenCount` × `<input rate>` + `OutputTokenCount` × `<output rate>`
  + `CacheReadInputTokenCount` × `<cache-read rate>` + `CacheWriteInputTokenCount` × `<cache-write rate>`,
  prices from `<Bedrock pricing page via verify_aws_claim / user-supplied>` as of `<date>`, assuming `<Standard tier, source-region rate>`.

| Model | Billed spend | Input / output / cache-read / cache-write tokens | Modelled spend | Divergence |
|---|---|---|---|---|
| `<model>` | `$<value>` **(billed)** | `<sum>` / `<sum>` / `<sum or no datapoints>` / `<sum or no datapoints>` | `$<value>` **(estimated)** | `<%>` |

- **Total:** billed `$<billed-total>` **(billed)** vs modelled `$<modelled-total>` **(estimated)**,
  divergence `<%>`. `<within tolerance / unexplained lines itemised below>`.
- **Metered, not billed (per day):** `<model / day / CloudWatch tokens with no billed line — unexplained / none>`.
- **Partly billed (recent days):** `<model / day / metered vs billed tokens — billed total not complete yet / none>`.
- **Billed lines the token model does not cover:** `<PT model-unit hours, -flex / -priority /
  -cross-region-global lines, non-token features / none>`.
- **Per caller / application:** `<billed via IAM principal attribution or application inference profile
  tags / estimated by proportional allocation — derivation / not requested>`.
- **Billed data unavailable:** `<no / ce:GetCostAndUsage denied or no data — token model is the
  result, labelled (estimated)>`.
- **Forward-looking projection:** `<none / directed to https://calculator.aws/ — not fabricated>`.

## Provisioned Throughput / reserved-tier inventory

| PT (masked ARN) | Status | Model units | Observed tokens/min (peak, avg) | check-id |
|---|---|---|---|---|
| `arn:aws:bedrock:...:<account>:provisioned-model/<id>` | `<InService>` | `<units>` | `<values or no datapoints>` | `<LLM-PT-001 / none>` |
| `<reserved usage type>` | `<reserved, term>` | `<reserved input / output TPM>` | `<observed input / output TPM>` | `<LLM-PT-001 / none>` |

> `InService` = provisioned and **billing**, not proof of use. Idle PT is billing-while-idle.

## Throughput headroom & throttling

- **`InvocationThrottles` over window:** per `ModelId` `<count / no datapoints>`, no-dimension
  series `<count / no datapoints>`; throttle rate `<throttles ÷ (Invocations + throttles)>` →
  `<LLM-INV-007 / none>`
- **Quota rejections** (`InvocationClientErrors`, `ServiceQuotaExceededException`):
  `<count / not separable — rejected requests not in logs / no datapoints>`
- **Quota headroom** (one line per model): peak `EstimatedTPMQuotaUsage` `<tokens/min / no datapoints>` ÷
  `<on-demand / cross-region / global>` TPM quota `<code, name, value; "matched by name" if so>` =
  `<% used>` (approximation), or `not computed — <no row in that form (forms it has) / no TPM row for
  the model (closest rows, other quota kinds)>`

  | Quota name | Code | Applied value | Adjustable |
  |---|---|---|---|
  | `<QuotaName as returned>` | `<QuotaCode>` | `<Value>` | `<yes / no>` |

- **Invoked by direct model ID vs inference profile:** `<direct / profile>` → `<LLM-INV-002 / none>`

## Findings

| check-id | severity | observed value | remediation |
|---|---|---|---|
| `<LLM-...>` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<concrete value that triggered it>` | `<exact read-only-recommended fix>` |

> No freelance findings — every row cites a catalog `check-id` and that check's severity.

## Recommended alarms

| alarm | namespace / metric | threshold | source |
|---|---|---|---|
| `<Quota consumption high>` | `AWS/Bedrock` / `EstimatedTPMQuotaUsage` | `<100 * m1 / TPM quota > 80>` | `<Derived>` |
| `<Token-spend spike>` | `AWS/Bedrock` / `OutputTokenCount` | `<anomaly band>` | `<Workload-specific>` |
| `<Elevated throttling>` | `AWS/Bedrock` / `InvocationThrottles` | `<baseline>` | `<Derived>` |

## Scope not covered

- Regions skipped: `<regions / none>`
- Checks blocked by permissions: `<API + resource you could not read, e.g. ce:GetCostAndUsage / none>`
- Metrics with no datapoints: `<metric names / none>`
- Other disclosed assumptions: `<region-unsupported feature, budget bound, etc. / none>`
