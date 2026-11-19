# Guardrails review (LLM-GRD)

Read this file before the first call of a guardrail question, or before answering one from evidence;
paths are relative to the skill root. The Output rule in `SKILL.md` applies throughout, and where this
file is stricter, it wins.

## Router
**Match the depth to the question.** A question that names a guardrail, app or Lambda: read that
resource and what calls it, and answer from what you read, not from memory. A how-to or "why" question with nothing
to inspect: "Answering from evidence" below. A request to review posture: the full Review Procedure.

How to read each API and metric is in `references/guardrails/collection-reference.md`. Load it with any row that
reads the account. Rows that load `references/guardrails/service-limits.md` or `references/guardrails/documented-behavior.md`,
and the questions in "Answering from evidence", work from the evidence; read the account only for a
resource the question names.

| Operator says | First read | Load |
|---|---|---|
| Is anything protecting this model, do we have a guardrail | Enforcements (Step 1a), then `ListGuardrails`, then what each production path references | `references/guardrails/checks-guardrails.md` (LLM-GRD-001, 021), [resolution table](references/guardrails/collection-reference.md) |
| Guardrail looks strong but nothing is blocked in production | The version the invocation pins, DRAFT or numeric; then every element's `inputAction`/`outputAction` | `references/guardrails/checks-guardrails.md` (LLM-GRD-006, 011), `references/guardrails/api-quirks.md` |
| Are the filters strong enough, prompt attacks getting through | `contentPolicy` filter strengths and actions per input and output (`PROMPT_ATTACK` is input-only) | `references/guardrails/checks-guardrails.md` (LLM-GRD-002) |
| PII in prompts or completions | `sensitiveInformationPolicy` entities, regexes and their actions per side | `references/guardrails/checks-guardrails.md` (LLM-GRD-003), `references/guardrails/api-quirks.md` §17, §18 |
| Off-topic answers, profanity | `topicPolicy`, `wordPolicy` | `references/guardrails/checks-guardrails.md` (LLM-GRD-004, 005) |
| Did we ever test this guardrail | `AWS/Bedrock/Guardrails` `Invocations` on this guardrail's DRAFT or an earlier version before the enforced version was created (activity only) | `references/guardrails/checks-guardrails.md` (LLM-GRD-007) |
| Hallucination on a RAG path, or correct answers blocked as ungrounded | `contextualGroundingPolicy` thresholds and `action`; each blocked sample's GROUNDING and RELEVANCE score against its threshold | `references/guardrails/checks-guardrails.md` (LLM-GRD-008), `references/guardrails/documented-behavior.md` §4, `references/guardrails/api-quirks.md` §16 |
| Intervention count spiked or dropped, or what share is blocked | `InvocationsIntervened` against `Invocations` for the same ARN, version and window | `references/guardrails/metrics-and-logs.md` |
| Tool output still gets through, or zero interventions on an app that uses tools | How the app passes tool output (`toolResult` blocks) and whether it screens it; on the Converse API the guardrail's strength is not the cause for those fields | `references/guardrails/documented-behavior.md` §1, `references/guardrails/api-quirks.md` §15 |
| The same prompt is blocked on one call and not the next | The version and side of each call, detect mode, what the call marks for evaluation, the streaming mode; no account sweep | `references/guardrails/documented-behavior.md` §2 |
| A guardrail adds latency, or streaming is slow | The streaming mode and what the call marks for evaluation (from the code or evidence given), then the measured latency | `references/guardrails/documented-behavior.md` §3, `references/guardrails/metrics-and-logs.md` |
| Blocked message UX, is it encrypted | Blocked-message config, `kmsKeyArn` | `references/guardrails/checks-guardrails.md` (LLM-GRD-009, 010) |
| A guardrail limit or quota is hit, or a call with a guardrail attached fails as input too long | The error text and the API that raised it, then the documented limit for that Region and tier | `references/guardrails/service-limits.md` |

## Answering from evidence (no account to read)
Use this section when the question is about a different account (a customer's), the user pasted the
evidence and says it is not this account, or it is a how-to or "why" question with nothing to inspect.
Then:

1. **Do not run the Review Procedure against the connected account, and do not list its guardrails or
   pick one for the user.** The connected account's guardrails say nothing about the account in the
   question. Work from the evidence the user gave, and say what you did not check.
2. **Name the cause the evidence supports, and the one check that confirms it.** When several causes
   fit, list the two or three most likely in order, each with the check that confirms or rules it out,
   and give the exact command or console step for the user to run. Do not write "almost certainly".
   Write commands with placeholders (`<guardrail-id>`, `<Region>`) and mask any 12-digit account ID
   that appears in pasted evidence.
3. **Cite a check-id when one matches.** When none does, give the guidance with its AWS-doc citation and
   no check-id. An answer that reports none of this skill's checks as a finding needs no check-id, and
   you never invent one.
4. **Use `references/guardrails/service-limits.md` for any guardrail limit or quota.** Say whether that row is
   fixed or adjustable and where the user reads the value that applies to them. Use
   `references/guardrails/documented-behavior.md` for what a guardrail evaluates when a call uses tools, why a
   prompt is blocked only sometimes, latency and grounding scores.
5. **Hand off what this skill does not own** (model access and logging; model quota and cost;
   knowledge-base ingestion and retrieval) with *Related skills (optional)* in `SKILL.md`.
6. **When the cause needs AWS-side data** (internal service behaviour, a defect, an activation), say so,
   give the workaround the evidence supports, and recommend a support case with the request IDs and
   timestamps.
7. **No invented specifics.** Do not write a limit, model name, date or documentation quote unless it is
   in the user's evidence, in `references/`, or in an Appendix page you have read.

## The Review Procedure
Run these steps in order for each guardrail and each production invocation path in scope. Track
progress against the checklist. Steps 2–10 only make sense once Steps 1 and 1a have established what
guardrails exist and which version each production path actually enforces, so do not skip ahead.

- [ ] Step 1: Enumerate guardrails with `ListGuardrails` and resolve which guardrail + version each production path references (agent alias version, flow node, app InvokeModel/Converse, RetrieveAndGenerate) with the [resolution table](references/guardrails/collection-reference.md) (Guardrails section): agent/flow configuration, `AWS/Bedrock/Guardrails` `Invocations` by `GuardrailArn` + `GuardrailVersion`, invocation-log `appliedGuardrailDetails` when logging is on
- [ ] Step 1a: Read enforcements before judging any path: `bedrock:ListEnforcedGuardrailsConfiguration` (per Region) and `organizations:DescribeEffectivePolicy` with policy type `BEDROCK_POLICY`. An enforced `guardrailArn`:`guardrailVersion` guards every invocation (`guardrailOrigin` `ACCOUNT_ENFORCED` / `ORGANIZATION_ENFORCED`): evaluate it in Steps 3–10 and report `modelEnforcement.excludedModels` and `selectiveContentGuarding`. "Not in an Organization" or AccessDenied is a disclosed gap, never "no enforcement". None at either level is LLM-GRD-021 (INFO)
- [ ] Step 2: For every customer-facing path with no request-level guardrail **and** no account/organization enforcement, raise LLM-GRD-001 (CRITICAL)
- [ ] Step 3: `GetGuardrail` the enforced version. First sweep every policy element's `inputAction`/`outputAction` and `inputEnabled`/`outputEnabled` (contextual grounding: `action`/`enabled`): `NONE` (detect mode) or `false` (side not evaluated) on a side the path uses leaves that side unprotected, LLM-GRD-011 (HIGH), whatever the strength. Then check `contentPolicy`: each harmful-content filter above `NONE` strength, action `BLOCK`, enabled on input and output; `PROMPT_ATTACK` is input-only — require `inputStrength` ≥ `MEDIUM` and `inputAction` `BLOCK`, never flag its output side (LLM-GRD-002)
- [ ] Step 4: Check `sensitiveInformationPolicy` — PII entities and regex filters present with action `BLOCK` or `ANONYMIZE` and evaluation enabled on the sides the path needs; for an `ANONYMIZE` entry that returns only `action`, input coverage is unproven (in a test it was masked on output and not on input); for a `BLOCK` entry that returns only `action` (untested), report the input side as could not confirm, a disclosed gap and not a finding (`references/guardrails/api-quirks.md` §17) (LLM-GRD-003)
- [ ] Step 5: Check `topicPolicy` for a non-empty denied-topics list with action `BLOCK` and evaluation enabled where off-topic risk exists (LLM-GRD-004)
- [ ] Step 6: Check `wordPolicy` for managed profanity and custom blocked words with action `BLOCK` and evaluation enabled where expected (LLM-GRD-005)
- [ ] Step 7: Confirm each path pins a published numeric version, not DRAFT or an omitted version, using the [resolution table](references/guardrails/collection-reference.md) evidence from Step 1 (LLM-GRD-006). When the symptom is strong filters but nothing blocked, always explain why strength read from DRAFT says nothing about production (production enforces the version the path pins; a numeric version is a frozen snapshot; DRAFT can be edited after it), then state which case applies (DRAFT pinned, older version pinned, detect mode with action `NONE`, or not attached), even when you rule DRAFT out
- [ ] Step 8: Look for evidence the guardrail was validated against adversarial inputs before rollout — `AWS/Bedrock/Guardrails` `Invocations` on this guardrail's `GuardrailVersion` `DRAFT` or an earlier published version before the enforced version's creation (activity only; LLM-GRD-007, INFO)
- [ ] Step 9: On any RAG / KB path, check `contextualGroundingPolicy` grounding and relevance filters: `threshold`, `action` `BLOCK`, `enabled` true (LLM-GRD-008)
- [ ] Step 10: Check blocked-message customization (LLM-GRD-009) and `kmsKeyArn` CMK encryption — absent means an AWS managed key; present, confirm with `kms:DescribeKey` `KeyManager` `CUSTOMER` (LLM-GRD-010)

The exact read-only API calls and the field each contributes, the path-resolution table and the Logs
Insights query are in `references/guardrails/collection-reference.md` (Guardrails section). Detection rules and
remediations for every check are in `references/guardrails/checks-guardrails.md`. Guardrail metrics
(`InvocationsIntervened`, `Invocations`) are in `references/guardrails/metrics-and-logs.md`.

**Bound the review and land a result in a single turn.** Each step is best-effort: if an API is
denied, record the gap and continue. A posture report built on the checks you could run, with the rest
disclosed as skipped, is a correct and useful answer; an exhaustive hunt that never produces a report
is not.

## Before You Present — Validate Your Own Output
A guardrail finding that is wrong — or that leaks what it was meant to protect — is worse than no
finding. Before you present a result, re-check your own output against this list. Treat it as a gate,
not a suggestion.

- [ ] Every finding carries a matching `LLM-GRD-###` check-id from `references/guardrails/checks-guardrails.md`,
  and that id corresponds to what was actually observed (not a near-miss id reused for convenience).
- [ ] Each finding cites the **concrete observed value** that triggered it (e.g. "content filters at
  NONE", "`outputAction` NONE on the PII policy", "no `guardrailVersion` on the Converse call"),
  distinguishing "measured absent" from "could not read". A per-model or per-path "no guardrail" claim
  from invocation logs is "could not confirm"; the measured claim is the aggregate in row (d).
- [ ] You evaluated the **version production actually enforces**, not a DRAFT — if the path points at
  DRAFT or omits the version, that itself is LLM-GRD-006, regardless of how strong the DRAFT looks.
- [ ] You read the **enforcements** (Step 1a) before raising LLM-GRD-001, and the report states the
  enforcement origin (`REQUEST`, `ACCOUNT_ENFORCED`, `ORGANIZATION_ENFORCED`, or none).
- [ ] No **raw 12-digit AWS account ID** (ARNs have the account segment masked), no **blocked prompt or
  completion text** (only the policy that fired and the count), no **secret material** (key name only),
  no **invented threshold** (a `workload-specific` check with no AWS number is `INFO`), and the **scope
  you skipped** (regions, paths, checks blocked by permissions) is disclosed.
- [ ] **The final chat answer is the report.** When a full report is requested, the output follows
  [the posture report template](assets/guardrail-posture-report-template.md), transcribed in full from
  any sub-agent output (never a summary), with a check-id and an AWS-doc URL on every finding row. A
  user's list of columns or sections is a minimum, never a replacement: keep all eight Findings columns
  and the Prescription section. When you delegate, paste the template's table header and each check's
  remediation text into the sub-agent's prompt, and copy cells forward unchanged, including the
  `measured` / `no-datapoints` / `not-queried` prefix, the `workload-specific` label and the
  Scope-not-covered lines. When you answer a task delegated to you by another agent, return the finished
  user-facing answer, with every finding's check-id and severity in the template format, so it can be
  relayed verbatim.

If any item cannot be satisfied, state that explicitly in the output rather than quietly dropping it.

## Guardrails
Non-negotiable, at every step:

1. **Read-only, with no exceptions.** Never call a mutating or invoking API. That includes
   `bedrock:ApplyGuardrail` and `bedrock:InvokeGuardrailChecks` (`bedrock-runtime` client calls): both invoke the
   guardrail, both are billable, and pointed at the wrong identifier they exercise a production path.
   IAM classes both as access level Read and `ReadOnlyAccess` omits them, so only this rule protects
   against them. Testing a guardrail is the customer's action, not yours. Report that no validation
   evidence exists and give them the exact command to run.
2. **Never echo a raw AWS account ID** or anything credential-shaped; the Output rule above covers
   every sentence, including delegation labels and status notes. Mask an ARN quoted as evidence:
   `arn:aws:bedrock:us-east-1:<account>:guardrail/...`. When you hand work to a sub-agent, put this rule
   in its prompt.
3. **Never disclose secret material — and never reproduce blocked content.** Report env vars, keys,
   tokens, connection strings by **key name only**. For a guardrail that intervened, report the
   **policy that fired and the count** — never the text of the blocked prompt or completion.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured absent" from "could not read" (`references/guardrails/api-quirks.md`).
5. **A check-id on every finding.** Each finding references an `LLM-GRD-###` catalog check-id and
   carries that check's severity and AWS-doc citation. No freelance findings.
6. **Never invent a threshold.** Severities come from the catalog. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which regions, guardrails, paths, or checks
   you did not cover, and why (budget, permissions, region-unsupported feature). `Regions skipped: none`
   is allowed only when every enabled Region was queried; a Region you did not query is skipped,
   whatever you believe it contains.

## Common wrong answers
- "A guardrail exists, so the path is protected." It protects nothing until the invocation references it or an enforcement applies it. Resolve what the production path actually passes.
- "No caller passes a guardrail, so nothing is protected." An account- or organization-level enforcement guards every invocation. Read the enforcements (Step 1a) before raising LLM-GRD-001.
- "The guardrail is strong." That may be the DRAFT you read. A path that pins a numeric version enforces that snapshot whatever the DRAFT says; a path that pins `DRAFT` enforces the DRAFT as it stands at each call, which can change (LLM-GRD-006).
- "`InvocationsIntervened` is high, so loosen the guardrail." A spike is often the guardrail working, against an attack or a prompt regression. Investigate the cause before weakening anything.
- "`InvocationsIntervened` is zero, so the guardrail is healthy." Zero interventions and zero invocations look identical on that metric. Check `Invocations` too.
- "Filters are configured." Configured at NONE strength filters nothing. Report the strength, not the presence.
- "Filters are at HIGH." HIGH strength with action NONE filters nothing — that is detect mode (LLM-GRD-011). Report the action, not the strength.
- "The prompt-attack filter has no output strength, that is a gap." `PROMPT_ATTACK` is input-only; its output side is not applicable.
- "PII detection is on." On for input and on for output are different settings, so check both sides. In a test, `ANONYMIZE` entries that returned only `action` were masked on output and nothing was reported on input (`references/guardrails/api-quirks.md` §17).
- "The invocation log has an `inputAssessment` entry for the guardrail, so the input was evaluated." The entry only shows the guardrail was applied to that side. Look for a policy section with `detected` true; a `usage` unit above 0 is supporting evidence only, and 0 units is not proof the side was skipped (`references/guardrails/api-quirks.md` §18). Read key names, counts and booleans, never the `match` values or `modelOutput`.
- "A guardrail is attached and nothing intervened, so tool output is screened." On the Converse API, tool results, tool definitions and tool-call arguments are not evaluated; the application has to screen them (`references/guardrails/documented-behavior.md` §1).
- "Answers are blocked as ungrounded, so lower the threshold." Read each blocked sample's score and compare the answer with the source passage: just under the threshold on an answer the source supports is tuning; an answer the source does not support is the check working at any score, and a lower threshold lets it through (`references/guardrails/documented-behavior.md` §4).
- "The same prompt is blocked only sometimes, so the guardrail is not wired everywhere." Rule out version, side, detect mode, what the call marks and the streaming mode first. AWS says ML-based safeguards are probabilistic but not that identical input is judged differently on repeated calls; name no cause the evidence does not show (`references/guardrails/documented-behavior.md` §2).
- "The intervention rate is `InvocationsIntervened` over model calls." `Invocations` counts evaluations (an allowed non-streaming inline `Converse` call counted twice when measured, one model, one Region; other paths not measured): divide by it and write "x of y evaluations" (`references/guardrails/metrics-and-logs.md`).

## Severity Definitions
| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active responsible-AI exposure on a production path | 24–48 hours |
| **HIGH** | Serious responsible-AI / reliability gap | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are operational guidance (derived), not AWS-published commitments.

## Error Handling
Before interpreting any response, consult `references/guardrails/api-quirks.md`: it lists the misleading responses
that cause false positives and false negatives. Call out the ones that apply; these matter most here:

- **A strong DRAFT is NOT what a path that pins a numeric version enforces** (`references/guardrails/api-quirks.md` §5).
  Evaluate the version the invocation pins; DRAFT or an older published version pinned is LLM-GRD-006.
- **An `InvocationsIntervened` spike is often the guardrail WORKING** (`references/guardrails/api-quirks.md` §11). Find the
  cause (attack or false positive) **before** recommending the guardrail be weakened.

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a guardrail feature**, record it as a disclosed assumption, not a finding. On **throttling of
describe/get calls**, back off and paginate. On **ambiguous scope** (which guardrail, which Region),
never stop to ask: default to the caller's current Region and to the guardrails that the request
describes or that a production path references (Step 1), say which ones you reviewed and why, and
list the others by name.

## Appendix — Reference Links
Guardrails references under `references/`:

- [references/guardrails/checks-guardrails.md](references/guardrails/checks-guardrails.md) — LLM-GRD-001..011 and 021 detection rules, remediations, citations (primary)
- [references/guardrails/collection-reference.md](references/guardrails/collection-reference.md) — the read-only API calls and fields per check, the path-resolution table and the Logs Insights query
- [references/guardrails/metrics-and-logs.md](references/guardrails/metrics-and-logs.md) — guardrail CloudWatch metrics and dimensions + invocation-log signals
- [references/guardrails/api-quirks.md](references/guardrails/api-quirks.md) — misleading read-only API responses (DRAFT §5, InvocationsIntervened §11, tool-using paths §15, grounding blocks §16, action-only PII entries §17, assessment entries §18)
- [references/guardrails/service-limits.md](references/guardrails/service-limits.md) — documented count, size and rate limits for guardrails, fixed vs adjustable, and how to answer a limit question
- [references/guardrails/documented-behavior.md](references/guardrails/documented-behavior.md) — what a guardrail evaluates when a call uses tools, why a prompt is blocked only sometimes, latency, and how to read a grounding score

Output template under `assets/`:

- `assets/guardrail-posture-report-template.md` — consolidated posture output (scope with enforcement
  origin, findings with check-ids, severities and AWS-doc URLs, enforced-version evidence, skipped scope)

AWS documentation:

- [Bedrock Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)
- [Guardrails enforcements (account and organization level)](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-enforcements.html)
- [Content filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html)
- [Prompt attacks (input-only filter)](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)
- [Handling options: block, mask, detect mode](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-harmful-content-handling-options.html)
- [Sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html)
- [Denied topics](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-denied-topics.html)
- [Word filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-word-filters.html)
- [Contextual grounding check](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html)
- [Test your guardrail (customer-run)](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-test.html)
- [Create a version of a guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-versions-create.html)
- [Deploy your guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-deploy.html)
- [Create your guardrail (components, blocked messaging)](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-components.html)
- [Customer managed key for your guardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-permissions-kms.html)
- [Monitor guardrails with CloudWatch metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html)
- [Amazon Bedrock endpoints and quotas (Guardrails rows)](https://docs.aws.amazon.com/general/latest/gr/bedrock.html)
- [Request a quota increase (Service Quotas)](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html)
