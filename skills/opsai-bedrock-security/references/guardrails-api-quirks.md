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

## 15. A guardrail attached to a tool-using call with zero interventions

- **Trap:** The call references a guardrail, `Invocations` is non-zero and `InvocationsIntervened` is zero. That reads as "protected, and nothing bad went through".
- **Correct reading:** On the Converse API a guardrail does not evaluate tool results, tool definitions or the model's tool-call arguments, whatever the filter strength or action (`documented-behavior.md` §1; the Converse page gives the table, the sensitive-information page adds `InvokeModel` tool-call arguments for the PII filter, and the pages read give no table for agents or flows). Zero interventions says nothing about content that travels in those fields. Check how the application passes tool output and whether it screens it; say what the metric cannot show. For those fields the configuration is not the cause, so do not recommend strengthening or recreating the guardrail. Zero interventions overall can still be detect mode or a disabled side (LLM-GRD-011), DRAFT (LLM-GRD-006) or no traffic; rule those out too.

## 16. A contextual grounding block is not proof the threshold is too strict

- **Trap:** Correct-looking answers are blocked as ungrounded, so the threshold is called too strict and lowered.
- **Correct reading:** Read the blocked sample's `score` against its `threshold`, check the tier and language (Classic does not support conversational use and covers English, French and Spanish), then compare the answer with the grounding-source passage (`documented-behavior.md` §4). The comparison decides it, not the score gap: a score close under the threshold does not show the answer is supported (observed: a supported answer scored 0.88 and one with an invented fact 0.85, `documented-behavior.md` §4). A supported answer close under the threshold is tuning (Classic strictness). An answer that adds to or contradicts the source is the check catching a real hallucination at any score, and a lower threshold lets it through. A grounding filter that is configured, enabled and set to `BLOCK` is not an LLM-GRD-008 finding.

## 17. A PII entity or regex that carries only `action`

- **Trap:** `GetGuardrail` returns a PII entity as `{type, action}`, or a regex as `{name, pattern, action}`, with no `inputAction`, `outputAction`, `inputEnabled` or `outputEnabled`. `action: ANONYMIZE` reads as "masked on input and on output".
- **What AWS says:** the API reference lists `action` as required and the four side-specific fields as optional, and does not say what an entry with only `action` does on each side ([GuardrailPiiEntity](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailPiiEntity.html), [GuardrailRegex](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailRegex.html)). The user guide calls `action` the action to take when the entity is detected and the four fields optional settings "to configure different behaviors for prompts and responses"; it does not say which sides `action` alone covers ([sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html)). AWS's April 2025 launch post for masking on input prompts says that Block and Mask modes were previously both available for model responses and that Block was the only option for input prompts ([launch post](https://aws.amazon.com/blogs/aws/amazon-bedrock-guardrails-enhances-generative-ai-application-safety-with-new-capabilities/)). None of these says what an `action`-only entry does today.
- **Observed, not documented** (one test: a test account used to evaluate this skill, us-east-1, 2026-11-07; three `ANONYMIZE` entries that carry only `action`, an EMAIL entity in each of two guardrails and a regex in one; an `action`-only `BLOCK` entry was not tested): `ApplyGuardrail` on the DRAFT masked the match with `source` `OUTPUT` and reported nothing with `source` `INPUT`. With `outputScope` `FULL`, which also lists entities that were evaluated and not detected (run on one of the EMAIL entities; it does not apply to regexes), the entity was absent from the `INPUT` result, while a guardrail with explicit `inputAction` listed its entities there. Through `Converse` (Amazon Nova Lite, temperature 0, `trace` `enabled_full`, three repeated calls per guardrail), a user message that gave a made-up address and asked for the text after the @ got `example.com` from one of the two guardrails with an `action`-only entry (the one used for the `FULL` run). A placeholder such as `{EMAIL}` carries no domain, so this fits the user's text reaching the model unmasked; the API does not return the text the model received, so that is an inference. In the same calls the trace listed the EMAIL entity on the output (evaluated, not detected) and no entity on the input. On a guardrail with explicit input fields the trace reported EMAIL ANONYMIZED on the input and the model declined to answer. A `BLOCK` entity with only `action`, `inputEnabled` false and `outputEnabled` true acted on output only, as its flags say. A second read, of the model invocation log of the same account, is consistent with this but counts units, not masking, and a 0 does not prove the policy did not run (§18): the input entries of four readable guardrail versions with `ANONYMIZE` PII entities that return only `action` showed no sensitive-information unit (paid or free) above 0, against above 0 for versions with a PII entity enabled on input. It is not fully independent of the test: the four versions belong to three guardrails, two of them tested above, and the six entries of the DRAFT are probably the `Converse` calls above.
- **Correct reading:** for an `ANONYMIZE` entry that returns only `action`, count the output side and treat the input side as unproven. It did not behave like detect mode (detect mode returns the detection, and none was returned on input). Raise LLM-GRD-003 for the input side when the path needs it, citing the observed value (the entry returns only `action`), and say the reading is an observation from one test. For an `action`-only `BLOCK` entry do not extend the observation: report the input side as could not confirm, a disclosed gap and not a finding (Guardrails rule 4), and give the customer the check below. The fix is explicit `inputAction`, `outputAction`, `inputEnabled` and `outputEnabled` on every entry.
- **The customer's check** (their action, billable, never yours): `aws bedrock-runtime apply-guardrail --guardrail-identifier <guardrail-id> --guardrail-version <version> --source INPUT --output-scope FULL --content '[{"text":{"text":"<text with a made-up value>"}}]' --region <Region>`, then the same call with `--source OUTPUT` as a control. An entity that appears on `OUTPUT` and is missing from `INPUT` is not evaluated on input. `--output-scope` does not apply to regexes: for a regex compare what each side reports ([ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ApplyGuardrail.html)).

## 18. A guardrail entry under `inputAssessment` or `outputAssessments` is not a detection

- **Trap:** In an invocation-log record the `inputAssessment` entry is keyed by the guardrail's id (observed in the log read; AWS's Converse example does not name the key). Finding that entry, or counting the records that contain it, reads as "the guardrail evaluated the input and acted on it".
- **Correct reading:**
  - The entry shows the guardrail was applied to that side (`appliedGuardrailDetails` names it, its version and its origin). It does not show that a policy ran or detected anything, so do not read a record that contains the entry as evidence of either. Counting records by applied version for traffic is still fine (`guardrails-collection-reference.md` row (e)).
  - A policy section with `detected` true is a detection on that side. A section can also hold only `detected` false items. A missing section says little unless the trace lists `detected` false items; that is an inference, because the log does not show the `trace` setting.
  - A `usage` unit above 0 for a policy is supporting evidence only (see Observed); a regex reports in `sensitiveInformationPolicyFreeUnits`, not `sensitiveInformationPolicyUnits`. The pages read do not say whether a policy that ran can report 0 units, so a 0 does not prove it did not run. Before reading a 0, check that `guardrailCoverage.textCharacters.guarded` covers the text that holds the value (`documented-behavior.md` §3) and read the version's `inputEnabled` and `inputAction` (a disabled side, or `inputAction` `NONE`, is LLM-GRD-011).
  - For an `ANONYMIZE` entry that returns only `action`, §17 already treats input coverage as unproven from the entry's shape; no section and 0 units on the input entry is consistent with that, and a section or units above 0 argues against it. The customer's check there tests it. For anything else (an entry with explicit `inputEnabled` and `inputAction`, an `action`-only `BLOCK` entry, another policy) a log entry with no section and 0 units is not a finding by itself: report could not confirm, a disclosed gap and not a finding, and give the customer the same check. If the customer's own evidence shows a value it should catch reaching the model (the reply repeats it; the API does not return the text the model received, so that is an inference), that strengthens the case.
  - Read key names, counts and booleans only. Never read or quote the `match` values, `modelOutput` (the reply before masking) or the prompt text: the trace and the log can hold the unmasked values (`documented-behavior.md` §3).
- **What AWS says:** every field of a `GuardrailAssessment` is optional: `appliedGuardrailDetails`, `invocationMetrics` (coverage, latency, `usage`) and one section per policy ([GuardrailAssessment](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailAssessment.html), [AppliedGuardrailDetails](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_AppliedGuardrailDetails.html)). The `usage` fields are described as units "processed by the guardrail", and the pages read do not say how the units are counted ([GuardrailUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailUsage.html)). For `inputEnabled` false, AWS says the evaluation is not charged and does not appear in the response ([GuardrailPiiEntity](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailPiiEntity.html)). `ApplyGuardrail` by default returns only detected content, and setting `trace` to `enabled_full` gives `Invoke` and `Converse` the same full output, which AWS's note says does not apply to word filters or to regexes in sensitive information filters ([ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)).
- **Observed, not documented** (eight reads of the model invocation log of a test account used to evaluate this skill, us-east-1, 2026-11-08, plus `GetGuardrail` reads of the versions in it): 318 `Converse` and `ConverseStream` records from the four days before, chosen because they contain the string `inputAssessment`, so the sample cannot show how many guarded calls have no entry; 313 had an input entry. None of the reads looked at the logged request, so the `trace` setting is unknown. Only the input side was counted by section; for the output side the shape was read in every record, and sections and units only for the four elements of one guardrail.
  - Every input entry held `appliedGuardrailDetails` and `invocationMetrics`; 205 of 313 held nothing else, and 23 of 120 policy sections listed only `detected` false items. `outputAssessments` was a list of one map from a guardrail id to one assessment (229 of 229 records), not the map to an array that the Converse reference documents for the API response; the pages read do not describe the log.
  - In the 26 readable versions (5 DRAFT, read after the calls), an input entry's `usage` field for a policy was above 0 in every entry of a version with an input-enabled element of that policy (PII entities: 6 versions, 26 entries; regexes: 1 version, 8 entries) and showed no unit above 0 in the one version whose only PII entity had `inputEnabled` false (7 entries). PII entities that return only `action` (all `ANONYMIZE`, read on 2026-11-07 and 2026-11-08) showed no unit above 0 in 4 versions (50 entries; the 3 non-DRAFT versions, 44 entries, also none), and the one regex that returned only `action` showed none in 10 entries. These counts treat a missing counter as 0, so they cannot tell it from an explicit 0. One guardrail with two such PII entities had an explicit 0 in `sensitiveInformationPolicyUnits` on its 4 input entries and 1 on each of its 4 output elements. Content, topic and word elements that return no `inputAction` or `inputEnabled` showed units above 0 on every input entry (content 113, topic 57, word 47), so the log gives no support for carrying §17's reading over to them; the probe did not read `inputStrength` for content filters.
