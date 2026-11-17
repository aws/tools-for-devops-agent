# API Quirks

Bedrock / SageMaker read-only API responses whose obvious reading is **wrong** or misleading. Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs).

---

## 1. `GetModelInvocationLoggingConfiguration` — empty vs disabled

- **Trap:** When logging has never been configured, the API returns a response with **no `loggingConfig`** (effectively empty), not an explicit `enabled: false`. An agent that only checks for a falsy "enabled" flag may skip the check.
- **Correct reading:** Absence of `loggingConfig` **means logging is disabled** → raise LLM-INV-001 (CRITICAL). Logging is enabled only if `loggingConfig` is present with at least one of `cloudWatchConfig` / `s3Config`. Also: `loggingConfig` can be present while the specific data-delivery flags (`textDataDeliveryEnabled`, etc.) are false — "configured" ≠ "capturing content".

## 2. `ListEvaluationJobs` — empty in unsupported regions

- **Trap:** An empty list reads as "no evaluation jobs → raise LLM-EVAL-001 CRITICAL." But Bedrock evaluation is **not available in every region**. In an unsupported region the API may return empty (or error) regardless of maturity.
- **Correct reading:** Before firing LLM-EVAL-001, confirm the region supports Bedrock evaluation. If unsupported, the finding is "evaluation not available in this region; verify workloads run where evaluation is supported" (INFO/advisory), not CRITICAL. Only raise CRITICAL when evaluation is supported **and** the list is empty.

## 3. Model access / `ListFoundationModels` — listed ≠ accessible

- **Trap:** `ListFoundationModels` returns models that exist in the region. Presence in the list does **not** mean the account has been granted access to invoke them.
- **Correct reading:** A model can appear in `ListFoundationModels` yet `InvokeModel` fails with `AccessDeniedException` because access was never requested/granted. Use model access status (and actual invocation errors in logs) to judge access, not list membership.

## 4. `modelLifecycle.status` — ACTIVE now, deprecated soon

- **Trap:** `status: ACTIVE` reads as "fine, no action." Deprecation is announced ahead of the end-of-life date; a model is `ACTIVE` right up until it legacies.
- **Correct reading:** `ACTIVE` is necessary but not sufficient. `modelLifecycle` carries `legacyTime` / `endOfLifeTime` only once a model is LEGACY; for an ACTIVE model, cross-check AWS model lifecycle announcements for a scheduled EOL date; a model with an imminent EOL still warrants LLM-INV-003 planning.

## 5. Guardrail `DRAFT` — exists but not what's enforced

- **Trap:** `GetGuardrail` on the DRAFT returns a fully populated policy, reading as "guardrail is configured and strong."
- **Correct reading:** DRAFT is editable and may differ from the **published version** the application actually references. Evaluate the specific `guardrailVersion` used at invoke time. A strong DRAFT with production pointing at an older/weaker version is still a finding (LLM-GRD-006).

## 6. Agent `PREPARED` status vs alias in use

- **Trap:** `GetAgent` showing `agentStatus: PREPARED` reads as "the latest config is live."
- **Correct reading:** Applications invoke an **alias**, which maps to a specific version — not necessarily the latest prepared DRAFT. A newly prepared DRAFT does not change production until an alias is pointed at a new published version (LLM-AGT-007). Always resolve alias → version.

## 7. SageMaker endpoint `InService` with `CurrentInstanceCount` = 0

- **Trap:** `DescribeEndpoint` `EndpointStatus: InService` reads as healthy and serving.
- **Correct reading:** A variant can be `InService` yet report `CurrentInstanceCount: 0` (scaled in, scale-to-zero async/serverless, or a misconfigured leftover). `InService` is control-plane state, not proof of serving capacity → check instance count and recent `Invocations` (LLM-SM-003).

## 8. Knowledge Base exists ≠ data ingested

- **Trap:** `GetKnowledgeBase` returning `status: ACTIVE` reads as "KB is ready and populated."
- **Correct reading:** KB `ACTIVE` only means the resource/vector-index wiring is valid. If no `StartIngestionJob` has completed (`ListIngestionJobs` empty), the vector store is empty and retrieval returns nothing (LLM-KB-001). Always verify ingestion-job history, not KB status.

## 9. `DescribeScalableTargets` empty ≠ no scaling intended

- **Trap:** An empty scalable-targets response reads as "auto-scaling is simply off, low severity."
- **Correct reading:** For a production endpoint, empty means **fixed capacity** — it cannot absorb spikes or scale in to save cost (LLM-SM-001, HIGH). Confirm it's registered under `application-autoscaling` with namespace `sagemaker`, resource id `endpoint/<name>/variant/<variant>`; a wrong resource-id lookup also returns empty and can be mistaken for "no scaling."

## 10. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource (LLM-AGT-004 / LLM-SM-003). Distinguish "zero measured" from "nothing reported."

## 11. Guardrail `InvocationsIntervened` high ≠ guardrail broken

- **Trap:** A spike in `InvocationsIntervened` reads as a misconfigured/overly-aggressive guardrail to loosen.
- **Correct reading:** A spike is often the guardrail **working** against an attack campaign or a prompt/model regression. Investigate the cause (attack vs false-positive) before weakening the guardrail.

## 12. Provisioned Throughput `InService` ≠ in use

- **Trap:** PT `status: InService` reads as "actively serving, keep it."
- **Correct reading:** `InService` means the capacity is provisioned and **billing**, independent of whether anything invokes it. Correlate with actual token throughput to detect idle PT (LLM-PT-001).

## 13. `GetDataSource` chunking default

- **Trap:** A missing/absent chunking configuration reads as "default is fine."
- **Correct reading:** The default behavior depends on the data-source/API version and may be "no chunking" (whole-document) — poor for long heterogeneous docs. Treat an unset strategy as a tuning gap to confirm (LLM-KB-003), not a safe default.

## 14. Cross-region inference profile IDs look region-prefixed but aren't a region override

- **Trap:** A profile id like `us.anthropic.claude-...` reads as "pinned to us-east-1 only."
- **Correct reading:** The prefix (`us.`, `eu.`, `apac.`, `jp.`, `au.`, `ca.`, `in.`, `global.` in testing; AWS adds more) denotes the **routing scope**, and requests may be served from any member region in that scope; don't assume single-region behavior (LLM-INV-002, LLM-COST-005). Don't tell profiles from model IDs by prefix: `GetInferenceProfile` accepts any profile ID and rejects a model ID. **Metrics follow the source region:** `AWS/Bedrock` metrics for profile traffic are published in the region the request was sent from, not the member region that served it, so a member region can show no metrics while serving traffic (in testing, `us.` traffic sent from us-east-1 left us-east-2 and us-west-2 empty). Pull metrics in the source region. Geographic profiles (every prefix except `global.`) bill at the source-region rate. `global.` profiles bill under their own usage type and unit price. Spellings vary (`-cross-region-global`, `_global_standard`, …): match any usage type containing `global`, in any case, rather than a list. The global rate can be lower or higher than the in-region rate (in testing, lower for Claude Sonnet 5), so do not assume either direction. Quote a price difference only with a citation to the billed usage-type line or the Bedrock pricing page, and do not assert that there is no data-transfer charge — say it must be confirmed (LLM-COST-005, INFO).

## 15. Cache token metrics — measured zero vs no datapoints

- **Trap:** `CacheReadInputTokenCount` returning no datapoints is read as "0 cache hits → prompt caching is off → LLM-COST-002."
- **Correct reading:** AWS documents that the cache metrics are **0 when prompt caching is not used** — so a *measured* 0 alongside high, stable `InputTokenCount` is a legitimate LLM-COST-002 signal. *No datapoints* is different: the metric was not emitted in the window, most often because the model does not support prompt caching or had no traffic. Report it as `no datapoints`, confirm model support, and do not raise LLM-COST-002 on it (§10 applies).

## 16. Cost Explorer `SERVICE = "Amazon Bedrock"` — undercounts Bedrock spend

- **Trap:** Filtering `ce:GetCostAndUsage` to the single service name `Amazon Bedrock` reads as "all Bedrock spend."
- **Correct reading:** AWS documents that the costs of a supported service can appear under **multiple service names**. A single-name SERVICE filter can miss part of the bill, and the token model will then look like it overshoots. Omit the SERVICE filter when filtering by product attributes, or list the names first with `ce:GetDimensionValues` (`Dimension = SERVICE`, `SearchString = Bedrock`) and include all of them. Also: product-attribute keys (`model`, `provider`, `inferenceType`, `feature`) are case-sensitive and a misspelled key returns **no error**, it just matches nothing — a mis-cased key (`Model` instead of `model`) returns the whole total in one unnamed bucket (`Model$`), so the tell is missing named groups, not a $0 figure. In testing, one account split Bedrock spend across `Amazon Bedrock` and `Amazon Bedrock Service`. Use `GroupBy Type=PRODUCT_ATTRIBUTE,Key=model`; `Type=DIMENSION` is rejected. Source: https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_ProductAttributeValues.html

## 17. Quota pressure hides in `InvocationClientErrors` and in series with no `ModelId`

- **Trap:** `InvocationThrottles` = 0 per `ModelId` reads as "no capacity pressure → no LLM-INV-007 / LLM-PT-002."
- **Correct reading:** Two documented behaviors make the per-model throttle series undercount. (1) Requests **rejected for exceeding a service quota** are counted in `InvocationClientErrors`, **not** in `InvocationThrottles`. (2) Requests that fail **before Bedrock determines the target model** are published **without** the `ModelId` dimension. Query `InvocationThrottles` and `InvocationClientErrors` both per `ModelId` and with no dimension, and, if invocation logs record rejected requests, split client errors by `errorCode` (`ServiceQuotaExceededException` vs `ValidationException` / `AccessDeniedException`); otherwise report that client errors could not be split: unsplit client errors alone never raise LLM-INV-007 or LLM-PT-002. Also, `Invocations` excludes throttled requests, so the throttle rate is throttles ÷ (`Invocations` + throttles). Source: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

## 18. `EstimatedTPMQuotaUsage` — an absolute estimate, not a percentage

- **Trap:** Reading the quota metric as "% of quota used" and alarming at `> 80`.
- **Correct reading:** `EstimatedTPMQuotaUsage` is a **Count** of estimated tokens-per-minute quota use, not a percentage. There is no `EstimatedQuotaConsumption` metric; that name returns no datapoints.
- **Headroom** = peak per-minute value ÷ the model's **applied** TPM quota (not the AWS default), read with `GetServiceQuota` per the lookup procedure below.
- **Approximation:** it ignores the up-front reservation (input tokens + `max_tokens`) that drives throttling, so a large `max_tokens` can throttle a workload whose estimate looks comfortable. Never use it as the only capacity signal.
- **Statistic and period:** the per-minute figure is `Sum` at 60 s. `Maximum` is the largest single request; longer periods add up several minutes. Always state statistic, period and window.
- **API:** pull 60 s data with `GetMetricData`. `GetMetricStatistics` at 60 s fails (`InvalidParameterCombination`) past 1,440 datapoints, about one day.
- **Bursty traffic:** pull `EstimatedTPMQuotaUsage` across the **whole trailing 15-day window in one `GetMetricData` query** (per `ModelId`) and take the max datapoint — a single-day query can miss the true peak (testing: 7,492 tok/min on one day vs 141,008 for the 15-day peak). Only if the full-window query is empty, re-confirm against a day on which `InputTokenCount` shows traffic before reporting "no datapoints". When one model's `ModelId` forms are added minute by minute and never overlap, the sum's peak is simply the larger single peak (Titan in testing: 2 and 1,430 → 1,430).
- **Mantle quotas:** models on the `bedrock-mantle` endpoint have separate `[bedrock-mantle endpoint] Input` / `Output tokens per minute` quotas; a combined count can't be divided by them.
- **Quota list paging:** `ListServiceQuotas` accepts no name or model filter (only `QuotaCode`; other filters are ignored, tested 2026-11-10), so finding a quota without its code means listing every page. The Bedrock list is long (1,121 quotas over 54 pages in testing; pages hold about 21, always well under the requested `MaxResults`). The CLI and an SDK paginator (about 9 to 14 s for the whole list, tested 2026-11-11) (boto3 client `service-quotas`, not `servicequotas`: `get_paginator('list_service_quotas')`) fetch every page in one command. A tool that makes single calls (e.g. `use_aws`) needs one call per page: in testing, 55 `use_aws` calls covered all 54 pages in about 10 minutes, with a `jmespath_filter` of ``{Next: NextToken, Q: Quotas[?contains(QuotaName, `<model>`)].[QuotaName, QuotaCode, Value, Adjustable]}`` so each page returns only the matching rows (name, code, applied value, adjustable) and the token (step 3). `Quotas[].[QuotaName, QuotaCode, Value, Adjustable]` without `contains` returns every row of the page: use it only when the user asks for the whole list; pages still hold about 21 rows, so it is the same 54 calls. Show the rows as a table (SKILL.md Step 6 "Report"). A **full list** is one whose last response has no `NextToken`; only a full list shows that a quota is absent. A partial scan is **not** evidence a quota is absent. List at most once per review and match every model against that one list; never page again for each model. A quota code learned earlier in the same review can be read directly with `GetServiceQuota`, provided the returned name matches the model and form.
- **Bad tokens:** the CLI's `--max-items` token works only with `--starting-token`; passed to `--next-token` it raises `InvalidPaginationTokenException`, as do empty, edited or foreign tokens (e.g. from another service code). A token with characters outside base64 (e.g. hyphens) raises `ValidationException` instead. Pass each token exactly as returned (about 1,300 characters for Bedrock); never trim, retype or edit it. A valid token can be replayed and returns the same page, so after an error re-request the previous page with its token and continue; never restart from page 1. An interrupted list never shows that a quota is absent: the list ends only when a response has no `NextToken`, never on an error. Copying a token by hand is error-prone (two slips in one test run); re-requesting the previous page gives a fresh token. A full scan one page per call takes about 54 calls at `MaxResults=100`. Quota codes are the same in every region where the quota exists (checked in us-east-1, us-west-2, eu-west-1, ap-northeast-1); which quotas exist and their values differ by region.
- **Quota names are free text:** nothing links a quota to a model ID (no TPM quota carries a `UsageMetric`, and the `Description` repeats the name), and names don't follow the model name. They add or drop the provider or a version (`Anthropic Claude Sonnet 4.5 V1`, `DeepSeek V3.2`), spell it differently (`Z.ai GLM-4.7 Flash`, `OpenAI GPT OSS 120B`), use another version label (`Voxtral Mini 1.0`) or carry a typo (`Mixtral 8X7BB Instruct`). In testing, an exact-suffix filter found the quota for 28 of 91 active models. Use the lookup procedure below.
- **Quota lookup procedure** (SKILL.md Step 6). Values and names are always read live from the account, and only when the
  question needs them (SKILL.md Step 6 "When to read the quota"). Listing is slow (one agent turn per page), so without a
  code ask the user for it (step 2b); sweep only when the user asks, once per review for every model in scope.
  1. **Resolve the model.** `GetInferenceProfile` on the `ModelId` returns the profile's foundation model, whatever the prefix (`us.`, `jp.`, `global.` …); an error means a direct call. `GetFoundationModel` gives `providerName` and `modelName`; the version is the `-v<n>` in the model ID.
  2. **A code you already have.** A code the user gives, one found earlier in this review, or one from
     [quota-codes.md](quota-codes.md) for the model and form: read it with
     `GetServiceQuota --service-code bedrock --quota-code <code>`, one call per quota, and check that the returned `QuotaName`
     names the model and form you resolved. Never use a code from memory; codes can change. Otherwise go to step 2b.
  2b. **No code: ask for it.** Give what you measured (throttles, client errors, the peak with its time) and ask the user for
     the code of the exact quota you resolved in steps 1, 4 and 5, named in full. They can find it in the Service Quotas
     console (Amazon Bedrock, search the quota name; the code is on the quota's page) or with the CLI command in step 3, which
     pages automatically and takes seconds. If the user mentions an earlier increase request, one
     `list_requested_service_quota_change_history` call (`ServiceCode=bedrock`) returns that quota's code; the operation has
     no `_by_service` variant. Run the sweep in step 3 only when the user asks for it. Reason: in testing (2026-11-10 and
     11-11), sweeps one page per call took 12 to 22 minutes when they finished, half did not, and one used the whole
     15-minute chat without answering.
  3. **Full sweep (only when the user asks for it).** List `ListServiceQuotas` once per review, every page, with the filter above covering all models in scope;
     the matching rows give the code, name and applied value. If your tool fetches every page in one command (the CLI or an SDK
     paginator), that command is the sweep. If it makes one call per page, continue until a response has no `NextToken`,
     passing each token exactly and never restarting from page 1; a helper that stops passes its last `NextToken` to the
     next one. Match as in step 4. If the sweep can't finish in this review
     (time or errors), report "quota not read: list not exhausted within this review", give the user
     `aws service-quotas list-service-quotas --service-code bedrock --region <region> --query "Quotas[?contains(QuotaName,'<model name>')].[QuotaName,QuotaCode,Value,Adjustable]" --output table`,
     and do not conclude the quota is absent.
  4. **Match by the text after `for`**, ignoring case, punctuation, the provider and words like `Instruct` or `IT` (`Meta Llama 4 Scout V1` is `Llama 4 Scout 17B Instruct`). Every other number and variant word must match, except a size (`17B`) or a date (`2507`) that one side omits: `Claude Sonnet 5.5` is not `Claude Sonnet 5`; `Nova Lite` and `Nova 2 Sonic` are not `Nova 2 Lite`; `Gemma 3 27B` is not `Gemma 3 12B`. A `V<n>` must match the model ID's version (for `-v2`, `… Titan Text Embeddings V2`, not `… Titan Text Embeddings`). `… 1M Context Length` rows are a separate long-context quota. Only if no row matches, a row whose version label stands where the model name has a size or date (`Voxtral Mini 1.0` for `Voxtral Mini 3B 2507`) is the model's row: say "matched by name". Collect every spelling across forms (`Claude Sonnet 5` on mantle rows).
  5. **Pick the form:** direct → `On-demand …`; `global.` profile → `Global cross-region …`; any other profile → `Cross-region …`; bedrock-mantle traffic → `[bedrock-mantle endpoint] …`.
- **No quota of that form:** some models lack a form (in testing, Claude Sonnet 5 had no `On-demand …` TPM quota) and some have no TPM quota at all (Nova 2 Sonic had only a concurrent-requests quota). Only a full list proves a form is missing; a sweep that stopped early proves nothing. A code that returns `NoSuchResourceException` shows only that this code doesn't exist in this region. Write "not computed" with its reason (SKILL.md Step 6). Do not conflate "I stopped scanning" or "no row has this exact name" with "no quota exists".

## 19. `storedBytes: 0` — does not mean the log group is empty

- **Trap:** `DescribeLogGroups` shows `storedBytes: 0` for the invocation log group, read as "no logs → skip the Logs Insights query → COST-001/002 unconfirmed."
- **Correct reading:** `storedBytes` lags and can read 0 for a group that holds records. Always run the Logs Insights query over a recent window before downgrading LLM-COST-001/002 to INFO.
- **Creation time:** records start at the group's `creationTime`. A query that starts earlier still runs; one that ends earlier fails with `MalformedQueryException` ("end date and time is either before the log groups creation time…"). That limits only the log signals: keep the token and cost windows from Step 1 and disclose the shorter log coverage.

## 20. No `AWS/Bedrock` data for a billed model — mantle endpoint, another region, Batch or PT

- **Trap:** Cost Explorer shows spend for a model but `AWS/Bedrock` token metrics return no datapoints, read as "no traffic" or a broken cross-check.
- **Correct reading:** the bedrock-mantle endpoint is one possible cause, not the only one. Another source region, Batch inference (`AWS/Bedrock/Batch`) and Provisioned Throughput also leave `AWS/Bedrock` empty for a billed model: check them before naming a cause (SKILL.md Step 2). Calls through the bedrock-mantle endpoint (OpenAI-compatible, Responses, Chat Completions, Anthropic Messages APIs) publish to `AWS/BedrockMantle` with different names: `Inferences`, `TotalInputTokens`, `TotalOutputTokens`, `InferenceClientErrors`, dimension `Model`. Quota rejections (HTTP 429) appear in **no** metric, so report throttling as not observable. Quotas are the separate `[bedrock-mantle endpoint] Input` / `Output tokens per minute`. There is no cache-token or `EstimatedTPMQuotaUsage` equivalent. Do not infer the endpoint from a `-mantle-` usage-type name: it also appears on bedrock-runtime traffic, and such lines bill at the model's Standard rate (no separate price). In testing, Claude Sonnet 5 billed only `USE1-anthropic.claude-sonnet-5-mantle-input-tokens-standard` / `-output-tokens-standard` lines while `AWS/BedrockMantle` was empty and `AWS/Bedrock` held all its tokens: bedrock-runtime traffic. Source: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-mantle-metrics.html

## 21. Token totals that don't match the bill — period and window both matter

- **Trap:** a CloudWatch token total far above the billed quantity (e.g. 4.26M vs 208K input tokens for one model) trusted as usage, or blamed on one cause without checking both.
- **Correct reading:** check both.
  - **Period:** **never pass a multi-day `Period`.** Pull token Sums at a **1-day period (86,400 s) in UTC days and add the days yourself** (Step 2). Treat any single multi-day bucket as unreliable for reconciliation: it can't be compared day by day with the bill and hides which day differs. Do not assume the period is immaterial.
  - **Window mismatch:** even at a 1-day period, a total above the bill usually comes from a window that differs from the cost window — typically one ending "now" that catches traffic Cost Explorer has not billed yet. In testing, such a gap was the 208,122 billed tokens plus same-day traffic not yet billed. Pull tokens over the **same** window as the cost data and compare day by day (`cost-analysis.md` §1b).
- The 1-day-period daily sum over the cost window is the figure that reconciles with the bill; use it for every cost cross-check.

## 22. Exclusive `End` date — an off-by-one window hides most of the spend

- **Trap:** the window is set to end "yesterday" with `End` = yesterday's date, to allow for Cost Explorer lag. Billed and token figures then agree inside the window, and the result is reported as "exact".
- **Correct reading:** `ce:GetCostAndUsage` `TimePeriod.End` is **exclusive**, and so is CloudWatch `EndTime`. `End` = yesterday leaves out yesterday, and today is left out too. Both sources leave out the same days, so they still agree with each other. For a model whose traffic is recent (newly adopted, bursty, or launched this week), most of its spend can sit in the days that were left out. A matching cross-check proves only that the two sources agree, not that the window covers the spend.
- **Do:** compute dates from today's UTC date at run time. Set `End` = today (UTC) so yesterday is included, and mark yesterday as possibly incomplete. Then run the coverage check (SKILL.md Step 3b): pull daily billed cost and daily tokens per model up to now. If billed cost or tokens fall outside the window, extend the window or report those days separately. Never call a figure "exact" or "complete" until that check passes. Source: https://docs.aws.amazon.com/aws-cost-management/latest/APIReference/API_DateInterval.html
