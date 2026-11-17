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
- **Correct reading:** `ACTIVE` is necessary but not sufficient. Cross-check the Bedrock model card or Model lifecycle page for a scheduled EOL date (provider dates differ and do not apply; never estimate one); a model with an imminent EOL still warrants LLM-INV-003 planning. An EOL model is gone from `ListFoundationModels` and `GetFoundationModel` returns `ResourceNotFoundException` ("reached the end of its life") — that error is the finding, not a collection gap.

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
- **Correct reading:** The prefix (`us.`, `eu.`, `apac.`, `jp.`, `au.`, `ca.`, and others, plus `global.` for global cross-Region inference) denotes the **routing scope**, and requests may be served from any member region in that scope; don't assume single-region behavior (LLM-INV-002, LLM-COST-005). An inference-profile ARN is also a profile; a `foundation-model/` ARN is a bare-model call. Metrics for profile traffic are published in the source region.

## 15. `GetFoundationModelAvailability` `AVAILABLE` ≠ the model can be invoked

- **Trap:** `agreementAvailability.status: AVAILABLE` read as "access is fine, so an AccessDenied must be IAM."
- **Correct reading:** The agreement can stay `AVAILABLE` for a model that has reached end-of-life (observed for `anthropic.claude-3-opus-20240229-v1:0`). Check `GetFoundationModel` lifecycle first (LLM-INV-003), then availability (LLM-INV-014).

## 16. Invocation logs have no error field

- **Trap:** "No `errorCode` in the invocation logs → no failed calls" or "→ all invocations succeeded."
- **Correct reading:** The documented log record has no `errorCode` field, and 0 of 2,745 records carried one in testing. Absence proves nothing. Count errors from `InvocationClientErrors` / `InvocationServerErrors` / `InvocationThrottles` (queried with and without `ModelId`), and say they cannot be classified further from logs.

## 17. `InvocationClientErrors` mixes quota rejections with other client errors

- **Trap:** `InvocationThrottles` with no datapoints read as "no capacity pressure", or `InvocationClientErrors` > 0 read as "access problem".
- **Correct reading:** Requests rejected for exceeding a service quota are counted in `InvocationClientErrors`, not `InvocationThrottles`, alongside validation and access errors. Unsplit client errors raise neither LLM-INV-007 nor an access finding; report them as unclassified. The part published only without `ModelId` (failed before model resolution) is not an access signature either: invalid model identifiers fail there too (a `Converse` `ValidationException` "The provided model identifier is invalid" was the only failed call on record in testing). Source: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

