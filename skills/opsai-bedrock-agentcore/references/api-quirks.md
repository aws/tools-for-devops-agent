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
- **Correct reading:** A model can appear in `ListFoundationModels` yet `InvokeModel` fails with `AccessDeniedException`. Access to many models is enabled by default with the right AWS Marketplace permissions; the usual causes are a missing `aws-marketplace` permission for the first (subscribing) call, an IAM or SCP deny, the Anthropic first-time-use form for Anthropic models earlier than Claude Opus 4.7, or additional account-level access the model needs ([model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html)). Judge access from those and from actual invocation errors, not list membership.

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
- **Correct reading:** For a production endpoint, empty means **fixed capacity** — it cannot absorb spikes or scale in to save cost. Confirm it's registered under `application-autoscaling` with namespace `sagemaker`, resource id `endpoint/<name>/variant/<variant>`; a wrong resource-id lookup also returns empty and can be mistaken for "no scaling."

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

- **Trap:** A missing chunking configuration reads as "no chunking" (whole documents), or as a fault.
- **Correct reading:** When the data source has no chunking configuration, Amazon Bedrock splits content into chunks of about 300 tokens, preserving sentence boundaries; whole-document chunking is the explicit `NONE` strategy ([customize ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-customize-ingestion.html)). An unset strategy is therefore a known default, not "no chunking"; treat it as a tuning question for long or heterogeneous documents (LLM-KB-003), not as a fault.

## 14. Cross-region inference profile IDs look region-prefixed but aren't a region override

- **Trap:** A profile id like `us.anthropic.claude-...` reads as "pinned to us-east-1 only."
- **Correct reading:** The `us.`/`eu.`/`apac.` prefix denotes the **geographic routing scope**, and requests may be served from any member region in that scope. Billing follows the source region; don't assume single-region behavior (LLM-INV-002, LLM-COST-005).

## 15. AgentCore and S3 buckets in another account — a policy gap is usually not the cause

- **Trap:** A 403 / access-denied when a runtime's code artifact or a gateway target's tool schema lives in another account's bucket reads as "widen the bucket policy, KMS key policy or role."
- **Correct reading:** Check the bucket owner first. A **gateway target** schema in S3 (`S3Configuration`) has a `bucketOwnerAccountId` field for cross-account buckets; when the bucket is in another account and that field is unset, recommend that the operator set it (they can test with `update-gateway-target` before changing IaC; this skill does not call it), then confirm the object key (case-sensitive) and the caller's `s3:GetObject`. A **runtime code artifact** location (`S3Location`: bucket, prefix, versionId) has no bucket-owner field; treat a code bucket in another account as unsupported and recommend staging the package in a bucket in the runtime's own account. Further bucket/KMS policy edits do not fix it. Raise an AWS Support case if cross-account staging is needed long term. Do not invent ACL, object-ownership or service-principal causes you did not read.

## 16. A 429 from an agent is not one quota

- **Trap:** Any 429 / `ThrottlingException` seen around an AgentCore agent reads as "the model is throttling, raise the model quota" (or, the other way round, "the model is slow").
- **Correct reading:** Find the layer first (LLM-AC-011). A 429 returned by `InvokeAgentRuntime` with no matching line in the runtime log was rejected by the AgentCore data plane before the container ran (data-plane 1,000 TPS, new session creation 25 TPS, both per account and shared). A throttle raised by the agent code's own model call is the Bedrock model quota. Gateway and Memory have their own rate quotas. Slowness when many requests share one session is contention for that session's fixed 2 vCPU / 8 GB, not a network throttle; AWS documents no per-session bandwidth quota. Cross-account calls count against the runtime owner's quotas. Cite the [AgentCore quotas page](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html) for every number.

## 17. A session ID is not memory, and a memory branch does not merge

- **Trap:** "The session ID is stable, so the history must be stored" — or a memory branch is expected to pick up later events from the main branch, or long-term records are expected right after `CreateEvent`.
- **Correct reading:** A runtime session ID only routes calls to one microVM. Conversation history exists only as AgentCore Memory events the agent code writes (`CreateEvent`) and reads back (`ListEvents`), scoped by memory, actor and session; agents share context only through the same memory resource. A branch (`CreateEvent` `branch` with `rootEventId`) holds the events written to it; there is no merge operation. Long-term records come from asynchronous extraction by the memory's strategies, and blob payloads are not extracted. See LLM-AC-012, [Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html) and [Create an event](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/short-term-create-event.html).

## 18. "Browser" has two meanings, and Runtime numbers are not Browser numbers

- **Trap:** A Browser tool session that crashes after hours is explained with the Runtime session's 2 vCPU / 8 GB allocation and a definite kernel or memory mechanism; or a console page that will not load in the operator's own web browser is called an AgentCore outage or console bug.
- **Correct reading:** Decide first whether the managed Browser tool or the operator's own web browser is involved (LLM-AC-013). A Browser tool session has 1 vCPU / 4 GB, 10 GB disk and a timeout of up to 8 hours; Code Interpreter has 2 vCPU / 8 GB. Long-session degradation is a hypothesis to test with fresh, recycled sessions and with recording off, not a confirmed internal cause. A page that loads in another browser or a private window is client-side first (cache, extensions, proxy, VPN, certificates, DNS; involve the IT or network team). See the [quotas page](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html) and [Browser sessions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-resource-session-management.html).

## 19. Cross-account AgentCore calls need both sides, per action

- **Trap:** A caller in another account can invoke a runtime, so its other calls (`StopRuntimeSession`, `InvokeAgentRuntimeCommand`, gateway or Memory actions) are assumed allowed too; when sessions are not stopped, an internal session-ownership or account-scoping mechanism is invented, or a same-account relay is proposed.
- **Correct reading:** Each action needs an allow in the caller's identity policy and in the resource-based policy on the runtime (and its endpoint), gateway or memory; read both with `get-resource-policy` and the caller's role policies, and read the error the caller's code got back. A missing allow for one action is the cause; the fix is to grant that action on both sides (LLM-AC-014). Unstopped sessions live until the idle timeout and count toward the runtime owner's active-session quota (LLM-AC-011). See [Resource-based policies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/resource-based-policies.html).
