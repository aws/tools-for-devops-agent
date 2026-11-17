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
- **Correct reading:** `ACTIVE` is necessary but not sufficient. Cross-check against AWS model lifecycle announcements for a scheduled EOL date; a model with an imminent EOL still warrants LLM-INV-003 planning.

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
- **Correct reading:** The `us.`/`eu.`/`apac.` prefix denotes the **geographic routing scope**, and requests may be served from any member region in that scope. Billing follows the source region; don't assume single-region behavior (LLM-INV-002, LLM-COST-005).

## 15. Invocation log shows no errors ≠ there were no errors (pre-flight rejects)

- **Trap:** `filter ispresent(errorCode) -> 0 records` over the invocation log reads as "no API errors in the window", and the answer goes out as a total claim.
- **Correct reading:** A request rejected **before** model resolution — an unresolvable or malformed model id, a caller without `bedrock:InvokeModel` — never produces an invocation-log record and carries **no `ModelId` dimension**. `InvocationClientErrors` counts it; the log does not; the per-model breakdown does not. So a 0-record log scan is a fact about the log, and the metric total minus the sum of logged codes is a real population of errors nobody has attributed yet.
- **How to attribute it:** `cloudtrail:LookupEvents` with `AttributeKey=EventSource`, `AttributeValue=bedrock.amazonaws.com` returns the `Converse`/`InvokeModel` events with their `errorCode` and `userIdentity.arn`. `AttributeKey=EventName, AttributeValue=InvokeModel` returns **nothing** — those are data events and the selector is off by default.
- **Measured 2026-10-26:** account `InvocationClientErrors` 476/24h; invocation log 30 `ValidationException`; per-`ModelId` metric 30. The 446-error remainder was invisible to both the log and the model dimension, and CloudTrail resolved it to `ValidationException` plus `AccessDenied` across two execution roles. An agent that inferred `ResourceNotFoundException` for that remainder reported a 403 as a 404 (LLM-INV-004 mistaken for LLM-INV-003).
