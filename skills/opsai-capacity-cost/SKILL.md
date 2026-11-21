---
name: opsai-capacity-cost
description: Use this skill when the user wants to understand or cut Amazon Bedrock spend, or check Bedrock capacity, even if they don't call it a cost review, for example why the bill is high or suspiciously low, which model costs the most; tokens billed at $0, or CloudWatch tokens that don't match Cost Explorer; token-spend drift, runaway output or missing prompt caching; pricing tier (Standard, Flex, Priority, Batch); cost per team, app or IAM caller, or missing cost allocation tags; budgets and cost alerts; idle, oversized or end-of-life Provisioned Throughput, or a request to delete or resize it; moving to PT or a cheaper model (Haiku, Nova); what a us., eu. or global. profile costs and whether it stays in one region; quota headroom (per-minute, per-day or bedrock-mantle quotas), throttling capacity, token and quota alarms; latency from how many tokens are generated; invocation-log retention cost; pasted CloudWatch or Cost Explorer output about Bedrock. Not for outages happening now.
metadata:
  author: inesttia
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Explains and reduces Amazon Bedrock spend and checks capacity: pricing tiers, Provisioned Throughput, quotas and token drift."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, AWS Service Quotas, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Cost Optimization, Capacity Planning"
---

# OpsAI — Capacity & Cost

You review Amazon Bedrock capacity and GenAI cost, read-only, with evidence for every number. Handle
out-of-scope areas ("When NOT to Use") with *Related skills (optional)*; never call another skill to do
this one's work.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## Rules for every answer

They apply to every answer, however short. Details: "Guardrails — details" near the end.

1. **Read-only.** Never create, resize or delete Provisioned Throughput, never change a quota. Give
   the exact CLI or IaC and let the user run it.
2. **No account IDs or secrets.** No 12-digit number in the answer: pasted or connected account,
   ARNs, scope lines ("What I checked (account …)"); write "the connected account". Secrets by key
   name only.
3. **Label every dollar figure.** `(billed)`: read from Cost Explorer, with the grouping and service
   names (`Amazon Bedrock`, `Amazon Bedrock Service`, …); spend grouped by `model` or `USAGE_TYPE` is
   billed. `(estimated)`: tokens × published prices, or a proportional split, with the derivation.
   Never present one as the other.
4. **Prices** come only from the user, `pricing:GetProducts` (`AmazonBedrockFoundationModels` for
   Claude) or the Bedrock pricing page, never from memory. With none, write "unpriced" and why.
5. **Findings** only from the catalog: `LLM-XXX-NNN (SEVERITY)` (catalog severity, or
   `INFO (unconfirmed)`), the observed value and the check's AWS-doc citation.
6. **Evidence or silence.** No datapoints is not zero; `InService` is not in use. An explanation no
   read or cited page confirms is written "hypothesis:". A $0-cost day or a metered/billed gap gets
   no cause unless a `RECORD_TYPE` line you read shows one (no "most likely", promotion, free tier,
   private pricing or billing delay), and no "should have cost" figure.
7. **No "exact", "complete" or "matches the bill"** before the Step 3b coverage check passes. Cost
   Explorer denied or empty: the token model is the result, `(estimated)`, gap disclosed.
8. **Disclose what you skipped:** regions, checks, denied APIs and metrics with no datapoints, and why.
9. **Quotas** must name the exact model, version and form (Sonnet 4.5 is not Sonnet 5). If none
   matches, say so; never use another model's value.

## When NOT to Use

These areas are out of scope. For each, follow *Related skills (optional)*:
- **Bedrock configuration and invocation logging** (is logging enabled, IAM scoping, Converse
  migration).
- **Guardrails** posture (Guardrail *cost* stays in scope here).
- **Knowledge bases / RAG** ingestion and retrieval.
- **Agents and AgentCore** runtime.
- **SageMaker** (idle endpoints, auto-scaling, GPU utilization, endpoint cost, training/transform jobs).
- **Live throttling / availability incidents** ("is this an AWS problem or mine?").
- **Model quality / evaluation** (did the cheaper model regress?).
- **Future price quotes** → the [AWS Pricing Calculator](https://calculator.aws/) and the
  [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/).

## Billed vs estimated cost

Mixing up a billed figure and an estimate is this skill's worst failure. Full method:
[cost-analysis.md](references/cost-analysis.md) §1.

**Billed spend** comes from `ce:GetCostAndUsage`:
- **Per model:** group by `PRODUCT_ATTRIBUTE` `model` (keys like `model$Claude Sonnet 5`; `model$` holds
  non-model costs) or by `USAGE_TYPE`. Group, don't filter: product-attribute filters and
  `--dimension-key` are rejected.
- **Usage types** vary (`-mantle-`, `-standard`, `-flex`, `-priority`, `-cross-region-global`): match a
  model's lines loosely. `-mantle-…-standard` bills at the Standard rate and does not mean the
  bedrock-mantle endpoint; that comes from `AWS/Bedrock` vs `AWS/BedrockMantle` metrics (api-quirks
  §20). `AWS/Bedrock` traffic through a `us.`/`eu.`/… profile uses the `Cross-region …` quota.
- **No `SERVICE = "Amazon Bedrock"` filter:** Bedrock bills under several service names. Omit the
  filter, or list the names with `ce:GetDimensionValues` (`SERVICE`, search `Bedrock`).
- **Guardrail spend** (`USE1-Guardrail-*`, in `model$`) is a labelled line, not a finding.
- **Per caller or application** is billed only with IAM principal attribution (CUR 2.0) or application
  inference profiles / project tags with activated cost allocation tags; otherwise it is an estimate.

**Token model** (the cross-check; the result when Cost Explorer is denied or empty; per-caller splits;
what-ifs): price all four token types (`InputTokenCount`, `OutputTokenCount`,
`CacheReadInputTokenCount`, `CacheWriteInputTokenCount`) at their own rates and state the tier and
routing (default Standard, source region).
- **Rates**, in order: the user (say so); `pricing:GetProducts` (us-east-1, one call per model; it does
  not use up `verify_aws_claim`'s single read) with service code `AmazonBedrockFoundationModels` for
  Claude and other third-party models, filters `regionCode` and `model` = the Pricing name (`Claude
  Sonnet 5`, `Claude Haiku 4.5`), and `AmazonBedrock` for Amazon models (an empty `AmazonBedrock`
  result for Claude does not mean unpriced); or the [pricing page](https://aws.amazon.com/bedrock/pricing/)
  read with `verify_aws_claim`. Match exact model, version, region, on-demand rate and unit
  (cost-analysis §1b). Denied: "unpriced: pricing:GetProducts denied".
- **Never** a rate from memory, a launch post or "the same price as the previous generation"; never
  back-derive a rate from the bill, or apply a bill-derived rate to $0-billed tokens or other days.
  No citable price: "cross-check not computed" and why.
- **What-if:** label it a what-if, not billed spend; a model switch needs a quality evaluation first
  (LLM-COST-004). Future volume goes to the AWS Pricing Calculator.

**Pasted figures: re-read only billing days with a gap.** Run the re-read yourself in the connected
account (Cost Explorer endpoint `us-east-1`); don't ask for an account or Region first. A failed call:
"not re-read: <error>", then label that day from the pasted figures.
- **Today** (the current UTC day): no re-read; "not billed yet".
- **An earlier day with a gap** (fewer billed than metered tokens, or no line): re-read only those
  days on both sides, one `ce:GetCostAndUsage` (`DAILY`, by `SERVICE` and `USAGE_TYPE`) and one
  `cloudwatch:GetMetricData` (the user's metric and `ModelId`, `Sum`, `Period` 86400). A pull made
  during a day is partial on both sides. If the re-read matches, stop: no metric listing, no scan of
  other usage types or services. Look further only if a gap remains (cost-analysis §1b).
- **Matching days, and pasted CloudWatch series and quotas on other days:** use as given, unless a
  value the answer needs is missing (e.g. `Maximum` where `Sum` is needed) or the user asks for
  current data.

Say which figures you re-read and which came from the user.

**Token reconciliation** needs no price, so it always runs: per UTC day, over the union of models with
tokens or a billed line, compare CloudWatch tokens with billed `UsageQuantity` (often in thousands)
and name the service of each usage type.
- Tokens with no billed line: "metered, not billed — unexplained". A billed line with no tokens:
  "billed, not metered". Never drop either.
- Fewer billed than metered, labelled only from figures read now: today "not billed yet"; yesterday
  "partly billed" (both counts, kept out of the divergence, billed total not complete yet); 2 or
  more days old "metered above billed — unexplained" (check cost-analysis §1b causes first). A
  re-read that matches is reported as matching.
- Quantity billed at $0.00: give the days, quantities and "billed at $0 — reason not visible from
  these reads", and stop. Only a `RECORD_TYPE` line you read is a cause: no hypothesis, no "most
  likely". Point to the billing console or AWS Billing support; never re-price these tokens as owed.
- Never name a cause you haven't checked (e.g. "traffic outside the window"): compare dates first.

**Divergence:** compare modelled and billed per model and in total. Beyond a few percent, report it and
itemise what the token model doesn't cover (PT model-unit hours, tier or routing suffixes, non-token
features).

## Router

How to read each API and metric: [collection-reference.md](references/collection-reference.md) (load
it with any row). If one read would answer the question, make it before answering; don't end by
offering to pull it. The exception is the full quota sweep: ask for the code instead (Step 6).

**Sub-agents** don't see this skill. When you hand work to one, put in its task the rules its answer
must follow: `(billed)` / `(estimated)` labels, the Cost Explorer service names read, where each
price came from, `LLM-XXX-NNN (SEVERITY)` check-ids, no 12-digit numbers. Check its answer against
"Rules for every answer" before you reply, and fix what doesn't hold.

| Operator says | First read | Load |
|---|---|---|
| Why is my bill so high, spend by model | One `ce:GetCostAndUsage` over the window by `SERVICE` and `USAGE_TYPE` (per-model lines and service names in one read; add `PRODUCT_ATTRIBUTE` `model` only if a usage type doesn't name the model), then `InputTokenCount`/`OutputTokenCount` by `ModelId` once for the cross-check | cost-analysis.md (LLM-COST-001) |
| Is my PT idle | `GetProvisionedModelThroughput` `modelUnits` vs token throughput | cost-analysis.md (LLM-PT-001) |
| Move to batch inference? | `Invocations` and the job's latency tolerance | cost-analysis.md (LLM-COST-003) |
| Is a cheaper model enough? | `InvokeModel`/`Converse` `ModelId` vs task complexity and volume | cost-analysis.md (LLM-COST-004) |
| Runaway output, unbounded `maxTokens`? | `OutputTokenCount` (Sum) distribution per `ModelId` | cost-analysis.md (LLM-COST-001) |
| Same prompt prefix every call, is caching paying off? | `InputTokenCount` vs cache reads and writes | cost-analysis.md (LLM-COST-002) |
| Am I paying for cross-region inference? | Profile id prefix and source-region billing | cost-analysis.md (LLM-COST-005) |
| Throttled, enough quota? | `InvocationThrottles` (Sum), `EstimatedTPMQuotaUsage` (Sum, 60 s) vs the quota from `GetServiceQuota` | checks-model-invocation.md (LLM-INV-007, LLM-INV-002) |
| What is our limit, how do I find it? | Throttle data and peak now; code from quota-codes.md or the user, then `GetServiceQuota`; else ask for it (Step 6) | quota-codes.md, api-quirks.md §18 |
| Invocation logs growing forever | Log destination and its retention policy | metrics-and-logs.md (LLM-COST-006) |
| Alarms on token spend or quota | Recommended token, quota and throttle alarms | cloudwatch-alarm-reference.md |

## Procedure — Capacity & Cost Review

Run the steps in order. Each step is bounded: a denied API, no datapoints or an unsupported region is recorded as `unavailable` /
`not checked` and the review goes on. A partial review with disclosed gaps is a correct result.

- [ ] Step 1: **Scope:** region(s), window, models and profiles; state the defaults chosen (current
  region, trailing window).
  - **Window:** Cost Explorer `End` and CloudWatch `EndTime` are exclusive: [`Start`, `End`) at 00:00
    UTC; to include day D set `End` = D + 1. Compute dates from today's UTC date, never hardcode.
    Default `End` = today, so yesterday is the last day: mark it possibly incomplete, never drop it
    (api-quirks §22).
  - **Regions** are where requests are sent from. Cost Explorer is account-wide (read once, group by
    `REGION`); metrics, quotas, logging and PT are per region: run Steps 2, 2b, 5 and 6 in each.
    Profile traffic is recorded only in the source region (api-quirks §14).
  - **User-supplied evidence** is analysed as given. If live data differs, show both and say which
    each finding rests on.
- [ ] Step 2: **Tokens:** `InputTokenCount` and `OutputTokenCount` (Sum) from `AWS/Bedrock` by
  `ModelId`, same window as the cost data, 1-day period, days added (metrics-and-logs.md). Add every
  form of a model (short ID, profile ARN, model ARN). Billed spend with no tokens in the region: check
  another source region (the line's `REGION` or usage-type prefix such as `USE1-`), the bedrock-mantle
  endpoint (`AWS/BedrockMantle` `TotalInputTokens`/`TotalOutputTokens` by `Model`, api-quirks §20),
  Batch (`AWS/Bedrock/Batch`) and PT (provisioned-model ARN). Name a cause only when a read shows it;
  otherwise "billed, not metered" and what you checked.
- [ ] Step 2b: **Confirming signals** for LLM-COST-001/002: cache read and write tokens (Sum, by
  `ModelId`); if a Bedrock invocation log group exists, the Logs Insights queries in
  metrics-and-logs.md (`stopReason`, `outputTokenCount` outliers, cache fields), even when
  `storedBytes` reads 0 (it lags), checking each field path with `ispresent()` first.
  - Same window as the cost data. Logs start at the group's `creationTime`: disclose shorter
    coverage, never shorten the window (api-quirks §19). `StartQuery` takes epoch seconds: compute
    them with a tool.
  - LLM-COST-001 needs a heavy output tail of records stopped by `max_tokens` (long `tool_use` /
    `end_turn` outputs or a low uniform cap don't count). LLM-COST-002 needs cache reads measured 0
    plus a repeated prefix or a high input floor (10th percentile, not the average). Otherwise
    `INFO (unconfirmed)`, with the missing signal disclosed (cost-analysis §1).
  - Counts and averages from one source and one window; never divide CloudWatch totals by log counts.
- [ ] Step 3: **Cost model** per "Billed vs estimated cost": billed per model, the four-token
  cross-check, daily reconciliation, divergence. Cost Explorer denied or empty: the token model is
  the result, `(estimated)`, with the missing billed cross-check disclosed.
- [ ] Step 3b: **Coverage check** (understating spend is the worst error). Pull daily billed cost and
  token Sums per model (all `ModelId` forms and `AWS/BedrockMantle`) up to today. If the first or
  last day, yesterday or today has cost or tokens, extend `End` and recompute, or report that day
  separately; if more than a few percent falls outside the window, report it and widen the window.
  Until this passes write "within the window `<start>` → `<end>` (exclusive)"; if it can't run, say
  the figure may understate spend, and why.
- [ ] Step 4: **COST checks** LLM-COST-001 to 006 (002 for every model with cache writes); decide
  003/004 from the invocation pattern and the stated workload, at catalog severity.
- [ ] Step 5: **Provisioned Throughput and reserved capacity** (cost-analysis §2): `modelUnits` vs
  observed throughput, and billed `…-reserved-…-tokens-per-minute` lines vs observed tokens per
  minute. Neither: "no Provisioned Throughput or reserved capacity in `<region>`", LLM-PT-001/003 not
  applicable, LLM-PT-002 still runs. PT can't be resized in place (`UpdateProvisionedModelThroughput`
  changes only the name or model): give the LLM-PT-001 remediation, never an update command.
- [ ] Step 6: **Headroom and throttling** (api-quirks §17–18).
  - **Pressure:** `InvocationThrottles` and `InvocationClientErrors` (Sum), per `ModelId` and with no
    dimension, per day. Count `ServiceQuotaExceededException` where invocation logs record it, else
    say client errors could not be split. LLM-INV-007 and LLM-PT-002 need throttles > 0 or confirmed
    quota rejections. Mantle rejections (HTTP 429) are not observable.
  - **LLM-INV-002:** a `ModelId` that `GetInferenceProfile` rejects is a direct call; raise only if
    `ListInferenceProfiles` has a profile for that model.
  - **Peak:** `EstimatedTPMQuotaUsage` (Sum, 60 s) over the trailing 15 days in one query per
    `ModelId`, max datapoint, never a single suspected day; forms sharing a quota are added minute by
    minute. If empty, re-check a day with traffic before "no datapoints". State statistic, period and
    window; the metric is an approximation. Give each peak its own timestamp: the token peak and the
    request peak can fall on different days.
  - **When to read the quota:** only if the user asks for the limit, headroom, an increase size or a
    percent-of-quota alarm, or throttles or quota rejections are above 0. Otherwise skip it and say
    "headroom not computed: no throttles in the window and the limit wasn't asked for".
  - **Quota, read live** (api-quirks §18): headroom = peak ÷ the applied TPM quota. Resolve the model
    and pick the form from how it is called. Take the code from the user, from earlier in this review,
    or from [quota-codes.md](references/quota-codes.md) (read it first): one `GetServiceQuota`, returned
    name checked. Never a remembered or guessed code.
    Without one, don't sweep: `ListServiceQuotas` can't filter by name (54 pages, 10+ minutes in
    testing). Answer with the throttle data and the peak, then ask for the code: name the exact quota
    (e.g. "Cross-region model inference tokens per minute for Anthropic Claude Sonnet 5") and give the
    console path (Service Quotas → Amazon Bedrock, search that name) and the CLI command (§18 step 3).
    If the user mentions an earlier increase request, `list_requested_service_quota_change_history`
    (`ServiceCode=bedrock`) returns its code. Sweep only when the user asks for it (§18 step 3).
  - **Report** the rows read as a table: | Quota name | Code | Applied value | Adjustable |, one row
    per quota (`GetServiceQuota` or sweep). "Not computed" needs a named reason (code not given yet; rows in
    other forms only: name them; no TPM row: name the closest rows), then the raw peak. Pressure with
    high TPM headroom: check the RPM and daily quotas before naming a cause.
- [ ] Step 7: **Alarms** from [cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md),
  with each threshold's source (AWS-published / Derived / Workload-specific).
- [ ] Step 8: Assemble the findings, then run "Before You Present".

## Check Families

Detection rules, remediations, citations: [cost-analysis.md](references/cost-analysis.md) (PT, COST),
[checks-model-invocation.md](references/checks-model-invocation.md) (INV). Families of other skills in
those files (GRD, KB, AGT, SM, EVAL, AC, TEL, other INV) are never raised here.

| check-id | Detects | Severity |
|---|---|---|
| LLM-PT-001 | PT `InService` with sustained low use: no datapoints on most days, or throughput far below a known per-unit capacity (cost-analysis §2) | HIGH |
| LLM-PT-002 | On-demand load sustained near its throttle ceiling, no PT: a steady baseline cheaper or more reliable on PT | MEDIUM |
| LLM-PT-003 | PT on a model version nearing or past end of life | MEDIUM |
| LLM-COST-001 | A few invocations drive a large share of `OutputTokenCount`: unbounded `maxTokens`, spend drift | MEDIUM |
| LLM-COST-002 | Repeated prefixes with no prompt caching, or cache writes far above reads | MEDIUM |
| LLM-COST-003 | Large latency-tolerant jobs on-demand instead of Batch | MEDIUM |
| LLM-COST-004 | A high-cost model on simple high-volume tasks (validate a smaller one first) | MEDIUM |
| LLM-COST-005 | Cross-region profile with its billed rate and data transfer unconfirmed (geographic: source-region rate; `global.`: a usage type containing `global`, own rate) | INFO |
| LLM-COST-006 | Invocation-log destination with no retention or lifecycle policy. Give `aws logs put-retention-policy --log-group-name <log-group> --retention-in-days <N>` (N workload-specific); data-delivery flags are configuration, out of scope here | MEDIUM |
| LLM-INV-002 | Direct model ID while a cross-region profile exists for that model (none: don't raise) | HIGH |
| LLM-INV-007 | Sustained throttles or quota rejections (> 0) with no backoff retry and no profile spreading | MEDIUM |

## Before You Present — Validate Your Own Output

A confidently wrong cost number is worse than a slow one. If an item can't be met, say so.

- [ ] Every top rule and "Guardrails — details" holds; no 12-digit number.
- [ ] Every dollar figure says `(billed)` or `(estimated)`, every finding `LLM-XXX-NNN (SEVERITY)`,
  billed spend names its Cost Explorer service names.
- [ ] Window stated with an exclusive `End`; Step 3b passed, or the figure is marked a possible
  understatement.
- [ ] No single SERVICE filter; the token model priced all four token types with tier and routing.
- [ ] Modelled vs billed per model and in total, or "not computed" and why; divergence itemised;
  partly billed days marked; each total equals the sum of its lines.
- [ ] Headroom = `EstimatedTPMQuotaUsage` ÷ the TPM quota, code and name cited, quota rejections
  counted as pressure; every "not computed" has its reason; no code, no sweep: the code asked for.
- [ ] No cause and no "should have cost" figure for a $0 or gap day without a `RECORD_TYPE` line.
- [ ] Each check-id matches what was observed; a PT finding separates `InService` from in use.
- [ ] A full report follows [capacity-cost-report-template.md](assets/capacity-cost-report-template.md).

## Guardrails — details

- **IDs and secrets (rule 2):** includes "I checked account …" lines (use the alias or "the account
  under review"); keys, tokens, connection strings and env vars by key name only.
- **Estimates (rules 3–4):** compare with the billed figure where one exists.
- **Findings (rule 5):** cite the observed value that triggered it; one severity, the same in heading
  and body; don't raise one whose remediation would say "this may not apply"; no freelance findings.
  Coverage and attribution notes are disclosures, not findings.
- **Hypotheses (rule 6):** name the read or AWS page that would confirm it; never contradict the
  references; billing anomalies get none. Quote AWS docs only from a page read in this review, cited.
- **Thresholds:** only from catalog rows; a `workload-specific` one is named as such and never
  changes the severity.
- **Skips (rule 8):** give the reason for each (budget, permissions, unsupported feature).

## Common wrong answers

Covered by the rules above: `InService` is not in use, per-model spend grouped by `model` is billed, no datapoints is not zero,
missing log retention is LLM-COST-006, Cost Explorer denied means the token model is `(estimated)`.
Also:

- **"A `us.` profile bills as us-east-1."** It is a geographic routing scope; billing follows the
  source region (api-quirks §14, LLM-COST-005).
- **"The PT's model is `ACTIVE`, so it's safe."** Models stay `ACTIVE` until end of life: check the EOL
  announcement (api-quirks §4, LLM-PT-003).
- **"`EstimatedTPMQuotaUsage` is at or below the tokens sent, so no burndown."** Quota use is `Sum` at
  60 s; `Maximum` is one request. Output weight = (`EstimatedTPMQuotaUsage` − `InputTokenCount` −
  `CacheWriteInputTokenCount`) ÷ `OutputTokenCount`, all `Sum` over one window (cache reads count 0;
  10.0x for Claude Sonnet 5 in testing). Pasted `Sum` values: compute it. Another statistic: re-read
  once, one `GetMetricData` with the four metrics, `Sum`, `Period` 86400 (daily Sums give the same
  totals); no cache-write datapoints = 0. Report only the weight measured (other models: cost-analysis
  §Quota link) and say burndown counts against the TPM quota, not the bill.
- **"A `us.` profile uses the on-demand quota."** Geographic profiles use `Cross-region model inference
  tokens per minute for <model>`, `global.` uses `Global cross-region …`, direct calls `On-demand …`
  (api-quirks §18 step 4). "No matching quota" or "no tokens-per-day quota for <model>" only after a
  full list; otherwise "quota not read" / "tokens-per-day quota not read for <model>".

## Severity

CRITICAL (active impact or large waste, 24–48 h) · HIGH (serious risk, 1 week) · MEDIUM (gap vs best
practice, 30 days) · LOW (hardening) · INFO (catalog row is INFO, or the confirming signal was
unavailable: `unconfirmed`). Response times are derived guidance, not AWS commitments.

## Error Handling

Check [api-quirks.md](references/api-quirks.md) before interpreting a response, in particular §4
(ACTIVE now, deprecated soon), §10 (no datapoints ≠ 0), §12 (`InService` ≠ in use), §14 (cross-region
pricing), §16 (single SERVICE filter undercounts), §17–18 (quota pressure, `EstimatedTPMQuotaUsage`,
free-text quota names), §19 (`storedBytes` lags), §22 (exclusive `End`).

- **AccessDenied** (e.g. `ce:GetCostAndUsage`, `pricing:GetProducts`, `servicequotas:ListServiceQuotas`,
  `GetProvisionedModelThroughput`): report the API and resource, continue, list the gap; never guess.
- **`DataUnavailableException`** on a product-attribute query: the window starts before that data
  exists. Read the date from the error, fall back to `USAGE_TYPE` grouping and say so.
- **Unsupported region:** a disclosed assumption, not a finding. **Throttled list calls:** back off
  and paginate. **Ambiguous scope:** ask, or use the current region and say so.

## Related skills (optional)

This skill works on its own and loads nothing outside its own `references/` and `assets/`. When a question
reaches into an area listed under *When NOT to Use*, read `references/related-skills.md` and:

1. If the skill named there is in your available skills, load it and use it for that part.
2. If it isn't, cover that part yourself with the fallback check in that file and general AWS knowledge.
   Label anything that comes from general knowledge, and give it no check-id: this skill's check-ids are
   only for checks this skill runs.
3. End the answer with one line recommending the missing skill and what it would add. Add it only when
   that skill would have changed the answer, and only once.

## References

Load when the step says so: [cost-analysis.md](references/cost-analysis.md) (Steps 3–5, before any LLM-COST or LLM-PT
finding); [checks-model-invocation.md](references/checks-model-invocation.md) (before LLM-INV-002/007);
[metrics-and-logs.md](references/metrics-and-logs.md) (Steps 2, 2b);
[cloudwatch-alarm-reference.md](references/cloudwatch-alarm-reference.md) (Step 7);
[collection-reference.md](references/collection-reference.md) (which API per signal);
[api-quirks.md](references/api-quirks.md) (before interpreting a response; quota lookup §18, Step 6);
[quota-codes.md](references/quota-codes.md) (quota-code shortcuts for `GetServiceQuota`, verified live; Step 6);
[capacity-cost-report-template.md](assets/capacity-cost-report-template.md) (only for a full report).
