---
name: llmops-quality-evaluation
description: Review whether model output quality is measured, measured automatically, and gated before it reaches
  production. Use this skill when answers have got worse or a model may be hallucinating more, when
  responses are being cut off, when nobody can say whether quality regressed or the same prompt gives
  different answers, when an evaluation job fails, or when someone asks how to compare two models or
  how mature their LLMOps practice is, even if they do not mention evaluation jobs, regression gates,
  promotion criteria or finish reasons by name. It leads on an advisory or standing-review question;
  inside a live investigation it supplies LLM-EVAL findings rows for output-quality depth and leaves
  the fault locus to llmops-incident-triage and the root cause to the host investigation.
  Finish-reason checks read Bedrock invocation logs and are reported not-applicable on a hosting that
  does not emit stopReason. Findings carry LLM-EVAL check-ids with a severity and an AWS-doc citation,
  from read-only APIs.
metadata:
  author: ankitsri-aws
  version: "1.0.0"
  summary: "Reviews whether model output quality is measured, automated and gated before production, and diagnoses evaluation jobs."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Observability"
---

# LLMOps — Evaluation & Model Quality

This is the **LLMOps quality / Continuous-Tuning pillar** — and it covers what no other skill does.
Everything else in the Bedrock operations surface tells you whether the model is *configured*,
*reachable*, *guarded*, and *observable*. This skill answers the three questions that actually
decide whether a GenAI workload is any good:

1. **Is model quality measured at all?** (Has any evaluation ever run?)
2. **Is it measured automatically?** (Is evaluation wired into CI/CD, or run by hand and hope?)
3. **Can a regression reach production?** (Is there a gate that blocks a quality drop before promotion?)

It owns Bedrock model evaluation, quality gates, and regression detection. It is the LLMOps skill
library's main differentiator — the quality pillar that separates LLMOps from running a model in production and
hoping.

Every assessment is grounded in the check catalog under `references/`. Each check carries a stable
`check-id`, a severity, a detection rule, a remediation, and an AWS-doc citation. You never invent a
threshold: if AWS publishes no number, the catalog marks it `workload-specific` (or `derived` for an
operational default) and you report it accordingly.

This skill uses **read-only APIs only** — the `bedrock` evaluation describe/list/get calls in
`references/collection-reference.md`, and the invocation-log and metric reads in
`references/metrics-and-logs.md`. It never mutates a resource. `bedrock:ApplyGuardrail` is not a
collection call, is billable, and is never called.

## When to Use

Activate this skill when the user:

- Reports an **evaluation incident** — an eval job failed, or **"did quality drop"** / a model
  **quality regression**.
- Asks **"is my model still good"**, or how to measure quality — **A/B compare models** or prompt
  versions, **human evaluation** setup.
- Asks how to add a **quality gate** / **regression gate** to model promotion, or wire evaluation
  into CI/CD.
- Asks about **LLMOps maturity** relative to the evaluation pillar.
- Wants a **review of the evaluation posture** — "do we evaluate our models?", "is there a quality
  gate before promotion?".
- Reports **outputs getting truncated** / **max_tokens truncation**, or raises a **finish reason**
  distribution shift (`end_turn` → `max_tokens`) as a suspected regression signal.

**Routing triggers — the literal phrasings, each with the rule that decides it.** A keyword list did
not land; these are the phrasings as users actually write them, with the deciding rule beside each,
because the two prompts below selected **no skill at all** on a measured run and every check-id and
citation went with it. Any question of these shapes selects **this** skill, whether or not the words
evaluation, quality or finish reason appear anywhere in it:

| the user writes | the deciding rule | selects |
|---|---|---|
| "the answers got worse" / "answers have gotten worse" / "quality dropped" | a change in output *quality* over time is the quality pillar, with or without an eval job | **this skill** |
| "we have no way to prove it" / "no evidence to confirm or deny" / "nobody can say whether quality regressed" | "is quality measured at all" is question 1 of this skill; an unmeasurable claim is the finding | **this skill** |
| "is quality measured" / "is anyone checking the model's answers" / "do we evaluate our models" | evaluation coverage and the promotion gate | **this skill** |
| "replies are getting cut off" / "cut off mid-sentence" / "responses are truncated" / "output stops mid-sentence" | truncation is a `stopReason` / `max_tokens` question, measured from invocation logs | **this skill** |
| "answers are shorter than they used to be" | a finish-reason distribution shift, `end_turn` → `max_tokens` | **this skill** |
| "can you prove it from telemetry" (attached to any of the above) | the demand is for evidence, not a different owner — it does not re-route the question | **this skill** |
| "is the model worse than last week" / "A/B compare two models" | quality trend vs baseline | **this skill** |
| "the same prompt gives different answers" / "answers vary run to run" / "is this a regression or just randomness" | separating nondeterminism from a real regression needs a baseline distribution and repeated sampling, which is evaluation work | **this skill** |

A question combining two of these rows — "the answers got worse and we cannot prove it, and some
replies look cut off" — is **one** question for this skill with two evidence tracks, not a reason to
hand it elsewhere or to leave it unrouted.

Truncation and finish-reason work is **this** skill's, not `llmops-incident-triage`'s — but a
truncation question whose evidence turns out to be an API error rather than a `max_tokens` stop
reason hands the **error half only** off to `llmops-incident-triage` by name, and keeps the
truncation half here.

**Corrupted output is a fault, not a quality regression.** Garbled text, wrong-language or
encoding-broken output, or nonsense that starts **abruptly** and affects **only part of the
traffic** (one region, one instance, one endpoint variant) is the shape of a serving or
infrastructure fault. An evaluation job would score it badly but cannot diagnose it. Say so, name
the evidence that separates the two (abrupt onset, partial blast radius, no model or prompt change),
and route the fault to `llmops-incident-triage` (or AWS Support for a managed model) rather than
prescribing an evaluation. A gradual, traffic-wide drift in answer quality stays here.

## When NOT to Use
Every row names a skill that exists. Three rows previously named a role rather than a skill — "the
quota/scaling skill", "the telemetry skill", "the AI/ML skill" — and an agent following them had
nowhere to go.

- **Bedrock configuration, invocation logging, model access setup** → use
  `llmops-bedrock-configuration`.
- **Guardrail policy and filter behaviour** → use `llmops-guardrails`.
- **Live failure triage** (is the fault provider-side, infrastructure or application?) → use
  `llmops-incident-triage`.
- **Access-denied diagnosis** (IAM / SCP / marketplace, AgentCore access) → use
  `llmops-bedrock-configuration`.
- **Throttling, quota, provisioned-throughput sizing, token spend** → use `llmops-capacity-cost`.
- **Telemetry and observability coverage, alarms** → use `llmops-incident-triage`, which owns the
  `LLM-TEL` family including the finish-reason *monitoring* filter LLM-TEL-002. This skill owns the
  eval *gate* that acts on it.
- **SageMaker training, customization and data preparation** → use `llmops-sagemaker-training`.
- **SageMaker-side evaluation jobs** (Nova eval recipe, LLM-as-judge on SageMaker) → use
  `llmops-sagemaker-evaluation`. Bedrock `CreateEvaluationJob` stays here.
- **Writing application code**, or **future price quotes** (direct to the
  [AWS Pricing Calculator](https://calculator.aws/)).

## Role in an investigation
The DevOps Agent's investigation owns a live incident; `llmops-incident-triage` owns the LLM-path
triage within it. This skill is loaded for **output-quality depth** and returns `LLM-EVAL` findings
rows — not a locus, not a root cause, and not the operator-facing answer.

Outside an investigation it leads as it always has: an advisory question about how to evaluate, or a
standing review of whether quality is measured and gated, is this skill's from the first turn.

**Hosting caveat.** The finish-reason work (LLM-EVAL-012, -013, -014) reads `stopReason` from
**Bedrock model invocation logs**. There is no equivalent for a SageMaker endpoint or a self-hosted
model unless the workload emits the field itself. On those hostings report the check as
`not-applicable` with the reason, and name what the workload would have to emit — never map a
Bedrock log field onto a system that does not produce it.

## Scope Model

| Family | Code | Resources | Catalog |
|---|---|---|---|
| Evaluation | `LLM-EVAL` | Bedrock model/RAG/human evaluation jobs, datasets, regression gates, promotion criteria, A/B comparison, finish-reason drift — the LLMOps quality pillar | `references/checks-evaluation.md` |

Assess only what the question or incident touches.

## Finish-Reason Drift

A first-class capability of this skill, not a footnote. The finish-reason distribution is **a small
check with outsized value** — an early, otherwise-invisible indicator of quality regression that no
AWS alarm watches by default. A shift from `end_turn` (natural completion) toward `max_tokens`
(truncation) means outputs are being cut off — because prompts grew and crowded the output budget,
because `maxTokens` was reduced, or because a model version changed generation length. It **precedes
visible quality complaints by hours or days.**

When a quality regression is suspected, examine the finish-reason distribution early. The full
analysis — the `stopReason` field values, the metric filter `{ $.stopReason = "max_tokens" }`, the
derived >10pp alarm threshold, the Logs Insights distribution query, and the correlated signals
(`OutputTokenCount` spikes, `InvocationLatency` rising, truncation complaints) — lives in
**`references/finish-reason-analysis.md`**.

**`stopReason` is not a CloudWatch metric.** The distribution can only be measured from the Bedrock
invocation logs, so resolve the log group from
`bedrock:GetModelInvocationLoggingConfiguration` before reasoning about truncation — the group name
is a customer choice and must never be assumed. The collection mechanics (that probe, the record
schema and the `stopReason` field path, the distribution query, and the fact that
`OutputTokenCount`/`Invocations` are a *precursor* and not a measurement) are in
**`references/metrics-and-logs.md`**.

Together these back three checks: **LLM-EVAL-012** (the shift
itself), **LLM-EVAL-013** (no metric filter, so the shift is invisible), and **LLM-EVAL-014**
(`OutputTokenCount` rising with flat `Invocations`, the correlated precursor) — plus the telemetry
view **LLM-TEL-002**.

## Guardrails

These rules are non-negotiable and apply at every step.

1. **Read-only.** Never call a mutating API. Recommend the fix; never apply it. State the exact CLI
   command or IaC change and let the user run it.
2. **Never disclose secret material.** Report keys, tokens, and connection strings by **key name
   only** — never the value. Evaluation datasets may contain sensitive content; summarize patterns,
   do not echo raw content.
3. **Evidence or silence.** Every finding must cite the concrete value — the eval-job status, the
   score vs baseline, or the finish-reason distribution. Distinguish "measured zero" from "no data
   reported".
4. **A check-id on every finding.** Each finding references a catalog `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings.
5. **Never invent a threshold.** Severities come from the catalog. A quality score bar is almost
   always `workload-specific`; the finish-reason >10pp bar is `derived`. Report observations
   accordingly unless the operator has set a number.
6. **Bound the work and disclose what you skipped.** State which regions, resources, or checks you
   did not cover, and why — especially whether the region supports Bedrock evaluation.
7. **Decision-critical content is inline on purpose — never move it out.** The investigation steps,
   the finish-reason decision rule (`stopReason` is not a metric; resolve the log group, query it,
   report **both** shares, and claim no measurement without a query), the verifiable-versus-not
   boundary, the output contract, the per-phrase routing table under `## When to Use`, the
   upgraded-negative phrasing table, the severity scale and the read-only + no-`ApplyGuardrail` rule
   are inline **by design**. Do not relocate them into `references/` to save tokens: reference
   fetches do fail at runtime, and when they do, an honest answer must still be reachable from this
   file alone.
8. **Make reference loss loud.** On an `Error fetching resource`, or any failed reference read:
   retry that **single** path once, on its own — never batched with another path. If it fails again,
   continue from the inline content and **name the failed path in the output along with what you
   could not cite because of it**. Never retry in a loop and never leave the failure unmentioned.
9. **Any delegation asks for the seven findings columns.** When you hand evidence-gathering to a
   sub-agent, the prompt you send names the columns you expect back — otherwise you get exactly the
   columns you happened to mention. The discriminating case is this skill's own: the delegation that
   named the severity column got severities back and, having not named the doc column, got **zero**
   citations back. The column written into the payload is the column that returns.

   `| check-id | Severity | Observed value | Window | Source API | Remediation owner | AWS doc |`

   `assets/delegation-payload.json` is that prompt, finished: read it, fill the four `<…>`
   placeholders (`task`, `context`, `resources`, `timeframe`), send it unchanged. If it will not
   fetch (Guardrail 8), the column list above plus these constraints is the whole of it. Severities
   are the catalog's, never improvised: `LLM-EVAL-001` CRITICAL, `-002` HIGH, `-003` MEDIUM,
   `-004` MEDIUM, `-005` MEDIUM, `-006` MEDIUM, `-007` HIGH, `-008` MEDIUM, `-009` MEDIUM,
   `-010` MEDIUM, `-011` LOW, `-012` HIGH, `-013` HIGH, `-014` MEDIUM. `Observed value` begins with
   `measured <value>` / `no-datapoints` / `not-queried`; `AWS doc` is a `https://docs.aws.amazon.com/…`
   URL; before reporting API errors ruled out, query **both** `InvocationClientErrors` and
   `InvocationServerErrors`; anything unconfirmable from an AWS API — above all whether evaluation is
   pipeline-triggered — comes back as an explicit "cannot be confirmed from AWS APIs" caveat on its
   row, never as a confirmed negative; read-only APIs only and `bedrock:ApplyGuardrail` is never
   called.

   **On the return leg, reconcile — do not rewrite.** Carry every row forward with its cells as
   returned; keep the three-state token **verbatim** (a model with no invocations in the baseline
   window was not measured clean, it was not measured at all); **a severity may not be changed**;
   caveats travel with their row and may never be upgraded into an assertion that the thing does not
   exist; the `Remediation owner` cell is handed over by name. Name any difference as
   `dropped: <row or cell> — because <reason>`.

## The output contract

Kept **inline on purpose** (see `## Guardrails` item 7). Stated once, here. Every answer on this
skill's path ends with a `Findings` block, one line per signal:

```
Findings
<check-id> (<SEVERITY>) — <measured <value> | no-datapoints | not-queried> — <window> — <source API> — owner:<skill> — <doc URL>
```

- **Every check-id also appears inside a sentence**, with its severity and value: "no evaluation
  job has run in 90 days, which is LLM-EVAL-001 (CRITICAL)". A block can be dropped when the answer
  is summarized; a sentence usually survives.
- The **observed-value field begins with one of three literal tokens** — `measured `,
  `no-datapoints`, `not-queried`. Never a bare number; "zero", "none", "clean", "no errors" are not
  tokens. The **severity is the catalog's**, unchanged.
- Every row names its **`<source API>`**, carries **`owner:<skill>`** for the skill that owns the
  remediation, and a **`https://docs.aws.amazon.com/…` URL**.
- Where a sub-agent returned rows, the block is **transcribed from its table, not summarised.**
  Re-wording a cell is dropping it — `no-datapoints` rendered as "showed nothing" or "was clean" is
  a dropped row, and adding a health conclusion on top of it ("so this isn't an AWS-side issue")
  converts an absent signal into a measurement that was never taken. The gatherer's **gap rows
  travel too**: its unexplained record count, its self-declared shallow pass, the API it was denied.
  An answer opening "the telemetry is unambiguous" while its own gatherer wrote "shallow pass" has
  deleted a row in a different column, and the verdict being right does not repair it. Name any
  difference as `dropped: <row or cell> — because <reason>`.
- An **unconfirmability caveat travels on its row** — a `cannot be confirmed from AWS APIs` row keeps
  that text rather than being quietly resolved into a negative.

**Negative claims are source-bound.** This is the recorded hard-gate failure on the truncation
prompt: the gatherer wrote `filter ispresent(errorCode) over the full incident window → 0 records` —
bounded, named and true — and the answer wrote `zero API errors in the window`, which was false of
the account, because a planted `ValidationException` sat inside that window and the metric was never
queried.

- An unqualified "zero API errors", "no errors in the window", "nothing failing", "no drift" may
  **not** appear in the prose. A negative lives in a `Findings` line, which forces the token, the
  window and the source API onto the same line as the claim.
- A signal you did not query is `not-queried` — the claim is that you did not look, never that there
  was nothing there. Listing a metric in `cloudwatch:ListMetrics` is **not** querying it.
- **"Ruled out errors" requires both metric reads, named.** Read `InvocationClientErrors` **and**
  `InvocationServerErrors` from `AWS/Bedrock` over the stated window, each with its own row. A log
  scan alone cannot carry it: the invocation log does not capture pre-flight rejects, so `0 records`
  is a fact about the log.

## What You Can and Cannot Verify from AWS APIs

Be precise about the boundary. Two of the three questions above are answerable from AWS read-only
APIs; one is not, and claiming otherwise is a fabricated finding.

| Question | Verifiable from AWS APIs? | How |
|---|---|---|
| Is quality measured at all? | **Yes** | `ListEvaluationJobs` / `GetEvaluationJob` |
| Did quality regress? | **Yes** | eval scores vs baseline, finish-reason distribution, token metrics |
| Is evaluation wired into CI/CD? | **No** | Pipeline definitions live in GitHub Actions, GitLab CI, CodePipeline, or Jenkins. No Bedrock API exposes the trigger that started an evaluation job. |

For **LLM-EVAL-002** (evaluation not automated), you can observe a *proxy* — whether evaluation jobs
appear on a regular cadence and whether their names or tags look machine-generated — but you cannot
confirm the pipeline wiring. So report it this way:

> I can see N evaluation jobs, the most recent on `<date>`. I **cannot** confirm from AWS APIs
> whether these are triggered automatically by a pipeline or run by hand — no Bedrock API exposes the
> trigger. To confirm, check for an evaluation step in your CI/CD definition
> (`.github/workflows/`, `buildspec.yml`, or the CodePipeline stage list).

Never state that evaluation "is not automated" as a finding when what you actually observed is an
absence of evidence either way. Say which it is.

## Router

Which evaluation call to make is in `references/collection-reference.md`; which log group, field,
query and metric carry the quality signals is in `references/metrics-and-logs.md`. Load both with
any row.

| Operator says | First read | Load |
|---|---|---|
| Do we have evals, is quality measured at all | `ListEvaluationJobs` (confirm regional support first) | `references/checks-evaluation.md` (LLM-EVAL-001), `references/api-quirks.md` |
| Is there a quality gate before deploy, regression gate on promotion | Candidate eval score vs established baseline | `references/checks-evaluation.md` (LLM-EVAL-007) |
| Do evals run automatically or by hand | Eval-job cadence and names as a proxy; CI/CD cannot be confirmed via API | `references/checks-evaluation.md` (LLM-EVAL-002) |
| Our eval job failed, did it ever re-run | `GetEvaluationJob` status and failure reason | `references/checks-evaluation.md` (LLM-EVAL-011) |
| Output is being cut off, responses are truncated | `GetModelInvocationLoggingConfiguration`, then the `stopReason` distribution over the resolved log group, current vs baseline window | `references/metrics-and-logs.md` (§1-§3), `references/finish-reason-analysis.md` (LLM-EVAL-012) |
| We can't see truncation, is anything watching finish reasons | `logs:DescribeMetricFilters` for `{ $.stopReason = "max_tokens" }` on the invocation log group | `references/metrics-and-logs.md` (§5), `references/finish-reason-analysis.md` (LLM-EVAL-013) |
| Answers got longer, did quality drop | `OutputTokenCount` against flat `Invocations` — a precursor, not a truncation measurement | `references/metrics-and-logs.md` (§4), `references/finish-reason-analysis.md` (LLM-EVAL-014) |
| How do I A/B compare two models | Candidate vs incumbent on the identical dataset and metrics | `references/checks-evaluation.md` (LLM-EVAL-006) |
| We need human evaluation for tone/helpfulness | Presence of a human-based evaluation job | `references/checks-evaluation.md` (LLM-EVAL-004) |
| Is the RAG path's retrieval quality measured | A retrieve / retrieve-and-generate evaluation job | `references/checks-evaluation.md` (LLM-EVAL-009) |

## Investigation Procedure

Work the steps in order. Do not skip a step; check each off as you complete it.

- [ ] Step 1: Understand the question and establish scope, confirming regional evaluation support first
- [ ] Step 2: Collect evaluation state — jobs, datasets, status, scores
- [ ] Step 3: Evaluate against the check catalog and assign severities
- [ ] Step 4: Examine the finish-reason distribution for truncation drift
- [ ] Step 5: Synthesize — answer the question or produce the report

### Step 1 — Understand the question and establish scope

Restate the goal in one line. Decide region(s) and which models/jobs are in play. **Confirm the
region supports Bedrock evaluation first** — evaluation support varies by region
(`references/api-quirks.md` §2). Default to the caller's current region and say so.

### Step 2 — Collect evaluation state

Using the EVAL section of `references/collection-reference.md`, list and get evaluation jobs, their
datasets, status, and scores. An **empty `ListEvaluationJobs` in a region that does not support
Bedrock evaluation is NOT a CRITICAL** — report INFO/advisory. In a region that *does* support it,
an empty list means no evaluation has ever been run (CRITICAL LLM-EVAL-001).

### Step 3 — Evaluate against the catalog

Walk `references/checks-evaluation.md`, applying each detection rule: no evaluation ever run
(LLM-EVAL-001), no regression gate (LLM-EVAL-007), eval not in CI/CD (LLM-EVAL-002), a failed job
(LLM-EVAL-011), and a quality drop vs baseline. Record each triggered check with its `check-id`,
severity, exact observed value, remediation, and AWS-doc citation.

### Step 4 — Examine the finish-reason distribution

For a quality regression, examine the **finish-reason distribution** — a shift from `end_turn`
toward `max_tokens` is an early regression indicator (LLM-EVAL-012); check whether the metric filter
even exists (LLM-EVAL-013) and whether `OutputTokenCount` is rising with flat `Invocations`
(LLM-EVAL-014). Collect it per `references/metrics-and-logs.md`: probe
`GetModelInvocationLoggingConfiguration`, query the log group it names over the incident window
**and** a comparable earlier window, and report both shares. See
`references/finish-reason-analysis.md` for what the shift means. Record each triggered check in the
findings table with its `check-id`, severity, exact observed value, window, source API and AWS-doc
citation.

### Step 5 — Synthesize

For an incident, lead with the root cause (failed job vs genuine quality drop vs truncation drift)
and the highest-impact action, with the exact read-only command to confirm. For a review, give a
prioritized summary (CRITICAL first — no evaluation ever run). Disclose what you did not cover,
especially regional evaluation support. When a report is requested, follow
`assets/evaluation-report-template.md`.

## Before You Present — Validate Your Own Output

Before presenting any answer or report, verify each item below:

- [ ] **Scan the draft for an upgraded negative, sentence by sentence.** This is a word-level check,
  not a sentiment check, because the failure it catches is a rewrite that happens while tightening
  prose: an absence of evidence becomes an assertion of absence. For every claim that something is
  not there, the evidence is either a positive observation or an absence — and if it is an absence,
  the sentence must say so in those words. Enumerated, because "frame it as what you observed" was
  already stated twice in this file and lost anyway:

  | FORBIDDEN as written | Required instead |
  |---|---|
  | "no regression gate exists" / "there is no gate" | "I found no evidence of a regression gate; a gate lives in pipeline config, which no Bedrock API exposes — check `<where>`" |
  | "evaluation is not automated" / "it's run by hand" | "N jobs, most recent `<date>`; whether a pipeline triggered them **cannot be confirmed from AWS APIs** — check `.github/workflows/`, `buildspec.yml`, or the CodePipeline stage list" |
  | "the infrastructure isn't wired up" / "there's no way to prove it today" | "the signals that would prove it are not reachable from AWS APIs; here is what I did observe, and here is where to look" |
  | "model X is clean over the same window" where X had no baseline invocations | "model X: `no-datapoints` in the baseline window — not measured clean, not measured at all" |

  The right-hand column is longer on purpose. If the gatherer attached an unconfirmability caveat to
  a row, that caveat is **not** editorial padding and removing it is a dropped row under Guardrail
  9's return leg. A team told as fact that its evaluation pipeline does not exist, on
  evidence that cannot establish it, gets a remediation list that may be entirely wrong.
- [ ] **No unqualified negative survives in the prose.** Search the draft for "zero API errors", "no
  errors", "nothing failing", "no drift", "no server-side signal". Each one either moves into a
  `Findings` row with its token, window and source API, or becomes `not-queried` because you did not
  read it. Before any "ruled out errors", confirm **both** `InvocationClientErrors` **and**
  `InvocationServerErrors` were queried and each has its own row — a `filter ispresent(errorCode)`
  log scan does not cover pre-flight rejects and cannot carry the claim, and a metric seen only
  inside a `ListMetrics` enumeration was never queried.
- [ ] **Every gatherer gap row survived the copy.** Search the draft for "unambiguous", "clear",
  "conclusive", "proven" and check each one against what the gatherer actually said about its own
  depth: an unexplained record count, a share of the window it could not account for, a
  self-declared shallow pass, a next step it listed as not yet done, an onset it could not date.
  Each of those is a row in the block, not optional context, and a correct verdict does not license
  dropping it.
- [ ] **No raw AWS account id appears anywhere in the answer.** Search the draft for a bare 12-digit
  number; the account is already identified by the agent space, so mask the ARN segment as
  `<account>`.
- [ ] **Every finding carries its `check-id`, its catalog `Severity` in the same row, and a
  `https://docs.aws.amazon.com/…` URL.** Ids and severities come from
  `references/checks-evaluation.md` and must match what was actually observed. A severity collected
  into a trailing summary is detached and does not count.
- [ ] An empty `ListEvaluationJobs` was interpreted against regional support — reported INFO/advisory
  where the region lacks Bedrock evaluation, CRITICAL (LLM-EVAL-001) only where it supports it.
- [ ] A claimed finish-reason shift cites **both** the current share and the baseline share, not just
  one number.
- [ ] No threshold was invented. The >10pp finish-reason threshold is marked **derived**; anything
  AWS does not publish is INFO and marked **workload-specific**.
- [ ] "No datapoints" was not reported as a measured zero.
- [ ] Scope not covered is disclosed, especially regional evaluation support.
- [ ] **Any reference path that failed to load is named in the output**, with what could not be
  cited because of it.
- [ ] **The `Findings` block was transcribed from the gatherer's table, not written from your
  reading of it.** Put the two side by side and compare row counts and columns, not impressions: if
  the gatherer's table has 7 ids and the draft has 0, the draft re-authored instead of copying and
  must be redone from the table. Every row, cell, three-state token, severity and caveat either
  appears or is printed as `dropped: <row or cell> — because <reason>`.
- [ ] **The terminal `Findings` block is present whether or not a report was asked for.** A
  conversational paragraph with no block is not a short answer, it is an incomplete one: measured
  across 91 captured answers, **no answer under 1,000 characters carried a single check-id (0 of
  40)**, because a paragraph cannot hold a findings table. Shorten the prose, never the block.
  `assets/evaluation-report-template.md` is the long form of the same shape, for when a full written
  report is wanted.

If any item cannot be satisfied, say so in the output rather than dropping it.

## Common wrong answers

- "Latency and error rates are healthy, so quality is fine." A rising share of `max_tokens` finish reasons is a quality regression that is invisible to latency, error, and invocation metrics — outputs are being cut off mid-answer. Trend the `stopReason` distribution (LLM-EVAL-012), not just the default `AWS/Bedrock` metrics.
- "An evaluation job exists, so quality is gated." A job existing is not a job that runs on every change, and running is not the same as blocking a regression. Confirm the automation proxy (LLM-EVAL-002) and whether a promotion gate actually fails on a score drop (LLM-EVAL-007).
- "The automated score is high, so the model is good." Model-as-judge and automated metrics have documented blind spots and are not proof of quality for a high-stakes, subjective, or customer-facing path. Add a human evaluation dimension (LLM-EVAL-004) and safety metrics (LLM-EVAL-010) before trusting a single number.
- "`ListEvaluationJobs` is empty, so no evaluation has ever run — CRITICAL." Bedrock evaluation is region-gated. In a region that does not support it the list is empty or errors regardless of maturity; confirm regional support first and report INFO/advisory, not LLM-EVAL-001 (`references/api-quirks.md` §2).
- "`max_tokens` is climbing, so just raise `maxTokens`." That treats the symptom. The usual cause is prompts growing and crowding the output budget, or a model-version change in generation length — check prompt length and recent deployments before changing the cap (`references/finish-reason-analysis.md`).
- "No datapoints on the finish-reason metric means zero truncation." No datapoints usually means no traffic or the metric was never emitted in that window, not a measured zero (`references/api-quirks.md` §10). Distinguish "measured zero" from "nothing reported" before calling it healthy.
- "I can confirm from AWS APIs that evaluation is not automated." No Bedrock API exposes the trigger that started an eval job. You can observe a cadence proxy, but CI/CD wiring lives in GitHub Actions, CodePipeline, or Jenkins — report the absence of evidence, not a confirmed negative.

## Severity Definitions

Severities are assigned by the catalog, not improvised. SLAs are **operational guidance (derived)**.

| Severity | Meaning | Example | Response SLA (derived) |
|---|---|---|---|
| **CRITICAL** | No quality safety net on a production GenAI path | No evaluation ever run (LLM-EVAL-001) in a region that supports evaluation | Immediate — same day |
| **HIGH** | Serious quality risk likely to ship a regression | No regression gate before promotion (LLM-EVAL-007); finish-reason shift to `max_tokens` (LLM-EVAL-012); no metric filter on `stopReason` (LLM-EVAL-013) | Days |
| **MEDIUM** | Meaningful gap vs best practice | Evaluation run manually, not in CI/CD (LLM-EVAL-002); `OutputTokenCount` rising with flat `Invocations` (LLM-EVAL-014) | Next sprint |
| **LOW** | Minor hardening or tidiness | A failed/stopped eval job never re-run (LLM-EVAL-011); eval dataset tidiness / coverage gaps of limited blast radius | Backlog |
| **INFO** | Observation with no AWS-published threshold | Quality-score bar is workload-specific; evaluation unsupported in region (advisory) | Document / monitor |

## Error Handling

Before interpreting any response, consult `references/api-quirks.md`. The highest-stakes trap for
this domain:

- **Region-gated features (§2).** An empty `ListEvaluationJobs` in a region that does **not** support
  Bedrock evaluation is *not* a CRITICAL "no evaluation ever run" finding — confirm regional support
  first, and otherwise report INFO/advisory. This is the single most common false positive in the
  evaluation domain.

Operational failures: on **AccessDenied**, report the specific API and resource you could not read,
continue, and list the gap. On a **region unsupported for evaluation**, record it as a disclosed
assumption, not a finding. On **throttling of describe/list calls**, back off and paginate. On
**ambiguous scope**, ask or default to the caller's current region and say so.

## Appendix — Reference Links

Check catalog (each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc`):

- `references/checks-evaluation.md` — LLM-EVAL-001..011 (the LLMOps quality pillar), the
  finish-reason regression signal (LLM-EVAL-012), the missing metric filter (LLM-EVAL-013), and the
  output-token precursor (LLM-EVAL-014)

Operational references:

- `references/finish-reason-analysis.md` — the finish-reason drift analysis: `stopReason` values,
  metric filter, derived >10pp threshold, Logs Insights distribution query, correlated signals
- `references/collection-reference.md` — read-only API calls (EVAL section) and the fields/checks they feed
- `references/metrics-and-logs.md` — the invocation-log group probe, the record schema and
  `stopReason` field path, the distribution query, and the `OutputTokenCount`/`Invocations`
  precursor pair
- `references/api-quirks.md` — misleading-response traps (esp. §2 region-gated evaluation)

Output template:

- `assets/evaluation-report-template.md` — the consolidated evaluation report format (header, quality
  posture, coverage, findings, finish-reason distribution, trend, and scope not covered)

AWS documentation:

- [Bedrock model evaluation](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html)
- [Model evaluation jobs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation-jobs.html)
- [RAG evaluation](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html)
- [Model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [CloudWatch Logs metric filters](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html)
- [Bedrock supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
