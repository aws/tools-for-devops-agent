# Documented Guardrail Behavior

What AWS documents about how a guardrail behaves, for questions that are not about one account's
configuration: which content a guardrail evaluates when a call uses tools, why the same prompt can be
blocked on one call and not the next, what adds latency, and how to read a contextual grounding score.
Most statements name the AWS page they rest on. The rule-out lists, the reading and recommendation
columns, and sentences saying "can be" are this skill's reasoning. A sentence marked **observed** reports one test in a test account used to evaluate this skill (one Region, one date),
not an AWS page, and it does not show the behaviour holds elsewhere. Where AWS says nothing, say so; do
not fill the gap with a plausible cause. This skill never calls
`ApplyGuardrail` or any other guardrail-invoking API (Guardrails rule 1 in `SKILL.md`): when a test is
the answer, tell the customer the command to run.

## 1. What a guardrail evaluates when a call uses tools

With `Converse` or `ConverseStream` and a `guardrailConfig`, AWS lists which fields any guardrail
filter evaluates (content filters, prompt-attack detection, denied topics, word filters and
sensitive-information filters)
([Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-converse-api.html)):

| Content | Field | Evaluated |
|---|---|---|
| Input prompts, system prompts, model responses | `text`, `guardContent` | Yes |
| Tool results your application returns | `messages[].content[].toolResult` | No |
| Tool definitions you send | `toolConfig.tools[].toolSpec.description`, `.inputSchema` | No |
| Tool call arguments the model generates | `output.message.content[].toolUse.input` | No |

On the same page, a system prompt is assessed only when it is wrapped in `guardContent`.

- **A tool result is not screened, whatever the filter strength or action.** PII, or an instruction
  injected into a tool result, reaches the next model call unevaluated. A guardrail that is attached
  and shows zero interventions says nothing about content that travels in those fields. The model's
  own text reply is still evaluated.
- **For these fields the cause is how the request is shaped, not how the guardrail is configured.** Do
  not recommend a higher strength, a new guardrail or re-attaching `guardrailConfig` to fix them: none
  of those changes which fields are evaluated. Zero interventions overall can still have the ordinary
  causes (detect mode, DRAFT, no traffic), so rule those out too.
- **The fix is in the application.** `ApplyGuardrail` assesses any text it is sent, without invoking a
  model
  ([ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)),
  so the application can screen tool output with it before the output joins the conversation. That use
  is this skill's suggestion, not an AWS statement: AWS describes `source` `INPUT` for content from a
  user, typically the input prompt, so tell the customer to test it on their own tool output. Tool
  output stays untrusted input: AWS's service card says guardrails do not replace application-level
  input validation
  ([service card](https://docs.aws.amazon.com/ai/responsible-ai/bedrock-guardrails/overview.html)).
  Tell the customer which call to add; you never make it.
- AWS publishes this table for the Converse API. The sensitive-information page adds that the PII
  filter also does not evaluate tool-call arguments in `InvokeModel` (`tool_use` parameters)
  ([sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html)).
  The pages read give no table for agents or flows: do not extend the table to them, and say so.
- Read-only evidence: how the application passes tool output (does it send `toolResult` blocks, and
  does it screen them first). Say that guardrail configuration cannot show this.

## 2. The same prompt is blocked on one call and not on another

AWS's service card says ML-based safeguards are probabilistic: they can miss violations or flag
acceptable content
([service card](https://docs.aws.amazon.com/ai/responsible-ai/bedrock-guardrails/overview.html)). For
built-in PII detection, AWS says it is a probabilistic, ML-based solution that depends on context, so
the same string in different surrounding text can be treated differently; custom regex works by
pattern matching
([sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html)),
and custom word filters by case-insensitive whole-word and whole-phrase matching
([word filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-word-filters.html)).
For content filters, denied topics and prompt-attack detection the pages read do not say which method
is used, so assign none. No page read says that identical input is judged differently on repeated
calls.

Rule out what differs between two calls before leaning on the probabilistic point:

1. **Version and origin.** One caller pins `DRAFT` or an older numeric version, another the current one
   (LLM-GRD-006); or a request-level guardrail applies on one path and an account or organization
   enforcement on another, and an enforcement can exclude models (LLM-GRD-021).
2. **Side.** The prompt passed the input check and the response was blocked on output. The response
   can differ on every call, so the output check can see different text each time.
3. **Detect mode.** An element with action `NONE` reports a detection and blocks nothing
   (LLM-GRD-011), so "blocked" can mean different things in two logs.
4. **What the call marks for evaluation.** `guardContent`, input tags, tool turns (§1) and system
   prompts (assessed only when wrapped in `guardContent`) change what the guardrail sees.
5. **Streaming mode.** In async mode chunks reach the user before the scan finishes, and only later
   chunks are blocked once content is identified, so two calls can differ in how much of a response was
   delivered (§3).
6. **A custom word or regex.** If one blocked it, find what differs between the two texts.
7. **Surrounding context.** For built-in PII detection the same value can be treated differently in
   different surrounding text.

If none of these explains it, say that the documented reason is the probabilistic behaviour above, not a
confirmed cause. Name no cause the evidence does not show, and do not sweep the account to look for
one.

AWS's method for judging a guardrail (service card): test benign, policy-violating, ambiguous and
adversarial prompts; review both missed and unnecessary interventions; set acceptance criteria from the
impact of each error type; retest after every change. Give the customer that method, not a verdict from
one call. Repeating a prompt against the guardrail is the customer's action (billable), never yours.

If behaviour changed and nothing changed on the customer's side: tell the customer to compare the date
it changed with `updatedAt` on the DRAFT, if DRAFT is pinned
([GetGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetGuardrail.html)), and
with when the pinned version number last changed in their deployment. A numeric version is a frozen
snapshot that does not change by itself; an edit to DRAFT or a change of the pinned number can.
Then tell the customer to check AWS Health for a service event and, if none explains it, to open a
support case with the request IDs and timestamps of one blocked and one allowed call. The service card
says changes in the service can change results.

## 3. Latency added by a guardrail

Ask the customer for measurements before recommending anything, and do not run a call yourself. Per
call, the Converse trace (when the application enables it) can carry
`invocationMetrics.guardrailProcessingLatency` (the reference gives no unit) and
`invocationMetrics.guardrailCoverage.textCharacters` (`guarded` and `total` characters)
([GuardrailInvocationMetrics](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailInvocationMetrics.html),
[GuardrailTextCharactersCoverage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailTextCharactersCoverage.html)).
The trace can also hold the unmasked values the guardrail detected (the Converse page says so), so tell
the customer not to log it with ordinary responses. Over time, the guardrail `InvocationLatency` metric
is defined by AWS as the time from when a request is sent to when the last token is received, per
`GuardrailArn` + `GuardrailVersion`; AWS does not document it as only the time the guardrail adds
([guardrail metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html)).
For streaming calls `TimeToFirstToken` in `AWS/Bedrock` shows when the first token arrives
([runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)).

- **Streaming mode.** The default **sync** mode buffers one or more response chunks and scans them
  before they go to the user, so every chunk is scanned before it is sent and chunks are delayed.
  **Async** sends chunks at once and scans in the background: chunks may contain inappropriate content
  until the scan completes, and masking of sensitive information is not supported in async mode
  ([streaming](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-streaming.html)). The
  service card says to keep sync unless latency outweighs content moderation, and that async is not
  appropriate for applications that handle sensitive information or serve vulnerable users. On
  `ConverseStream` the setting is `streamProcessingMode` (`sync` or `async`)
  ([GuardrailStreamConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailStreamConfiguration.html));
  on `InvokeModelWithResponseStream` the streaming page shows `streamProcessingMode` inside
  `amazon-bedrock-guardrailConfig`. Never offer async as the answer without those limits.
- **Evaluate less text.** For input tags on `InvokeModel*`, AWS says evaluating a shorter, relevant
  section of the input helps improve performance and reduce cost
  ([input tags](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tagging.html)). On
  Converse, `guardContent` marks the content to assess, for example only the latest message; that page
  states no performance or cost benefit. The trade is coverage, and the Converse page gives two
  statements about unmarked content that it does not reconcile (skipped entirely; may still be
  evaluated, depending on the policy), so tell the customer to read `guardrailCoverage` in the trace to
  see how much text was guarded.
- **Do not trade protection for speed unannounced.** Turning a policy or a side off removes that
  protection. If you suggest it, say that the side is then unprotected.

## 4. Contextual grounding: reading a blocked answer

Each response gets a **grounding** score and a **relevance** score from 0 to 1. A score below its
filter's threshold is detected, and blocked when the filter's action is `BLOCK`. Thresholds run from 0
to 0.99; 1 is invalid because it would block everything. The check needs the grounding source, the
query and the model response, and it runs on the output only
([contextual grounding](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html)).

- **Grounding** asks whether the response is supported by the source; AWS says any new information
  the response introduces counts as un-grounded. **Relevance** asks whether it answers the query.
- **Tier.** With no tier set the guardrail uses **Classic**, which is strict: any information not
  stated in the source lowers the grounding score, including reasonable inferences and conversational
  phrasing. Classic does not support conversational use cases and supports English, French and Spanish.
  **Standard** scores differently worded answers with the same meaning more consistently, supports
  reasoning and conversational content, needs cross-Region inference and exists in a subset of Regions;
  for conversational or reasoning use on Standard AWS gives 0.7 as a reasonable starting point.
  `GetGuardrail` returns the tier in `contextualGroundingPolicy.tier.tierName` (optional)
  ([policy](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailContextualGroundingPolicy.html)).
  `UpdateGuardrail` replaces the whole policy, and omitting `tierConfig` resets Standard to Classic, so
  a block rate that rose after an update can be a tier change.
- **The trace** holds, per filter, `type`, `threshold`, `score`, `action` (`BLOCKED` or `NONE`) and
  `detected`
  ([filter](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailContextualGroundingFilter.html)).
  By default only detected content is returned, and `trace` `enabled_full` also returns entries that
  were not detected
  ([ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)).
  A blocked sample with no score in the evidence cannot be classified; say so.

Read each blocked sample before anyone changes a threshold. Check the tier and language first: a score
far under on a conversational answer, or in another language, can be Classic used outside what it
supports rather than a hallucination. The comparison of the answer with the grounding-source passage
decides the reading, not the score gap:

| Score against threshold | Answer against the source passage | Reading | What to recommend |
|---|---|---|---|
| Close under | The source supports the answer (paraphrase, inference) | Tuning: Classic strictness, or a threshold set too high for this use | Calibrate on the customer's own blocked and allowed samples and test before deploying; consider Standard tier, which needs cross-Region inference, and retest the thresholds after a tier change (AWS says to). Say that lowering the threshold lets more ungrounded answers through. Name no threshold: AWS's one number is the 0.7 starting point for Standard tier in conversational or reasoning use |
| Far under, or close under | The answer adds a fact to the source or contradicts it | A real hallucination or a wrong passage: the check is working | Fix retrieval, prompt or source; lowering the threshold would let it through |

The score alone does not separate the two rows, as the observation below shows. Classic lowers the grounding score for any information the source does not state,
reasonable inference and conversational phrasing included, so a supported answer and an answer with an invented fact can score alike.
**Observed** (a test account used to evaluate this skill, us-east-1, Classic tier, threshold 0.9, twelve candidate answers each scored three times with identical scores, 2026-11-07): a conversational answer the
source supported scored 0.88 and an answer that invented a reply time scored 0.85. Do not
group blocked answers by score, and do not call a block tuning until you have read that answer against the source passage.

A low **relevance** score with a high grounding score means the answer is supported but does not
address the query, so look at what was retrieved and at the prompt. AWS's service card says the check
evaluates consistency with the source the application provides, not truth in general, and cannot
correct inaccurate or incomplete sources. Because information missing from the source counts as
un-grounded, an incomplete source can lead to a correct answer being blocked (this skill's inference),
and a pass is not proof the answer is accurate.

## AWS sources

- [Converse API with guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-converse-api.html)
- [ApplyGuardrail](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-use-independent-api.html)
- [Streaming behaviour](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-streaming.html)
- [Input tags](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-tagging.html)
- [Word filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-word-filters.html)
- [Contextual grounding check](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html)
- [GetGuardrail](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetGuardrail.html)
- [GuardrailContextualGroundingPolicy](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GuardrailContextualGroundingPolicy.html)
- [GuardrailContextualGroundingFilter](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailContextualGroundingFilter.html)
- [GuardrailStreamConfiguration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailStreamConfiguration.html)
- [GuardrailInvocationMetrics](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailInvocationMetrics.html)
- [GuardrailTextCharactersCoverage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailTextCharactersCoverage.html)
- [Sensitive information filters](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-sensitive-filters.html)
- [Guardrail metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-guardrails-cw-metrics.html)
- [Runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)
- [AWS AI Service Card: Amazon Bedrock Guardrails](https://docs.aws.amazon.com/ai/responsible-ai/bedrock-guardrails/overview.html)
