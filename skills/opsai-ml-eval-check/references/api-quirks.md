# API Quirks

Bedrock / SageMaker read-only API responses whose obvious reading is **wrong** or misleading (traps §1–§15). Each entry: the trap, why it misleads, and the correct interpretation. Misreading these produces false positives (phantom findings) or false negatives (missed CRITICALs). Traps outside the evaluation catalog keep their knowledge for the fallback but carry no check-id here; they name the owning area instead.

---

## 1. `GetModelInvocationLoggingConfiguration` — empty vs disabled

- **Trap:** When logging has never been configured, the API returns a response with **no `loggingConfig`** (effectively empty), not an explicit `enabled: false`. An agent that only checks for a falsy "enabled" flag may skip the check.
- **Correct reading:** Absence of `loggingConfig` **means logging is disabled** → an invocation-logging gap (Bedrock invocation-logging area). Logging is enabled only if `loggingConfig` is present with at least one of `cloudWatchConfig` / `s3Config`. Also: `loggingConfig` can be present while the specific data-delivery flags (`textDataDeliveryEnabled`, etc.) are false — "configured" ≠ "capturing content".

## 2. `ListEvaluationJobs` — empty in unsupported regions

- **Trap:** An empty list reads as "no evaluation jobs → raise LLM-EVAL-001 CRITICAL." But Bedrock evaluation is **not available in every region**. In an unsupported region the API may return empty (or error) regardless of maturity.
- **Correct reading:** Before firing LLM-EVAL-001, confirm the region supports Bedrock evaluation. If unsupported, the finding is "evaluation not available in this region; verify workloads run where evaluation is supported" (INFO/advisory), not CRITICAL. Only raise CRITICAL when evaluation is supported **and** the list is empty.

## 3. Model access / `ListFoundationModels` — listed ≠ accessible

- **Trap:** `ListFoundationModels` returns models that exist in the region. Presence in the list does **not** mean the account has been granted access to invoke them.
- **Correct reading:** A model can appear in `ListFoundationModels` yet `InvokeModel` fails with `AccessDeniedException`. Access to many models is enabled by default with the right AWS Marketplace permissions; the usual causes are a missing `aws-marketplace` permission for the first (subscribing) call, an IAM or SCP deny, the Anthropic first-time-use form for Anthropic models earlier than Claude Opus 4.7, or additional account-level access the model needs ([model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)). Judge access from those and from actual invocation errors, not list membership.

## 4. `modelLifecycle.status` — ACTIVE now, deprecated soon

- **Trap:** `status: ACTIVE` reads as "fine, no action." Deprecation is announced ahead of the end-of-life date; a model is `ACTIVE` right up until it legacies.
- **Correct reading:** `ACTIVE` is necessary but not sufficient. Cross-check against AWS model lifecycle announcements for a scheduled EOL date; a model with an imminent EOL still warrants lifecycle planning (Bedrock model-lifecycle area).

## 5. Guardrail `DRAFT` — exists but not what's enforced

- **Trap:** `GetGuardrail` on the DRAFT returns a fully populated policy, reading as "guardrail is configured and strong."
- **Correct reading:** DRAFT is editable and may differ from the **published version** the application actually references. Evaluate the specific `guardrailVersion` used at invoke time. A strong DRAFT with production pointing at an older/weaker version is still a finding for the Bedrock Guardrails area.

## 6. Agent `PREPARED` status vs alias in use

- **Trap:** `GetAgent` showing `agentStatus: PREPARED` reads as "the latest config is live."
- **Correct reading:** Applications invoke an **alias**, which maps to a specific version — not necessarily the latest prepared DRAFT. A newly prepared DRAFT does not change production until an alias is pointed at a new published version (Bedrock Agents area). Always resolve alias → version.

## 7. SageMaker endpoint `InService` with `CurrentInstanceCount` = 0

- **Trap:** `DescribeEndpoint` `EndpointStatus: InService` reads as healthy and serving.
- **Correct reading:** A variant can be `InService` yet report `CurrentInstanceCount: 0` (scaled in, scale-to-zero async/serverless, or a misconfigured leftover). `InService` is control-plane state, not proof of serving capacity → check instance count and recent `Invocations` (SageMaker endpoint area).

## 8. Knowledge Base exists ≠ data ingested

- **Trap:** `GetKnowledgeBase` returning `status: ACTIVE` reads as "KB is ready and populated."
- **Correct reading:** KB `ACTIVE` only means the resource/vector-index wiring is valid. If no `StartIngestionJob` has completed (`ListIngestionJobs` empty), the vector store is empty and retrieval returns nothing (Knowledge Bases / RAG area). Always verify ingestion-job history, not KB status.

## 9. `DescribeScalableTargets` empty ≠ no scaling intended

- **Trap:** An empty scalable-targets response reads as "auto-scaling is simply off, low severity."
- **Correct reading:** For a production endpoint, empty means **fixed capacity** (SageMaker endpoint area) — it cannot absorb spikes or scale in to save cost. Confirm it's registered under `application-autoscaling` with namespace `sagemaker`, resource id `endpoint/<name>/variant/<variant>`; a wrong resource-id lookup also returns empty and can be mistaken for "no scaling."

## 10. CloudWatch "no datapoints" ≠ metric is zero

- **Trap:** `GetMetricStatistics`/`GetMetricData` returning no datapoints is read as "the value is 0 (e.g., 0 errors — healthy)."
- **Correct reading:** No datapoints usually means **no traffic / metric not emitted in that window**, not a measured zero. For error metrics this is benign; for `Invocations` it may indicate an idle resource. Distinguish "zero measured" from "nothing reported." When reading the `OpsAI/Evaluation` custom-metric presence for LLM-SM-EVAL-003, absent datapoints mean the scores were never published, not a measured zero.

## 11. Guardrail `InvocationsIntervened` high ≠ guardrail broken

- **Trap:** A spike in `InvocationsIntervened` reads as a misconfigured/overly-aggressive guardrail to loosen.
- **Correct reading:** A spike is often the guardrail **working** against an attack campaign or a prompt/model regression. Investigate the cause (attack vs false-positive) before weakening the guardrail.

## 12. Provisioned Throughput `InService` ≠ in use

- **Trap:** PT `status: InService` reads as "actively serving, keep it."
- **Correct reading:** `InService` means the capacity is provisioned and **billing**, independent of whether anything invokes it. Correlate with actual token throughput to detect idle PT (Provisioned Throughput area).

## 13. `GetDataSource` chunking default

- **Trap:** A missing chunking configuration reads as "no chunking" (whole documents), or as a fault.
- **Correct reading:** When the data source has no chunking configuration, Amazon Bedrock splits content into chunks of about 300 tokens, preserving sentence boundaries; whole-document chunking is the explicit `NONE` strategy ([customize ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-customize-ingestion.html)). An unset strategy is therefore a known default, not "no chunking"; treat it as a tuning question for long or heterogeneous documents (LLM-KB-003), not as a fault.

## 14. Cross-region inference profile IDs look region-prefixed but aren't a region override

- **Trap:** A profile id like `us.anthropic.claude-...` reads as "pinned to us-east-1 only."
- **Correct reading:** The `us.`/`eu.`/`apac.` prefix denotes the **geographic routing scope**, and requests may be served from any member region in that scope. Billing follows the source region; don't assume single-region behavior (inference-profile and spend areas).

## 15. A SageMaker-side eval runs as a recipe-driven training job

- **Trap:** An evaluation request reads as one kind of job regardless of which service runs it.
- **Correct reading:** A SageMaker-side eval runs as a recipe-driven training job — confirm which service ran it (`sagemaker:DescribeTrainingJob` vs `bedrock:GetEvaluationJob`); a Bedrock-native `CreateEvaluationJob` is diagnosed on this skill's Bedrock path with LLM-EVAL ids (LLM-SM-EVAL-004 marks the switch).
