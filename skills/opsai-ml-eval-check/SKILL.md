---
name: opsai-ml-eval-check
description: Diagnose and review model output quality and evaluation jobs on Amazon Bedrock and SageMaker. Use
  this skill when answers got worse or a model may hallucinate more, responses are cut off or end on
  max_tokens, the same prompt gives different answers, a Bedrock CreateEvaluationJob or a Bedrock RAG
  evaluation job for a knowledge base fails or needs interpreting, a SageMaker Nova evaluation recipe or
  LLM-as-judge job fails or hits an instance limit, judge scores swing, model versions cannot be compared,
  or a fine-tuned model is about to ship unevaluated, and when someone asks whether quality is measured,
  automated and gated before production or how to compare two models. Inside a live incident it still
  produces its own LLM-EVAL findings; live-failure triage decides where the fault sits, and without it the
  answer says the locus was not determined. Finish-reason checks read Bedrock invocation logs. Findings
  carry LLM-EVAL and LLM-SM-EVAL check-ids with an AWS-doc citation, from read-only APIs.
metadata:
  author: jmadhuki, ankitsri-aws
  version: "1.0.1"
  tier: "aws-support-managed"
  summary: "Reviews whether model output quality is measured, automated and gated, and diagnoses Bedrock (including RAG) and SageMaker evaluation jobs."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, Amazon SageMaker AI, Amazon S3, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Observability"
---

# OpsAI — ML evaluation and model quality

This is the **OpsAI quality / Continuous-Tuning pillar**. Everything else in the Bedrock and SageMaker operations surface tells you whether the model is *configured*, *reachable*, *guarded*, and *observable*. This skill answers the three questions that actually decide whether a GenAI workload is any good:

1. **Is model quality measured at all?** (Has any evaluation ever run?)
2. **Is it measured automatically?** (Is evaluation wired into CI/CD, or run by hand and hope?)
3. **Can a regression reach production?** (Is there a gate that blocks a quality drop before promotion?)

It covers three evaluation paths and keeps them apart: **Bedrock model evaluation** (`CreateEvaluationJob`, `applicationType` `ModelEvaluation`, automated or human), **Bedrock RAG evaluation** (`applicationType` `RagEvaluation` on a knowledge base), and **SageMaker-side evaluation** (a Nova eval recipe or an LLM-as-judge run as a SageMaker training job). It also owns quality gates, regression detection and finish-reason drift.

This skill works on its own: everything it needs is in its `references/` and `assets/` files. Read-only APIs only.

Every assessment is grounded in the check catalog [checks-evaluation.md](references/checks-evaluation.md) (load it before assigning any check-id or severity). Each check carries a stable `check-id`, a severity, a detection rule, a remediation, and an AWS-doc citation. You never invent a threshold: if AWS publishes no number, the catalog marks it `workload-specific` (or `derived` for an operational default) and you report it accordingly.

The read-only calls are the `bedrock` evaluation describe/list/get calls and the SageMaker training-job describe calls in [collection-reference.md](references/collection-reference.md) (load with any Router row), and the invocation-log and metric reads in [metrics-and-logs.md](references/metrics-and-logs.md) (load before any log query or metric read). It never mutates a resource. `bedrock:ApplyGuardrail` is not a collection call, is billable, and is never called.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## When to Use

Activate this skill when the user:

- Reports an **evaluation incident** — an eval job failed, or **"did quality drop"** / a model **quality regression**.
- Asks **"is my model still good"**, or how to measure quality — **A/B compare models** or prompt versions, **human evaluation** setup.
- Asks how to add a **quality gate** / **regression gate** to model promotion, or wire evaluation into CI/CD.
- Asks about **OpsAI maturity** relative to the evaluation pillar.
- Wants a **review of the evaluation posture** — "do we evaluate our models?", "is there a quality gate before promotion?".
- Reports **outputs getting truncated** / **max_tokens truncation**, or raises a **finish reason** distribution shift (`end_turn` → `max_tokens`) as a suspected regression signal.
- Reports that a **Bedrock RAG evaluation job for a knowledge base fails**, or its retrieval/grounding scores need interpreting.
- Asks about a **SageMaker-side evaluation / benchmark job** — a Nova eval recipe or LLM-as-judge run as a SageMaker job.
- Reports a **customized or fine-tuned artifact promoted or deployed with no eval run** against it (LLM-SM-EVAL-001).
- Reports a **SageMaker evaluation job that Failed** — a bad eval-dataset path, a malformed recipe, or a judge-model access error (LLM-SM-EVAL-002).
- Asks whether **SageMaker eval output was published or retained** for run-over-run comparison (LLM-SM-EVAL-003).
- Reports a **break-fix symptom** on a SageMaker-side evaluation — a job that cannot start on an instance limit, judge scores that swing between runs, or a domain metric no built-in covers.

**Routing triggers — the literal phrasings, each with the rule that decides it.** A keyword list did not land; these are the phrasings as users actually write them, with the deciding rule beside each, because the two prompts below selected **no skill at all** on a measured run and every check-id and citation went with it. Any question of these shapes selects **this** skill, whether or not the words evaluation, quality or finish reason appear anywhere in it:

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
| "our RAG evaluation job failed" / "what do the RAG eval scores mean" | a Bedrock evaluation job with `applicationType` `RagEvaluation` | **this skill** (Bedrock RAG path) |
| "our Nova eval recipe / LLM-as-judge job failed" / "judge scores swing" | a SageMaker-side evaluation run as a training job | **this skill** (SageMaker path) |

A question combining two of these rows — "the answers got worse and we cannot prove it, and some replies look cut off" — is **one** question for this skill with two evidence tracks, not a reason to hand it elsewhere or to leave it unrouted.

Truncation and finish-reason work is **this** skill's — but a truncation question whose evidence turns out to be an API error rather than a `max_tokens` stop reason has an error half that belongs to the live-failure triage area (Related skills); keep the truncation half here.

**Corrupted output is a fault, not a quality regression.** Garbled text, wrong-language or encoding-broken output, or nonsense that starts **abruptly** and affects **only part of the traffic** (one region, one instance, one endpoint variant) is the shape of a serving or infrastructure fault. An evaluation job would score it badly but cannot diagnose it. Say so, name the evidence that separates the two (abrupt onset, partial blast radius, no model or prompt change), and do not prescribe an evaluation: the fault locus belongs to the live-failure triage area (Related skills); if that skill is not available, say the locus was not determined and recommend AWS Support for a managed model. A gradual, traffic-wide drift in answer quality stays here.

## Role in an investigation

Inside a live incident this skill still produces its own LLM-EVAL findings rows for output-quality depth. Where the fault sits (provider, infrastructure or application) is decided by the live-failure triage area: if that skill is in your available skills it owns the locus; if not, state that the fault locus was not determined and recommend it once under Related skills. The root cause and the operator-facing answer belong to the host investigation.

Outside an investigation it leads as it always has: an advisory question about how to evaluate, a failed evaluation job, or a standing review of whether quality is measured and gated, is this skill's from the first turn.

**Hosting caveat.** The finish-reason work (LLM-EVAL-012, -013, -014) reads `stopReason` from **Bedrock model invocation logs**. There is no equivalent for a SageMaker endpoint or a self-hosted model unless the workload emits the field itself. On those hostings report the check as `not-applicable` with the reason, and name what the workload would have to emit — never map a Bedrock log field onto a system that does not produce it. SageMaker *evaluation jobs* are in scope (the LLM-SM-EVAL path); SageMaker *endpoint* output has no `stopReason`, so its finish-reason checks are `not-applicable`.

## Scope Model

| Family | Code | Resources | Catalog |
|---|---|---|---|
| Bedrock evaluation | `LLM-EVAL` | Bedrock model/RAG/human evaluation jobs, datasets, regression gates, promotion criteria, A/B comparison, finish-reason drift — the OpsAI quality pillar | [checks-evaluation.md](references/checks-evaluation.md) — load before assigning any check-id or severity |
| SageMaker-side evaluation | `LLM-SM-EVAL` | Nova eval recipes and LLM-as-judge jobs run as SageMaker training jobs, their output retention, and evaluation before promotion of a customized model | [checks-evaluation.md](references/checks-evaluation.md) (SageMaker-side section) |

Assess only what the question or incident touches.

## Finish-Reason Drift

A first-class capability of this skill, not a footnote. The finish-reason distribution is **a small check with outsized value** — an early, otherwise-invisible indicator of quality regression that no AWS alarm watches by default. A shift from `end_turn` (natural completion) toward `max_tokens` (truncation) means outputs are being cut off — because prompts grew and crowded the output budget, because `maxTokens` was reduced, or because a model version changed generation length. It **precedes visible quality complaints by hours or days.**

When a quality regression is suspected, examine the finish-reason distribution early. The full analysis — the `stopReason` field values, the metric filter `{ $.stopReason = "max_tokens" }`, the derived >10pp alarm threshold, the Logs Insights distribution query, and the correlated signals (`OutputTokenCount` spikes, `InvocationLatency` rising, truncation complaints) — lives in [finish-reason-analysis.md](references/finish-reason-analysis.md) (load when a truncation or finish-reason shift is in question).

**`stopReason` is not a CloudWatch metric.** The distribution can only be measured from the Bedrock invocation logs, so resolve the log group from `bedrock:GetModelInvocationLoggingConfiguration` before reasoning about truncation — the group name is a customer choice and must never be assumed. The collection mechanics (that probe, the record schema and the `stopReason` field path, the distribution query, and the fact that `OutputTokenCount`/`Invocations` are a *precursor* and not a measurement) are in [metrics-and-logs.md](references/metrics-and-logs.md) (load before querying the invocation logs).

Together these back three checks: **LLM-EVAL-012** (the shift itself), **LLM-EVAL-013** (no metric filter, so the shift is invisible), and **LLM-EVAL-014** (`OutputTokenCount` rising with flat `Invocations`, the correlated precursor).

## Break-fix first

When the user states a specific error or symptom on an evaluation job, answer that symptom before any review. Decide which service ran the job first (Step 1).

- **Failed Bedrock job (model or RAG).** Read `bedrock:GetEvaluationJob` `status` and `failureMessages` first (if it is denied, use the `ListEvaluationJobs` summary `status` and report the failure messages as not read); confirm the region supports Bedrock evaluation ([api-quirks.md](references/api-quirks.md) §2); then check the usual causes: dataset format and S3 location, the service role's access to the input and output buckets and any KMS key, the task type and metric configuration. A failed job never re-run is LLM-EVAL-011.
- **Failed SageMaker eval job.** Load [known-causes.md](references/known-causes.md) whenever the user names an error or symptom; match it to a section, check the cited AWS page, and give the cause, how to confirm it, and the fix.
- Answer in this turn. Do not end with only a plan or "I'll report back"; if you also inspect the account, include what you found and what you could not read.
- A known cause tied to an `LLM-EVAL-*` or `LLM-SM-EVAL-*` id is a finding with the catalog severity. A cause with no id is guidance with its AWS citation; never invent an id for it.

## Guardrails

These rules are non-negotiable and apply at every step.

1. **Read-only.** Never call a mutating API — in particular `CreateEvaluationJob`, `StopEvaluationJob`, `CreateTrainingJob` or `StopTrainingJob` (a SageMaker-side eval runs as a training job). Recommend the fix; never apply it. State the exact CLI command or IaC change and let the user run it.
2. **Never disclose secret material.** Report keys, tokens, and connection strings by **key name only** — never the value. Evaluation datasets may contain sensitive content; summarize patterns, do not echo raw content, and refer to eval-dataset content by reference only.
3. **Evidence or silence.** Every finding must cite the concrete value — the eval-job status, the score vs baseline, or the finish-reason distribution. Distinguish "measured zero" from "no data reported".
4. **A check-id on every finding.** Each finding references a catalog `check-id` and carries that check's severity and AWS-doc citation. No freelance findings.
5. **Never invent a threshold.** Severities come from the catalog. A quality score bar is almost always `workload-specific`; the finish-reason >10pp bar is `derived`. Report observations accordingly unless the operator has set a number.
6. **Bound the work and disclose what you skipped.** State which regions, resources, or checks you did not cover, and why — especially whether the region supports Bedrock evaluation.
7. **Decision-critical content is inline on purpose — never move it out.** The investigation steps, the finish-reason decision rule (`stopReason` is not a metric; resolve the log group, query it, report **both** shares, and claim no measurement without a query), the verifiable-versus-not boundary, the output contract, the per-phrase routing table under `## When to Use`, the upgraded-negative phrasing table, the severity scale and the read-only + no-`ApplyGuardrail` rule are inline **by design**. Do not relocate them into `references/` to save tokens: reference fetches do fail at runtime, and when they do, an honest answer must still be reachable from this file alone.
8. **Make reference loss loud.** On an `Error fetching resource`, or any failed reference read: retry that **single** path once, on its own — never batched with another path. If it fails again, continue from the inline content and **name the failed path in the output along with what you could not cite because of it**. Never retry in a loop and never leave the failure unmentioned.
9. **Any delegation asks for the seven findings columns.** When you hand evidence-gathering to a sub-agent, the prompt you send names the columns you expect back — otherwise you get exactly the columns you happened to mention. The discriminating case is this skill's own: the delegation that named the severity column got severities back and, having not named the doc column, got **zero** citations back. The column written into the payload is the column that returns.

   `| check-id | Severity | Observed value | Window | Source API | Owning area | AWS doc |`

   [delegation-payload.json](assets/delegation-payload.json) is that prompt, finished (load when delegating evidence-gathering): read it, fill the four `<…>` placeholders (`task`, `context`, `resources`, `timeframe`), send it unchanged. If it will not fetch (Guardrail 8), the column list above plus these constraints is the whole of it. Severities are the catalog's, never improvised: `LLM-EVAL-001` CRITICAL, `-002` HIGH, `-003` MEDIUM, `-004` MEDIUM, `-005` MEDIUM, `-006` MEDIUM, `-007` HIGH, `-008` MEDIUM, `-009` MEDIUM, `-010` MEDIUM, `-011` LOW, `-012` HIGH, `-013` HIGH, `-014` MEDIUM; `LLM-SM-EVAL-001` MEDIUM, `-002` HIGH, `-003` LOW, `-004` INFO. `Observed value` begins with `measured <value>` / `no-datapoints` / `not-queried`; `AWS doc` is a `https://docs.aws.amazon.com/…` URL; before reporting API errors ruled out, query **both** `InvocationClientErrors` and `InvocationServerErrors`; anything unconfirmable from an AWS API — above all whether evaluation is pipeline-triggered — comes back as an explicit "cannot be confirmed from AWS APIs" caveat on its row, never as a confirmed negative; read-only APIs only and `bedrock:ApplyGuardrail` is never called.

   **On the return leg, reconcile — do not rewrite.** Carry every row forward with its cells as returned; keep the three-state token **verbatim** (a model with no invocations in the baseline window was not measured clean, it was not measured at all); **a severity may not be changed**; caveats travel with their row and may never be upgraded into an assertion that the thing does not exist; the `Owning area` cell is handed over as written. Name any difference as `dropped: <row or cell> — because <reason>`.
10. **Never echo a raw AWS account ID.** Refer to the account by alias or as `the account under review`. If an ARN must be quoted as evidence, mask the account segment (`arn:aws:sagemaker:us-east-1:<account>:training-job/...`). The same applies to anything credential-shaped.

## The output contract

Kept **inline on purpose** (see `## Guardrails` item 7). Stated once, here. Every answer on this skill's path ends with a `Findings` block, one line per signal:

```
Findings
<check-id> (<SEVERITY>) — <measured <value> | no-datapoints | not-queried> — <window> — <source API> — owner:<area> — <doc URL>
```

- **Every check-id also appears inside a sentence**, with its severity and value: "no evaluation job has run in 90 days, which is LLM-EVAL-001 (CRITICAL)". A block can be dropped when the answer is summarized; a sentence usually survives.
- The **observed-value field begins with one of three literal tokens** — `measured `, `no-datapoints`, `not-queried`. Never a bare number; "zero", "none", "clean", "no errors" are not tokens. The **severity is the catalog's**, unchanged.
- Every row names its **`<source API>`**, carries **`owner:<area>`** for the area that owns the remediation, and a **`https://docs.aws.amazon.com/…` URL**.
- Where a sub-agent returned rows, the block is **transcribed from its table, not summarised.** Re-wording a cell is dropping it — `no-datapoints` rendered as "showed nothing" or "was clean" is a dropped row, and adding a health conclusion on top of it ("so this isn't an AWS-side issue") converts an absent signal into a measurement that was never taken. The gatherer's **gap rows travel too**: its unexplained record count, its self-declared shallow pass, the API it was denied. An answer opening "the telemetry is unambiguous" while its own gatherer wrote "shallow pass" has deleted a row in a different column, and the verdict being right does not repair it. Name any difference as `dropped: <row or cell> — because <reason>`.
- An **unconfirmability caveat travels on its row** — a `cannot be confirmed from AWS APIs` row keeps that text rather than being quietly resolved into a negative.

**Negative claims are source-bound.** This is the recorded hard-gate failure on the truncation prompt: the gatherer wrote `filter ispresent(errorCode) over the full incident window → 0 records` — bounded, named and true — and the answer wrote `zero API errors in the window`, which was false of the account, because a planted `ValidationException` sat inside that window and the metric was never queried.

- An unqualified "zero API errors", "no errors in the window", "nothing failing", "no drift" may **not** appear in the prose. A negative lives in a `Findings` line, which forces the token, the window and the source API onto the same line as the claim.
- A signal you did not query is `not-queried` — the claim is that you did not look, never that there was nothing there. Listing a metric in `cloudwatch:ListMetrics` is **not** querying it.
- **"Ruled out errors" requires both metric reads, named.** Read `InvocationClientErrors` **and** `InvocationServerErrors` from `AWS/Bedrock` over the stated window, each with its own row. A log scan alone cannot carry it: the invocation log does not capture pre-flight rejects, so `0 records` is a fact about the log.

## What You Can and Cannot Verify from AWS APIs

Be precise about the boundary. Two of the three questions above are answerable from AWS read-only APIs; one is not, and claiming otherwise is a fabricated finding.

| Question | Verifiable from AWS APIs? | How |
|---|---|---|
| Is quality measured at all? | **Yes** | `ListEvaluationJobs` / `GetEvaluationJob` |
| Did quality regress? | **Yes** | eval scores vs baseline, finish-reason distribution, token metrics |
| Was a SageMaker-side eval run against the artifact? | **Yes** | `DescribeTrainingJob` for the eval job and its results object under the output path |
| Is evaluation wired into CI/CD? | **No** | Pipeline definitions live in GitHub Actions, GitLab CI, CodePipeline, or Jenkins. No Bedrock API exposes the trigger that started an evaluation job. |

For **LLM-EVAL-002** (evaluation not automated), you can observe a *proxy* — whether evaluation jobs appear on a regular cadence and whether their names or tags look machine-generated — but you cannot confirm the pipeline wiring. So report it this way:

> I can see N evaluation jobs, the most recent on `<date>`. I **cannot** confirm from AWS APIs whether these are triggered automatically by a pipeline or run by hand — no Bedrock API exposes the trigger. To confirm, check for an evaluation step in your CI/CD definition (`.github/workflows/`, `buildspec.yml`, or the CodePipeline stage list).

Never state that evaluation "is not automated" as a finding when what you actually observed is an absence of evidence either way. Say which it is.

## Router

Which evaluation call to make is in [collection-reference.md](references/collection-reference.md); which log group, field, query and metric carry the quality signals is in [metrics-and-logs.md](references/metrics-and-logs.md). Load both with any row.

The table that maps what the operator says to the first read, the check-ids and the files to load is in [router.md](references/router.md). Read it before the first API call.

## Investigation Procedure

Work the steps in order. Do not skip a step; check each off as you complete it. Every step is best-effort: if an API is denied or a feature is unsupported in the region, record that signal as unavailable and continue.

- [ ] Step 1: Understand the question, pick the path and confirm regional support
- [ ] Step 2: Collect evaluation state for the path — jobs, datasets, status, scores
- [ ] Step 3: Evaluate against the catalog for the path and assign severities
- [ ] Step 4: Examine the finish-reason distribution (Bedrock hosting) for truncation drift
- [ ] Step 5: Synthesize — answer the question or produce the report

### Step 1 — Understand the question, pick the path and confirm regional support

Restate the goal in one line. Decide region(s) and which models/jobs are in play, then name the path you are on: **Bedrock CreateEvaluationJob** (model evaluation, automated or human), **Bedrock RAG evaluation job** (a knowledge base), **SageMaker eval recipe / LLM-as-judge**, **Quality posture review** (measured, automated, gated), or **Truncation** (finish reasons). A question can take more than one path; say which.

**Service check.** When a job is named, confirm which service ran it: `sagemaker:DescribeTrainingJob` for a recipe-driven job, `bedrock:GetEvaluationJob` for a Bedrock-native one ([api-quirks.md](references/api-quirks.md) §15). A Bedrock-native job presented as SageMaker is LLM-SM-EVAL-004 (INFO) and moves to the Bedrock path; it never gets LLM-SM-EVAL ids.

**Regional support.** For a Bedrock path, **confirm the region supports Bedrock evaluation first** — evaluation support varies by region ([api-quirks.md](references/api-quirks.md) §2). Default to the caller's current region and say so.

### Step 2 — Collect evaluation state for the path

**Bedrock (model and RAG).** Using the EVAL section of [collection-reference.md](references/collection-reference.md), list and get evaluation jobs (`ListEvaluationJobs`, `GetEvaluationJob`): `applicationType` (`ModelEvaluation` | `RagEvaluation`), datasets, status, `failureMessages`, and scores. An **empty `ListEvaluationJobs` in a region that does not support Bedrock evaluation is NOT a CRITICAL** — report INFO/advisory. In a region that *does* support it, an empty list means no evaluation has ever been run (CRITICAL LLM-EVAL-001).

**SageMaker.** Using the SM-EVAL section, read `ListTrainingJobs` / `DescribeTrainingJob` for the recipe job (`TrainingJobStatus`, `FailureReason`, eval-dataset S3 path, judge-model reference), the eval output prefix (`ListObjectsV2`, authorized by `s3:ListBucket`), and whether scores are published in `OpsAI/Evaluation` (`cloudwatch:ListMetrics`; absent datapoints are not a zero score, [api-quirks.md](references/api-quirks.md) §10).

### Step 3 — Evaluate against the catalog for the path

Walk [checks-evaluation.md](references/checks-evaluation.md) for the path you are on, applying each detection rule. Record each triggered check with its `check-id`, severity, exact observed value, remediation, and AWS-doc citation.

**Bedrock CreateEvaluationJob path.** No evaluation ever run (LLM-EVAL-001), stale dataset (LLM-EVAL-003), no human evaluation for subjective dimensions (LLM-EVAL-004), scores not published as metrics (LLM-EVAL-005), no A/B comparison (LLM-EVAL-006), no regression gate (LLM-EVAL-007), results not versioned (LLM-EVAL-008), no safety dimension (LLM-EVAL-010), and a quality drop vs baseline. A failed job: read `failureMessages`, name the cause (dataset format or S3 location, service-role or KMS access, task type or metric configuration), and raise LLM-EVAL-011 if it was never re-run.

**Bedrock RAG evaluation job path.** Confirm `applicationType` is `RagEvaluation` and name the knowledge base evaluated from `inferenceConfig` (`ragIdentifiers` is deprecated). Say whether it is a retrieve-only or a retrieve-and-generate evaluation, and read retrieval relevance and grounding metrics against the baseline run. A RAG/KB workload with model evaluation but no RAG evaluation is LLM-EVAL-009. A failed RAG job: read `failureMessages` and raise LLM-EVAL-011 if it was never re-run. KB ingestion or configuration problems behind a poor score belong to the Knowledge Bases / RAG area (Related skills).

**SageMaker eval recipe / LLM-as-judge path.** A customized artifact promoted with no eval run (LLM-SM-EVAL-001; registration or approval is not an eval run), a `Failed` eval job (LLM-SM-EVAL-002; match `FailureReason` to [known-causes.md](references/known-causes.md), load it for any named error), and output not retained or published for comparison (LLM-SM-EVAL-003). For swinging judge scores, read the judge's `*_stderr` and the `lower_rate` / `upper_rate` bootstrap bounds before calling a difference a regression. A Bedrock-native job presented here is LLM-SM-EVAL-004: switch to the Bedrock path.

**Is quality measured, automated and gated.** Question 1: LLM-EVAL-001 (after the regional check). Question 2: LLM-EVAL-002, reported with the proxy wording in *What You Can and Cannot Verify* — never as a confirmed negative. Question 3: LLM-EVAL-007 for Bedrock, LLM-SM-EVAL-001 for a customized SageMaker model. Use the verifiable-vs-not table for every claim about CI/CD.

### Step 4 — Examine the finish-reason distribution (Bedrock hosting)

For a quality regression, examine the **finish-reason distribution** — a shift from `end_turn` toward `max_tokens` is an early regression indicator (LLM-EVAL-012); check whether the metric filter even exists (LLM-EVAL-013) and whether `OutputTokenCount` is rising with flat `Invocations` (LLM-EVAL-014). Collect it per [metrics-and-logs.md](references/metrics-and-logs.md): probe `GetModelInvocationLoggingConfiguration`, query the log group it names over the incident window **and** a comparable earlier window, and report both shares. See [finish-reason-analysis.md](references/finish-reason-analysis.md) for what the shift means. Record each triggered check in the findings table with its `check-id`, severity, exact observed value, window, source API and AWS-doc citation. On a SageMaker endpoint or a self-hosted model, report these checks `not-applicable` with the reason (Hosting caveat).

### Step 5 — Synthesize

For an incident, lead with the root cause (failed job vs genuine quality drop vs truncation drift) and the highest-impact action, with the exact read-only command to confirm. Inside a live incident, the fault locus is the live-failure triage area's when that skill is available; otherwise state that the locus was not determined and recommend it once under Related skills. For a review, give a prioritized summary (CRITICAL first — no evaluation ever run). Disclose what you did not cover, especially regional evaluation support and any job, region or S3 prefix you could not read.

When a report is requested, load [evaluation-report-template.md](assets/evaluation-report-template.md) for the Bedrock path and the posture review, and [sagemaker-evaluation-report-template.md](assets/sagemaker-evaluation-report-template.md) (load when the report covers the SageMaker path). A question on both paths uses both, Bedrock first.

## Before You Present — Validate Your Own Output

Before presenting any answer or report, verify each item below:

- [ ] **Scan the draft for an upgraded negative, sentence by sentence.** This is a word-level check, not a sentiment check, because the failure it catches is a rewrite that happens while tightening prose: an absence of evidence becomes an assertion of absence. For every claim that something is not there, the evidence is either a positive observation or an absence — and if it is an absence, the sentence must say so in those words. Enumerated, because "frame it as what you observed" was already stated twice in this file and lost anyway:

  | FORBIDDEN as written | Required instead |
  |---|---|
  | "no regression gate exists" / "there is no gate" | "I found no evidence of a regression gate; a gate lives in pipeline config, which no Bedrock API exposes — check `<where>`" |
  | "evaluation is not automated" / "it's run by hand" | "N jobs, most recent `<date>`; whether a pipeline triggered them **cannot be confirmed from AWS APIs** — check `.github/workflows/`, `buildspec.yml`, or the CodePipeline stage list" |
  | "the infrastructure isn't wired up" / "there's no way to prove it today" | "the signals that would prove it are not reachable from AWS APIs; here is what I did observe, and here is where to look" |
  | "model X is clean over the same window" where X had no baseline invocations | "model X: `no-datapoints` in the baseline window — not measured clean, not measured at all" |

  The right-hand column is longer on purpose. If the gatherer attached an unconfirmability caveat to a row, that caveat is **not** editorial padding and removing it is a dropped row under Guardrail 9's return leg. A team told as fact that its evaluation pipeline does not exist, on evidence that cannot establish it, gets a remediation list that may be entirely wrong.
- [ ] **No unqualified negative survives in the prose.** Search the draft for "zero API errors", "no errors", "nothing failing", "no drift", "no server-side signal". Each one either moves into a `Findings` row with its token, window and source API, or becomes `not-queried` because you did not read it. Before any "ruled out errors", confirm **both** `InvocationClientErrors` **and** `InvocationServerErrors` were queried and each has its own row — a `filter ispresent(errorCode)` log scan does not cover pre-flight rejects and cannot carry the claim, and a metric seen only inside a `ListMetrics` enumeration was never queried.
- [ ] **Every gatherer gap row survived the copy.** Search the draft for "unambiguous", "clear", "conclusive", "proven" and check each one against what the gatherer actually said about its own depth: an unexplained record count, a share of the window it could not account for, a self-declared shallow pass, a next step it listed as not yet done, an onset it could not date. Each of those is a row in the block, not optional context, and a correct verdict does not license dropping it.
- [ ] **No raw AWS account id appears anywhere in the answer.** Search the draft for a bare 12-digit number; the account is already identified by the agent space, so mask the ARN segment as `<account>`.
- [ ] **No eval-dataset content is reproduced** — datasets, prompts and judge outputs are summarized or referenced, never echoed.
- [ ] **Every finding carries its `check-id`, its catalog `Severity` in the same row, an owning area, and a `https://docs.aws.amazon.com/…` URL.** Ids and severities come from [checks-evaluation.md](references/checks-evaluation.md) and must match what was actually observed. A severity collected into a trailing summary is detached and does not count.
- [ ] **The LLM-SM-EVAL-004 switch is applied** — a Bedrock-native job carries LLM-EVAL ids, never LLM-SM-EVAL ids.
- [ ] An empty `ListEvaluationJobs` was interpreted against regional support — reported INFO/advisory where the region lacks Bedrock evaluation, CRITICAL (LLM-EVAL-001) only where it supports it.
- [ ] A claimed finish-reason shift cites **both** the current share and the baseline share, not just one number.
- [ ] No threshold was invented. The >10pp finish-reason threshold is marked **derived**; anything AWS does not publish is INFO and marked **workload-specific**; a binary failed/absent state keeps its catalog severity.
- [ ] "No datapoints" was not reported as a measured zero.
- [ ] Scope not covered is disclosed, especially regional evaluation support.
- [ ] **Any reference path that failed to load is named in the output**, with what could not be cited because of it.
- [ ] **The `Findings` block was transcribed from the gatherer's table, not written from your reading of it.** Put the two side by side and compare row counts and columns, not impressions: if the gatherer's table has 7 ids and the draft has 0, the draft re-authored instead of copying and must be redone from the table. Every row, cell, three-state token, severity and caveat either appears or is printed as `dropped: <row or cell> — because <reason>`.
- [ ] **The terminal `Findings` block is present whether or not a report was asked for.** A conversational paragraph with no block is not a short answer, it is an incomplete one: measured across 91 captured answers, **no answer under 1,000 characters carried a single check-id (0 of 40)**, because a paragraph cannot hold a findings table. Shorten the prose, never the block. [evaluation-report-template.md](assets/evaluation-report-template.md) is the long form of the same shape (load when a full written report is wanted).

If any item cannot be satisfied, say so in the output rather than dropping it.

## Common wrong answers

- "Latency and error rates are healthy, so quality is fine." A rising share of `max_tokens` finish reasons is a quality regression that is invisible to latency, error, and invocation metrics — outputs are being cut off mid-answer. Trend the `stopReason` distribution (LLM-EVAL-012), not just the default `AWS/Bedrock` metrics.
- "An evaluation job exists, so quality is gated." A job existing is not a job that runs on every change, and running is not the same as blocking a regression. Confirm the automation proxy (LLM-EVAL-002) and whether a promotion gate actually fails on a score drop (LLM-EVAL-007).
- "The automated score is high, so the model is good." Model-as-judge and automated metrics have documented blind spots and are not proof of quality for a high-stakes, subjective, or customer-facing path. Add a human evaluation dimension (LLM-EVAL-004) and safety metrics (LLM-EVAL-010) before trusting a single number.
- "`ListEvaluationJobs` is empty, so no evaluation has ever run — CRITICAL." Bedrock evaluation is region-gated. In a region that does not support it the list is empty or errors regardless of maturity; confirm regional support first and report INFO/advisory, not LLM-EVAL-001 ([api-quirks.md](references/api-quirks.md) §2).
- "`max_tokens` is climbing, so just raise `maxTokens`." That treats the symptom. The usual cause is prompts growing and crowding the output budget, or a model-version change in generation length — check prompt length and recent deployments before changing the cap ([finish-reason-analysis.md](references/finish-reason-analysis.md)).
- "No datapoints on the finish-reason metric means zero truncation." No datapoints usually means no traffic or the metric was never emitted in that window, not a measured zero ([api-quirks.md](references/api-quirks.md) §10). Distinguish "measured zero" from "nothing reported" before calling it healthy.
- "I can confirm from AWS APIs that evaluation is not automated." No Bedrock API exposes the trigger that started an eval job. You can observe a cadence proxy, but CI/CD wiring lives in GitHub Actions, CodePipeline, or Jenkins — report the absence of evidence, not a confirmed negative.
- "This is an evaluation request, so it gets LLM-SM-EVAL ids." Only a SageMaker-side eval, which runs as a recipe-driven training job, gets LLM-SM-EVAL ids. A Bedrock-native `CreateEvaluationJob` goes to the Bedrock path with LLM-EVAL ids; LLM-SM-EVAL-004 marks the switch ([api-quirks.md](references/api-quirks.md) §15).
- "No evaluation metrics were found, so the scores are zero." Absent datapoints in `OpsAI/Evaluation` mean the scores were never published, not a measured zero. That supports LLM-SM-EVAL-003 as "not retained for comparison", not as a bad score ([api-quirks.md](references/api-quirks.md) §10).
- "The model was registered and approved, so it has been evaluated." Registration and approval are governance state, not evidence of an eval run. Look for an actual SageMaker evaluation job against the artifact before clearing LLM-SM-EVAL-001.
- "The eval job failed, so the model is bad." A `Failed` eval job is usually a bad dataset S3 path, a malformed recipe or a judge-model access error. It says nothing about model quality. Read `FailureReason` (SageMaker) or `failureMessages` (Bedrock) and fix the cause (LLM-SM-EVAL-002 / LLM-EVAL-011).
- "A collection call returned AccessDenied, so the check doesn't apply." AccessDenied is a gap, not a clean result. Name the API and resource you could not read, continue, and disclose the gap.

## Severity Definitions

Severities are assigned by the catalog, not improvised. SLAs are **operational guidance (derived)**.

| Severity | Meaning | Example | Response SLA (derived) |
|---|---|---|---|
| **CRITICAL** | No quality safety net on a production GenAI path | No evaluation ever run (LLM-EVAL-001) in a region that supports evaluation | Immediate — same day |
| **HIGH** | Serious quality risk likely to ship a regression | No regression gate before promotion (LLM-EVAL-007); finish-reason shift to `max_tokens` (LLM-EVAL-012); no metric filter on `stopReason` (LLM-EVAL-013); SageMaker eval job `Failed` (LLM-SM-EVAL-002) | Days |
| **MEDIUM** | Meaningful gap vs best practice | Evaluation run manually, not in CI/CD (LLM-EVAL-002); `OutputTokenCount` rising with flat `Invocations` (LLM-EVAL-014); customized model promoted with no SageMaker eval run (LLM-SM-EVAL-001) | Next sprint |
| **LOW** | Minor hardening or tidiness | A failed/stopped eval job never re-run (LLM-EVAL-011); eval dataset tidiness / coverage gaps of limited blast radius; SageMaker eval output not retained for comparison (LLM-SM-EVAL-003) | Backlog |
| **INFO** | Observation with no AWS-published threshold | Quality-score bar is workload-specific; evaluation unsupported in region (advisory); a Bedrock-native job presented as SageMaker (LLM-SM-EVAL-004) | Document / monitor |

## Error Handling

Before interpreting any response, consult [api-quirks.md](references/api-quirks.md) (load before interpreting any empty list, empty metric, or deciding which service ran a job). The highest-stakes traps for this domain:

- **Region-gated features (§2).** An empty `ListEvaluationJobs` in a region that does **not** support Bedrock evaluation is *not* a CRITICAL "no evaluation ever run" finding — confirm regional support first, and otherwise report INFO/advisory. This is the single most common false positive in the evaluation domain.
- **CloudWatch "no datapoints" ≠ a measured zero (§10).** Absent datapoints mean no traffic or no emission in the window — and for `OpsAI/Evaluation`, scores that were never published (LLM-SM-EVAL-003), not a zero score.
- **A SageMaker-side eval runs as a recipe-driven training job (§15).** Confirm which service ran the job before cataloguing it; a Bedrock-native `CreateEvaluationJob` is diagnosed on the Bedrock path (LLM-SM-EVAL-004).

Operational failures: on **AccessDenied**, report the specific API and resource you could not read, continue, and list the gap. On a **region unsupported for evaluation**, record it as a disclosed assumption, not a finding. On **throttling of describe/list calls**, back off and paginate. On **ambiguous scope**, ask or default to the caller's current region and say so.

## Related skills (optional)

**Related skills (optional).** This skill works on its own. When a question reaches into an area listed below:
- If that skill is in your available skills, load it and use it for that part.
- If it isn't, handle that part yourself with the read-only checks in this skill and general AWS knowledge.
  Label findings that come from general knowledge, and don't give them a check-id.
- At the end of the answer, recommend installing the missing skill once, and name what it would add.

| Area | Skill |
|---|---|
| Live failures right now: errors, 5xx, throttling, latency, "is it AWS or us" | opsai-incident-triage |
| Bedrock model access, invocation logging, model lifecycle, inference profiles, Knowledge Bases / RAG | opsai-bedrock-review |
| Who can call Bedrock (IAM users, long-lived keys), Bedrock Guardrails | opsai-bedrock-security |
| Bedrock spend, quotas, Provisioned Throughput | opsai-capacity-cost |
| Bedrock AgentCore and Bedrock Agents | opsai-bedrock-agentcore |
| SageMaker real-time, serverless and async endpoints, batch transform, SageMaker endpoint cost | opsai-sagemaker-inference |
| SageMaker training, fine-tuning, Model Registry | opsai-sagemaker-training |

Future price quotes: use the [AWS Pricing Calculator](https://calculator.aws/).

## Appendix — Reference Links

Check catalog (each row: `check-id | pillar | severity | detection-rule | remediation | AWS-doc`):

- [checks-evaluation.md](references/checks-evaluation.md) — load before assigning any check-id or severity: LLM-EVAL-001..011 (the OpsAI quality pillar), the finish-reason regression signal (LLM-EVAL-012), the missing metric filter (LLM-EVAL-013), the output-token precursor (LLM-EVAL-014), and the SageMaker-side LLM-SM-EVAL-001..004.

Operational references:

- [finish-reason-analysis.md](references/finish-reason-analysis.md) — load when truncation or a finish-reason shift is in question: `stopReason` values, metric filter, derived >10pp threshold, Logs Insights distribution query, correlated signals.
- [collection-reference.md](references/collection-reference.md) — load with any Router row: read-only API calls (EVAL, SM-EVAL and quality-signal sections; other areas' calls are in `related-skills.md`) and the fields/checks they feed.
- [metrics-and-logs.md](references/metrics-and-logs.md) — load before any log query or metric read: the invocation-log group probe, the record schema and `stopReason` field path, the distribution query, the `OutputTokenCount`/`Invocations` precursor pair, and SageMaker-side eval job signals (§7).
- [api-quirks.md](references/api-quirks.md) — load before interpreting any empty response: misleading-response traps §1–§15 (esp. §2 region-gated evaluation, §10 no datapoints, §15 which service ran the eval).
- [known-causes.md](references/known-causes.md) — load whenever the user names a SageMaker-side evaluation error or symptom: failure logs, the Engine core model-type mismatch, the `gen_qa.jsonl` schema, execution-role access, instance limits, `temperature` and judge standard errors and bootstrap bounds, the results artifact and MLflow fields, Bring-Your-Own-Metrics, each with its AWS-doc citation.

Output templates and delegation:

- [evaluation-report-template.md](assets/evaluation-report-template.md) — load when a report is requested on the Bedrock path or the posture review: header, quality posture, coverage, findings, finish-reason distribution, trend, and scope not covered.
- [sagemaker-evaluation-report-template.md](assets/sagemaker-evaluation-report-template.md) — load when a report is requested on the SageMaker path: service check, evaluation coverage, per-job state, findings with LLM-SM-EVAL check-ids, disclosed scope.
- [delegation-payload.json](assets/delegation-payload.json) — load when delegating evidence-gathering to a sub-agent: the findings contract to send unchanged.

AWS documentation:

- [Bedrock model evaluation](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation.html)
- [Model evaluation jobs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation-jobs.html)
- [Bedrock model evaluation (overview)](https://docs.aws.amazon.com/bedrock/latest/userguide/model-evaluation.html)
- [RAG evaluation](https://docs.aws.amazon.com/bedrock/latest/userguide/evaluation-kb.html)
- [GetEvaluationJob API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetEvaluationJob.html)
- [Model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [CloudWatch Logs metric filters](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html)
- [Bedrock supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [Nova evaluation recipe examples](https://docs.aws.amazon.com/nova/latest/userguide/customize-fine-tune-evaluate-recipe-examples.html)
- [SageMaker CloudWatch metrics](https://docs.aws.amazon.com/sagemaker/latest/dg/monitoring-cloudwatch.html)
