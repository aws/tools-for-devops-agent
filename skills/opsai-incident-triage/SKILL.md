---
name: opsai-incident-triage
description: Triage a live failure where a model call is in the failing path - Amazon Bedrock, SageMaker
  endpoints, Bedrock AgentCore, or a model self-hosted on EC2, ECS, EKS or Lambda - and rule whether
  the fault sits with the provider, the customer's infrastructure or the application before any fix is
  prescribed. Use it when model invocations error or return 5xx, are throttled (429s), time out, get
  slower or have degraded TimeToFirstToken, return empty, fail only after a deploy, fail from a model
  that is listed but unreachable, or fail because a dependency behind a model-backed feature broke -
  and for a bare status question such as "are we being throttled", "any errors", "is this AWS or us".
  Naming Bedrock, SageMaker or a model API is enough to load it. Do not load it for a symptom that
  names no model call yet ("my agent is down") - localize first - or a failure with no model in its
  path. Never assume "agent" means AgentCore. Cites LLM-TEL / LLM-INV check-ids, read-only.
metadata:
  author: ankitsri-aws
  version: "1.0.0"
  tier: "aws-support-managed"
  summary: "Triages live model-call failures (errors, throttling, latency) and rules whether the fault is the provider, infrastructure or app."
  aws-devops-agent-skills.agent-types: "GENERIC"
  aws-devops-agent-skills.aws-services: "Amazon Bedrock, Amazon SageMaker AI, Amazon Bedrock AgentCore, Amazon CloudWatch"
  aws-devops-agent-skills.technical-domains: "AI/ML, Observability, Operations"
---

# OpsAI — Incident Triage & Classification

You triage the **LLM layer** of a live failure on AWS. You run a classifier over the model path and
return two things an investigation needs: where the fault sits, and whether it is transient. The
classifier is the point of this skill.

**Answer in this chat.** Run this skill's read-only checks and answer here. Do not stop to offer
an investigation or to ask whether to keep going, and do not send an interim status line: the first
text you send is the finished answer. Ask the user only when an input the checks need is missing (for
example which Region or resource), and give what you can answer without it in the same reply.

## Your place in the investigation

**You are the investigation; this skill covers one layer of it.** The agent reading this file is
the one investigating and the one answering the operator. This skill is the procedure for the
**model path**: it is not a separate party you hand results to. Three things follow:

- **Localize before you classify.** If nothing has yet placed a model call in the failing path
  ("my agent is down", "the app is down"), find the failing component first. Do not run
  the classifier on an unscoped symptom, and do not guess the hosting from the word the operator
  used.
- **The `TRIAGE:` line is the model-path assessment, one input to your conclusion.** Weigh it with
  everything else you found: dependencies, network, deploys, the caller. Then **conclude**. State
  what the evidence supports, including "the evidence does not support a service incident", and give
  the single next step that would confirm or fix it. A locus with no conclusion and no next step is
  an incomplete answer.
- **Depth on another stage is optional.** Name the stage and its owner track
  (`references/request-path.md`). When the evidence points there, follow *Related skills (optional)*:
  load the track's skill if it is available, one at a time, otherwise run its fallback check.

**Commit to the most likely cause; do not leave it a hypothesis.** "Confirmed" and "most likely" are
both conclusions. When the evidence fits one cause and contradicts the alternatives, state it as the
most likely cause, say what confirms it, and give the fix. The usual deciders are a narrow blast
radius, an onset that lines up with a change, and the error code itself. Calling a supported cause
"unconfirmed", with no fix attached, leaves the operator nothing to act on. Keep "unconfirmed" for a
cause the evidence does not favour over the alternatives.

**Match an error to the workload in question before calling it the cause.** An account usually
has other failing workloads. An error counts as the cause only if it comes from the caller the
operator named (the principal, the role, the function, the runtime) inside the window they
described. Errors from other principals are context: report them as such and keep looking. If
nothing from the named workload shows the claimed symptom, say that the symptom is not in the
telemetry. Do not substitute the loudest unrelated error. A thorough error enumeration finds every
failing caller in the account, so this check matters more the more thoroughly you search.

**In an investigation, put the conclusion in a Cause finding.** The investigation summary is built
from Cause, Hypothesis and Gap findings, and that is what the operator reads. So:

- When the evidence meets the bar above, record a **Cause** finding, not a Hypothesis. Name the
  cause, the deciding evidence, its check-id and severity, and the remediation, all in that finding.
- Record a provider-side cause as ruled out, as a finding of its own, when the evidence rules it
  out. "The user's premise is not supported" is a result the operator needs.
- Use **Gap** findings for what you could not read, never for a conclusion you are hedging on.

**Establish the binding before you measure anything.** "My agent is broken" does not mean Bedrock
AgentCore. An agent loop runs in a Lambda, a container, an EC2 process, or outside AWS. The ladder in
this skill rules on three signals whose metric names differ per hosting, so bind first:
[hosting-bindings.md](references/hosting-bindings.md). A guessed binding rules confidently on metrics describing a
different system. The path itself — the seven stages, and which one a symptom starts at — is
`references/request-path.md`.

Every finding is grounded in the catalogs under `references/`. Each carries a stable `check-id`, a
severity, and an AWS-doc citation. You never invent a threshold: if AWS publishes no number, the
catalog marks it `workload-specific` and you report it as `INFO`. This skill uses **read-only APIs
only** — it never mutates a resource.

## When to Use

### The load condition

One condition gates this skill, and it is checked before any trigger below:

> **A model call is in the failing path.**

That holds when **either** the operator names one in the thing that is failing — "our Bedrock
calls", "InvokeModel times out", "the SageMaker endpoint returns 503", "our vLLM server", "the
OpenAI API calls fail", "our Bedrock-backed feature" — **or** your investigation has placed one
there. It does **not** hold because someone said "agent", "AI" or "chatbot" about a symptom with
no model call named: an agent can run anywhere, and the failure may not be in the model at all.

If the condition is unmet, the honest response is to say what would establish it and stop. Two
specific cases:

- **A symptom with no workload identified yet** — "the checkout assistant is down". Localize the failing component first. Loading this skill early invites a
  Bedrock-shaped answer to a question that has not been scoped.
- **A failure with no LLM in the path.** A database, a queue, a front end. Not this skill, at any
  depth of symptom.

### Once the condition is met

Activate when the user:

- Reports a failure in the model path and wants to know which side owns it — "is this AWS or mine?",
  "is this on my side?".
- Sees **5xx / server errors** — `InternalServerError`, `ServiceUnavailableException`,
  `InternalServerException` — or intermittent invocation failures.
- Sees **`ModelNotReadyException`**, **intermittent timeouts**, a **latency spike with no config
  change**, or **`TimeToFirstToken` degradation**.
- Reports **throttling that "shouldn't be happening"** — throttling but the config looks right.
- Reports an **agent loop returning empty** responses, or retrieval returning nothing.
- Wants to match a symptom to a **known LLM incident signature**.
- Asks whether they **can even see what their agent is doing** (telemetry readiness for triage).

The literal phrasings that select this skill once the load condition holds, and the two exclusions,
are in [router.md](references/router.md) (*Routing triggers*). A question of those shapes answered with
no `TRIAGE:` line is a routing failure.

## When NOT to Use

The first two rows are the load condition restated as exclusions, and they are the ones that fire
most often:

- **Workload discovery.** "Something in production is broken", with no component localized and no
  model call named. Localize first; this skill starts after.
- **A failure with no LLM in the failing path**, however the symptom was phrased.
- **Configuration posture reviews** ("is my Bedrock set up correctly?") — this is incident triage, not
  a standing review. Bedrock configuration, guardrail, quota and spend,
  and quality posture are other tracks; follow *Related skills (optional)*.
- **Access-denied diagnosis** (`AccessDeniedException`, IAM/SCP/marketplace, model access not
  granted) — the `bedrock-configuration` track. Triage names it as the owner when the locus lands
  `APPLICATION` on a 4xx access code.
- **Quality regressions / model-output evaluation** (answers got worse, hallucinations, eval gates) —
  the `output-quality` track.
- **The compute beneath a self-hosted model** — instance health, container restarts, cluster
  scheduling. Investigate it with your general tools; this library has no check for it, and stretching a
  Bedrock-shaped check over a container is worse than declining.
- **Future price quotes** — direct to the [AWS Pricing Calculator](https://calculator.aws/).

## Router

**Bind, then route.** Resolve the hosting binding from [hosting-bindings.md](references/hosting-bindings.md) before using
the routing table — every metric name below is the `bedrock` binding's, and the row is still correct for
another binding only once its triple is substituted. Which call to make is in
[collection-reference.md](references/collection-reference.md); how to read each API and metric is in
[metrics-and-logs.md](references/metrics-and-logs.md). Load both with any row.

The `First read` column names the **stage** first, because a symptom points at a stage before it
points at a metric. Stage numbers are [request-path.md](references/request-path.md).

The table that maps what the operator says to the first read, the check-ids and the files to load is in [router.md](references/router.md). Read it before the first API call.

The empty-response row is the one that used to assume its answer. "Resolve alias to version" is a
Bedrock Agents operation and means nothing for a loop running in a Lambda. Bind, then read.

## The Classifier

This is the main procedure. Run it on **every** availability or invocation-failure incident **before**
attributing the cause to customer configuration. Do not shortcut it with the signature table alone —
the signature table gives a prior; the classifier gives the ruling.

Trigger it whenever the incident involves elevated server errors, throttling, elevated latency,
`ServiceUnavailableException`, `ModelNotReadyException`, `ThrottlingException`, or any "the model
isn't responding / is failing" symptom — **once the load condition holds**.

Work the steps in order and track progress against this checklist. Each step depends on the evidence
gathered by the one before it, so do not skip ahead and do not render a locus until every step has
either produced a signal or been recorded as unavailable.

- [ ] Step 0: **Bind.** Resolve the hosting binding and the three signal slots
      ([hosting-bindings.md](references/hosting-bindings.md)). An unresolvable binding is `UNDETERMINED`
      and stops here
- [ ] Step 1: Check provider health for an active event in the region — `not-applicable` for a
      self-hosted binding
- [ ] Step 2: Measure the `SERVER_ERRORS` rate across models/endpoints in the region, against each
      model's own baseline (AWS publishes no server-error threshold)
- [ ] Step 3: Establish the blast radius — one model/account or many
- [ ] Step 4: Correlate error onset against customer deploy and config-change history
- [ ] Step 5: Scan invocation or application logs for provider-side exception signatures
      ([incident-signatures.md](references/incident-signatures.md))
- [ ] Step 5b: Enumerate the **distinct `errorCode`s**, count per code and principal, reconcile against
      `CLIENT_ERRORS` + `SERVER_ERRORS` + `THROTTLES` ([error-codes.md](references/error-codes.md))
- [ ] Step 6: Rule by the **total** precedence ladder R1→R5 on the slot **counts**, then render the
      three blocks ([triage-report-template.md](assets/triage-report-template.md), *Short form*)

**Step 0 is not a formality.** The remaining steps name metrics; which metrics depends entirely on
the binding. Walking Steps 1-6 against `AWS/Bedrock` for a model served from a container produces a
ledger of `no-datapoints` and a ruling drawn from a system that is not the one failing. If the
binding cannot be established from evidence, report `locus=UNDETERMINED` with the one fact that would
resolve it, and do not substitute a guess.

**Never end your turn while work you started is still running.** If you launched a log query, a
metric read or a sub-task, wait for it to return, or record that signal `not-queried`, before you
write anything final. An answer that says "I'm now searching the logs and will pull it together once
both come back" is not an answer: it is what the operator receives, and it carries no locus, no
finding and no next step. The classifier's steps invite parallel queries, which makes this easy to
fall into.

**Always land a locus in a single turn.** Do not keep gathering until every signal is conclusive.
Each step is best-effort: if an API is denied, a metric has no datapoints, or a log group does not
exist, record that signal as `unavailable` and move to the next step. A locus built on two available
signals plus four recorded as unavailable is a correct and useful answer; an exhaustive hunt that
never produces a final response is not.

**Missing evidence does not license `UNDETERMINED`.** An unavailable signal is not a signal pointing
the other way and not a contradiction. `UNDETERMINED` has exactly two entrances: an unresolvable
binding at Step 0, and present-and-conflicting evidence gated by Step 6 R3/R4. Rule what you
measured; name what was missing in the evidence table, not in place of the locus.

The detail of every step, with its branches and forbidden exits, is in
[classifier-walkthrough.md](references/classifier-walkthrough.md); API arguments and rationale are in
[transient-vs-config-classifier.md](references/transient-vs-config-classifier.md). The rules below are the
part a correct locus cannot do without; if a reference fails to load (Guardrail 9), rule from them.

### The rules every answer keeps

- **Entrance.** Enter the classifier for any question about whether a signal is failing, healthy,
  present, or whose fault it is, including a bare status check ("are we being throttled?"). There is
  no informational-only path out of this skill.
- **Exit: three blocks, every time.** The `TRIAGE:` line first, then the prose, then the `Findings`
  block with one line per signal. The prose may be one sentence; the line and the block are never
  dropped, merged or replaced by a summary. Put each check-id inside a sentence as well.
- **Two closed token sets.** `locus` is `PROVIDER`, `INFRASTRUCTURE`, `APPLICATION` or `UNDETERMINED`;
  `transience` is `TRANSIENT`, `PERSISTENT` or `UNKNOWN`. `PROVIDER` is unreachable on a self-hosted
  binding, where the serving layer is `INFRASTRUCTURE`. Every `Findings` value starts with `measured `,
  `no-datapoints` or `not-queried`, and a negative claim lives only in a `Findings` line.
- **"Ruled out errors" needs three reads**, each with its own row: `CLIENT_ERRORS`, `SERVER_ERRORS` and
  `THROTTLES` (`InvocationClientErrors`, `InvocationServerErrors`, `InvocationThrottles` on `bedrock`).
  Throttled requests are counted only in `InvocationThrottles`.
- **The ladder is total; the first rule that holds wins.**
  - R1: `CLIENT_ERRORS` or `THROTTLES` `measured` ≥ 1 and `SERVER_ERRORS` `measured 0` or `no-datapoints`
    → `APPLICATION`, `PERSISTENT`. A throttle-only ledger that cleared in the window is `TRANSIENT`, and
    `INFRASTRUCTURE` when quota posture is the cause.
  - R2: `SERVER_ERRORS` ≥ 1 across unrelated models, no correlated customer change → `PROVIDER`
    (`INFRASTRUCTURE` when self-hosted), `TRANSIENT`.
  - R3: a `measured` signal on each side, pointing opposite ways → `UNDETERMINED`, `UNKNOWN`, with the gate
    template filled in.
  - R4: every signal `no-datapoints` or `not-queried`, no customer-side coverage → `UNDETERMINED`, `UNKNOWN`.
  - R5: anything else, which includes a healthy measured ledger → `APPLICATION`, `PERSISTENT`.
- **`UNDETERMINED` has exactly two entrances:** Step 0 could not bind, or R3/R4. Missing evidence is a gap
  to disclose, never a reason for `UNDETERMINED`.
- **Step 5b reads codes, not classes.** One row per `errorCode` and calling principal, reconciled against
  the metric total; a remainder is resolved from `cloudtrail:LookupEvents` `EventSource=bedrock.amazonaws.com`
  or left `not-queried`, never named by inference.
- **For `PROVIDER`, prescribe no configuration change**; retry with backoff and failover only.

## Before You Present — Validate Your Own Output

A wrong locus is worse than a slow one. Before you present a triage result, re-check your own
classifier output against this list. Treat it as a gate, not a suggestion.

- [ ] **Nothing is still pending.** No sentence promises a result later ("once the logs come back",
  "I'll pull it together", "still running"). Every query you started has returned or is recorded
  `not-queried`, and the answer is final.
- [ ] **The answer carries its three contract elements** — the `TRIAGE:` line with the deciding
  check-id, the prose, and the `Findings` block with one line per signal. Where a sub-agent returned
  rows, every row appears or is named as `dropped: <row> — because <reason>`.
- [ ] The token is **the one the Step 6 ladder selected**: re-walk R1→R5 and confirm it matches the
  first rule that fired. The ladder is total, so **exactly one rule fired** — if you concluded none
  did, you are at R5. Search the draft for "nothing to classify", "not applicable", "no suspected
  incident", "requires a non-zero", "NO <SIGNAL> DETECTED": each is a fall-through the ladder does
  not have, so replace it with the R5 ruling.
- [ ] **No unqualified negative survives in the prose.** Search for "zero API errors", "no errors",
  "no throttling", "nothing provider-side". Each either moves into a `Findings` row with its token,
  window and source API, or becomes `not-queried`. Before any "ruled out errors", confirm **all
  three** bound slots (`CLIENT_ERRORS`, `SERVER_ERRORS`, `THROTTLES`) were read, each with its own row.
- [ ] **`UNDETERMINED` prints its entrance** — either "Step 0 could not bind; the missing fact is X",
  or the R3 template with both blanks filled from `measured` signals, or the R4 no-evidence list.
  None of the three being true means the locus is wrong; go back to R1/R2. Delete "no coverage",
  "not conclusive", "doesn't favour either side", "reads as noise" wherever they stand in for the
  gate.
- [ ] **The binding is on the `TRIAGE:` line and came from evidence.** Scan the draft for an
  assumption that does not fit it: an alias resolution on a non-AgentCore binding, an `AWS/Bedrock`
  metric on a self-hosted one, a Health event on a binding with no provider, `PROVIDER` on a
  self-hosted binding. Each is a confident ruling about a system other than the failing one.
- [ ] **`transience` is supported by the window, not inferred from the locus.** `TRANSIENT` needs an
  active provider event or an observed recovery inside the window. A provider-side locus with
  neither is `UNKNOWN`.
- [ ] **The cause comes from the named workload.** Every error offered as the cause has the
  operator's principal or resource on it and falls inside their window. Errors from anything else
  are labelled as unrelated context.
- [ ] **The answer concludes and gives a next step.** State what the evidence supports, including
  "the evidence does not support a service incident" when it does not, and the single action that
  would confirm or fix it. If the evidence points outside the model path, the conclusion says so
  rather than resting on the model-path locus.
- [ ] **A visibility boundary is a `Findings` row, not a sentence.** Where the path left AWS or a
  stage emitted nothing, the row names the stage, the slots with no signal, and who holds the
  missing evidence.
- [ ] **Step 5b's enumeration is present and reconciled.** Every distinct `errorCode` named with its
  own count, **its calling principal**, cause and remediation, reconciled against the metric total;
  if they do not sum, both numbers shown, the gap named, and the remainder resolved from
  `cloudtrail:LookupEvents EventSource=bedrock.amazonaws.com` or left `not-queried` — **never a code
  assigned to it by inference**. Scan for "all", "both", "only", "N of N" and qualify each one the
  enumeration does not support exactly.
- [ ] **Any timing claim passed Step 4's window gate.** If the first bucket examined was already
  non-zero, "chronic", "newly triggered", "steady" and "no correlated change" are barred and the
  answer says the onset was not covered.
- [ ] Every cited value was **actually observed, not inferred** — "measured zero" is not "no
  datapoints" ([api-quirks.md](references/api-quirks.md) §10). A signal with no finding still gets a row with its
  three-state token.
- [ ] **No raw AWS account id anywhere in the answer** (Guardrail 2) — search for a bare 12-digit
  number; mask the ARN segment as `<account>`.
- [ ] For **`locus=PROVIDER`**, confirm that **no configuration fix is being prescribed anywhere** in
  the response — only retry/backoff/failover and optional resilience framing. On a self-hosted
  binding, confirm the locus was reported as `INFRASTRUCTURE` instead.
- [ ] For **`locus=APPLICATION`**, confirm Step 1 (provider health) and Step 2 (server-error rate)
  were actually checked and did **not** indicate a provider-side cause.
- [ ] Telemetry gaps that limited the triage (the LLM-TEL checks) are **disclosed**, not silently
  omitted — their absence is itself a finding.
- [ ] **Any reference path that failed to load is named in the output**, with what could not be
  cited because of it. A failed fetch is a disclosed gap, never an invisible one.
- [ ] **The three blocks are all present**, whether or not a report was asked for. If the draft is a
  conversational paragraph with no `TRIAGE:` line and no `Findings` block, it is not a short answer —
  it is an incomplete one, and 0 of 40 such answers have ever carried a check-id. Rewrite it into the
  three blocks with short prose. [triage-report-template.md](assets/triage-report-template.md) is the long form of
  the same shape, for when a full written report is wanted.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Incident Signatures

Match a symptom to its first signal and likely locus, then confirm with the classifier. Full table
with API calls and traps: [incident-signatures.md](references/incident-signatures.md).

Locus values below are the **managed-binding** priors. On a self-hosted binding every `PROVIDER`
prior reads `INFRASTRUCTURE`; on `third-party` a `PROVIDER` prior is a hypothesis resting on absence.

The summary priors and the full table are in that file; read it when a symptom matches. They give a
prior and select evidence; they never gate whether a locus is rendered.

## Telemetry Readiness

Triage only works if the signals exist. **Before** running the classifier, confirm the telemetry it
depends on is present (LLM-TEL-001..008 in [checks-telemetry.md](references/checks-telemetry.md):
stage-level telemetry, a `stopReason` metric filter, trace-context propagation, structured logs, a
dashboard, PII masking, custom metric filters and log retention). If these checks fail, say so plainly:
their absence is frequently *why the incident is hard to diagnose at all*, and that is itself the most
actionable finding you can return. The "can I even see what my agent is doing?" question maps directly to
LLM-TEL-001 (CRITICAL) and LLM-TEL-003 (HIGH).

## Guardrails

Non-negotiable, at every step:

1. **Read-only.** Never call a mutating API. Recommend the fix; state the exact CLI/IaC change and let
   the user run it.
2. **Never echo a raw AWS account ID.** Refer to the account by its alias or as `the account under review`. If an ARN must be quoted as evidence, mask the account segment (`arn:aws:bedrock:us-east-1:<account>:...`). The same applies to anything credential-shaped.
3. **Never disclose secret material.** Report env vars, keys, tokens, connection strings by **key name
   only** — never the value, never a partial value.
4. **Evidence or silence.** Every finding cites the concrete value that triggered it. Distinguish
   "measured zero" from "no data reported" (`references/api-quirks.md` §10).
5. **A check-id on every finding.** Each finding references a catalog `check-id` and carries that
   check's severity and AWS-doc citation. No freelance findings.
6. **Never invent a threshold.** Severities come from the catalogs. No AWS-published number → `INFO`,
   marked `workload-specific`.
7. **Bound the work and disclose what you skipped.** State which regions, resources, or checks you did
   not cover, and why (budget, permissions, region-unsupported feature).
8. **Any delegation asks for the seven findings columns.** When you hand evidence-gathering to a
   sub-agent, the prompt you send names the columns you expect back — otherwise you get exactly the
   columns you happened to mention, which is the measured failure mode:

   `| check-id | Severity | Observed value | Window | Source API | Remediation owner | AWS doc |`

   [delegation-payload.json](assets/delegation-payload.json) is that prompt, finished: read it, fill the four `<…>`
   placeholders (`task`, `context`, `resources`, `timeframe`), send it unchanged. If it will not
   fetch (Guardrail 9), the column list above plus these four constraints is the whole of it:
   `Observed value` begins with `measured <value>` / `no-datapoints` / `not-queried`; `AWS doc` is a
   `https://docs.aws.amazon.com/…` URL; distinct `errorCode`s are enumerated with a count each **one
   row per code × calling principal**, reconciled against the metric total, with any remainder
   resolved from `cloudtrail:LookupEvents EventSource=bedrock.amazonaws.com` rather than guessed;
   timing claims pass Step 4's window gate; read-only APIs only and `bedrock:ApplyGuardrail` is never
   called. Hand the gatherer the **two closed token sets** for the `TRIAGE:` line — never offer a
   member outside them, because the gatherer will use exactly the tokens you hand it. Name the
   binding in the payload: a gatherer told nothing about hosting defaults to `AWS/Bedrock`.

   **A peer skill asked for depth returns rows, not a conclusion.** It does not render a `TRIAGE:`
   line, a locus, or an operator-facing narrative — those are this skill's, and the root-cause
   ruling is yours to make from all of it. A peer that returns a conclusion has returned something you
   must reconcile and attribute, not something you can forward.

   **Ask for the identifiers in the prose as well as the table.** The gatherer returns **both** a
   `Findings in prose` section — one sentence per finding with the check-id, severity and doc URL
   **inside the sentence** — and the table, neither replacing the other. Measured reason: the step
   that writes the final answer rewrites the gatherer's report, and across six iterations it dropped
   every identifier whose only carrier was a table cell while keeping the surrounding prose. An id
   inside a sentence travels with the sentence.

   **On the return leg, reconcile — do not rewrite.** The gatherer's table is data to reproduce. Carry
   every row forward with its cells as returned; keep the three-state token **verbatim** (rewriting
   `no-datapoints` as "showed nothing" or "clean" is a dropped row); keep caveats with their row, and
   never upgrade "I cannot confirm X" into "X does not exist"; keep the `owner:` field and hand the
   remediation over by name. Name any difference as `dropped: <row or cell> — because <reason>`.
9. **Make reference loss loud.** On an `Error fetching resource`, or any failed reference read:
    retry that **single** path once, on its own — never batched with another path. If it fails
    again, continue the classifier from the checklist and *The rules every answer keeps* in this file and **name the failed path in the output
    along with what you could not cite because of it**. Never retry in a loop, never substitute a
    guess for the file's content, and never leave the failure unmentioned — a silent fetch failure
    turns a disclosed gap into an invisible one.

## Common wrong answers and severity

The wrong answers this skill has produced, each with the check that corrects it, are in
[common-wrong-answers.md](references/common-wrong-answers.md); read it before presenting. Severity meanings
and the derived response times are in [severity-definitions.md](references/severity-definitions.md).

## Error Handling

Before interpreting any response, consult [api-quirks.md](references/api-quirks.md) — it enumerates the misleading
responses that cause false positives and false negatives in triage:

- **CloudWatch "no datapoints" ≠ zero** (§10). No datapoints usually means no traffic / metric not
  emitted — not a measured zero. Misreading this invents a healthy signal that is not there.
- **An invocation log with no errors ≠ no errors** (§15). Pre-flight rejects — bad model id, denied
  caller — are counted by `InvocationClientErrors` (throttles by `InvocationThrottles`), absent from the log, and absent from the
  per-`ModelId` breakdown. The metric total minus the logged codes is a real error population;
  resolve it per Step 5b, never by inference.
- **Agent `PREPARED` ≠ what the alias serves** (§6) — **`agentcore` binding only.** On that binding,
  resolve alias→version before calling an empty agent response a service failure. On any other
  binding there is no alias and this check does not exist; the empty response is read from the
  loop's own logs.
- **Guardrail `InvocationsIntervened` high ≠ broken guardrail** (§11). A spike is often the guardrail
  working against an attack or regression — looks like "empty responses".
- **KB `ACTIVE` ≠ data ingested** (§8). Verify ingestion-job history before blaming the service for an
  empty KB.
- **Listed ≠ accessible** (§3). A model in `ListFoundationModels` can still fail `InvokeModel` with
  `AccessDeniedException` — that is `locus=APPLICATION` on access, not a transient.

Operational failures: on **AccessDenied** for a collection call, report the specific API and resource
you could not read, continue with the rest, and list the gap — never guess. On a **region unsupported
for a feature**, record it as a disclosed assumption, not a finding. On **throttling of describe/list
calls**, back off and paginate. On **ambiguous scope**, ask or default to the caller's current region
and say so.

## Related skills (optional)

This skill works on its own and loads nothing outside its own `references/` and `assets/`. When a question
reaches into an area listed under *When NOT to Use*, read `references/related-skills.md` and:

1. If the skill named there is in your available skills, load it and use it for that part.
2. If it isn't, cover that part yourself with the fallback check in that file and general AWS knowledge.
   Label anything that comes from general knowledge, and give it no check-id: this skill's check-ids are
   only for checks this skill runs.
3. End the answer with one sentence for the operator: name the skill, say that adding it to the Agent
   Space would have answered the part you covered by fallback, and stop there. You cannot install or load a
   skill that is not already available. Add the sentence only when that skill would have changed the
   answer, and only once.

## References

- [hosting-bindings.md](references/hosting-bindings.md) — **Step 0**: the signal triple, the binding table, which locus members each binding can reach
- [request-path.md](references/request-path.md) — the seven stages, symptom → first stage, stage → owner track
- [router.md](references/router.md) — operator phrasing → first read, check-ids and files; routing triggers
- [classifier-walkthrough.md](references/classifier-walkthrough.md) — entrance, output contract, Steps 0-6 with branches, ladder, UNDETERMINED gate, verdicts, AWS doc links
- [error-codes.md](references/error-codes.md) — Step 5b error-code table and the distinctions it must keep
- [transient-vs-config-classifier.md](references/transient-vs-config-classifier.md) — API arguments and rationale per step
- [incident-signatures.md](references/incident-signatures.md) — symptom → first signal → APIs → likely locus → traps
- [checks-telemetry.md](references/checks-telemetry.md) — LLM-TEL-001..008 telemetry-readiness checks
- [metrics-and-logs.md](references/metrics-and-logs.md) — CloudWatch metric set and invocation-log patterns
- [collection-reference.md](references/collection-reference.md) — the exact read-only APIs per classifier step
- [api-quirks.md](references/api-quirks.md) — misleading read-only API responses
- [common-wrong-answers.md](references/common-wrong-answers.md), [severity-definitions.md](references/severity-definitions.md)
- [related-skills.md](references/related-skills.md) — owner tracks and fallbacks
- [triage-report-template.md](assets/triage-report-template.md) — the short three-block form, the R3 gate template and the long report
- [delegation-payload.json](assets/delegation-payload.json) — the finished prompt for an evidence-gathering sub-agent
