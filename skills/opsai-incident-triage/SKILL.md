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
`references/hosting-bindings.md`. A guessed binding rules confidently on metrics describing a
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

**Routing triggers — the literal phrasings, enumerated because each one was observed to miss.** This
list is not illustrative. Any question of these shapes selects this skill **once the load condition
holds**, whether or not the word incident, outage, error or triage appears. Scoped to the LLM path:
the same phrasings about a non-LLM component are not this skill's.

| The user says | Why it is triage |
|---|---|
| "are we being throttled", "are we hitting throttling limits", "are we hitting a quota" | a throttle question is a locus question — the `THROTTLES` slot rules at R1/R5 |
| "any 429s", "any ThrottlingException" | same, by error code |
| "we are seeing 400s and 404s", "two different errors", "two distinct client errors" | Step 5b error-code enumeration is this skill's procedure and nothing else owns it |
| "4xx but no 5xx anywhere", "client errors but no server errors" | R1 is the ruling, by definition |
| "do you see any errors", "any errors in the last N hours" | a status check is an incident question with the incident word removed — see `## ENTRANCE` |
| "is anything wrong with our model calls", "is this on my side" | the core question this skill exists for |
| "is this signal healthy", "absent signal versus healthy signal", "is the metric just empty" | the `measured 0` / `no-datapoints` / `not-queried` distinction is this skill's, and a healthy ledger still rules at R5 |

A question on this list that reaches a different skill, or is answered with no `TRIAGE:` line, is a
routing failure and not a style choice. Two exclusions:

- Truncated or cut-off model output is **not** on this list — finish-reason work is the
  `output-quality` track (see *Related skills (optional)*).
- None of these rows fires before the load condition holds. "Do you see any errors" about a workload
  with no model call identified in its failing path is a general investigation question, not this
  skill's.

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

**Bind, then route.** Resolve the hosting binding from `references/hosting-bindings.md` before using
this table — every metric name below is the `bedrock` binding's, and the row is still correct for
another binding only once its triple is substituted. Which call to make is in
`references/collection-reference.md`; how to read each API and metric is in
`references/metrics-and-logs.md`. Load both with any row.

The `First read` column names the **stage** first, because a symptom points at a stage before it
points at a metric. Stage numbers are `references/request-path.md`.

The table that maps what the operator says to the first read, the check-ids and the files to load is in `references/router.md`. Read it before the first API call.

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
      (`references/hosting-bindings.md`). An unresolvable binding is `UNDETERMINED` and stops here
- [ ] Step 1: Check provider health for an active event in the region — `not-applicable` for a
      self-hosted binding
- [ ] Step 2: Measure the `SERVER_ERRORS` rate across models/endpoints in the region
- [ ] Step 3: Establish the blast radius — one model/account or many
- [ ] Step 4: Correlate error onset against customer deploy and config-change history
- [ ] Step 5: Scan invocation or application logs for provider-side exception signatures
- [ ] Step 5b: Enumerate the **distinct `errorCode`s**, count per code, reconcile against the metric
- [ ] Step 6: Rule by the **total** precedence ladder R1→R5 on client/server **counts**, then render
      the `Findings` block and the `TRIAGE:` line

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

### Entering the classifier, and the contract every answer meets

Kept **inline on purpose** (see `## Guardrails` item 9).

**ENTRANCE — not restricted to a declared incident.** Enter the classifier whenever the question
asks whether a signal is healthy, whether it is present, whether something is failing, or whose
fault it is — including a bare status check ("are we being throttled?", "is anything wrong with X?",
"do you see any errors?"). A status check is an incident question with the incident word removed, and
it takes the same Step 6 ladder with no exemption. **There is no informational-only path out of this
skill:** "the numbers look fine" with no attribution is the answer this skill exists to replace.
Scale the **prose** down for a small question if you like. **Do not scale the structure down** —
see the length rule under the output contract. A short answer is a short *explanation* wrapped in the
same three blocks, never three blocks collapsed into a paragraph.

**EXIT — the output contract.** Stated once, here. Every answer on this skill's path carries these
three things, in this order.

**THE REPORT IS THE DEFAULT OUTPUT, NOT A MODE THE USER HAS TO ASK FOR.** This is the measured
failure of this skill and the reason the rule is stated before the contract rather than after it.
Across 91 captured answers, **no answer under 1,000 characters carried a single check-id (0 of 40)**,
while answers over 3,000 characters carried them half the time — and when the three blocks were
rendered in full the entire contract landed, `TRIAGE:` line included, on every attempt. A
conversational paragraph **physically cannot hold** a triage line, an evidence ledger and a findings
table, so choosing the paragraph is choosing to drop them. Therefore:

- Produce the three blocks **every time**, including for a one-line question, a status check, a
  casual framing, or a follow-up in an ongoing conversation.
- You may shorten the **prose block** to a single sentence. You may not shorten, merge, or omit the
  `TRIAGE:` line or the `Findings` block, and you may not substitute a bulleted summary for them.
- Brevity is never a reason, and the user not having asked for a report is never a reason. If the
  user explicitly asks for one line only, give the `TRIAGE:` line — that is the one line.

```
TRIAGE: binding=<binding> locus=<PROVIDER | INFRASTRUCTURE | APPLICATION | UNDETERMINED> transience=<TRANSIENT | PERSISTENT | UNKNOWN> — <deciding check-id> (<SEVERITY>) — <clause naming the deciding signal>

<the plain-language explanation — as short as the question deserves>

Findings
<check-id> (<SEVERITY>) — <measured <value> | no-datapoints | not-queried> — <window> — <source API> — owner:<skill> — <doc URL>
```

1. **The `TRIAGE:` line, first, with the deciding check-id on it.** A line **beginning with the
   literal string `TRIAGE:`** is the only form that satisfies this. These are the observed
   substitutes and none of them counts: `## Triage: APPLICATION`, `**Locus:** APPLICATION`,
   `Fault locus — APPLICATION`, or a token inside a heading or a sentence. A markdown heading is a
   heading. Write the line, then write the heading too if you want one.

   **Two closed token sets, assessed separately.** They were one token in the previous version of
   this skill (`SERVICE_TRANSIENT` / `CUSTOMER_CONFIG`) and that conflated where the fault sits with
   whether it will clear on its own. Separating them is what lets the line stay honest on a
   self-hosted or third-party binding, where "service transient" has no referent.

   | `locus` | Meaning |
   |---|---|
   | `PROVIDER` | the entity serving the model owns it — AWS for a managed binding, the vendor for `third-party`. **Unreachable on a self-hosted binding**: see `references/hosting-bindings.md` |
   | `INFRASTRUCTURE` | the customer's own serving or network layer — endpoint sizing, container, VPC, ingress, quota posture |
   | `APPLICATION` | the caller's request shape, prompt assembly, identity, configuration or orchestration |
   | `UNDETERMINED` | Step 0 could not bind, or Step 6 R3/R4 fired |

   | `transience` | Meaning |
   |---|---|
   | `TRANSIENT` | expected to clear without a customer change — retry and backoff are the action |
   | `PERSISTENT` | will not clear on its own; a change is required somewhere |
   | `UNKNOWN` | the window does not support the call, or the evidence sits past a visibility boundary |

   Never a token outside these sets, invented at run time. `NO THROTTLING DETECTED`, `HEALTHY`,
   `NOT APPLICABLE` are **observations**, which belong in the clause after the dash, and may not be
   offered to a sub-agent either. **A healthy signal still gets a line**: a `THROTTLES` slot
   `measured 0` against real traffic is R5 — `locus=APPLICATION transience=PERSISTENT`, demand within
   quota and no provider-side fault in evidence.

   **The line covers the model path, not the whole incident.** If the evidence points outside the
   model path (a dependency, the network, a deploy), say so in the prose and conclude there. Do not
   let a model-path locus stand in for a root cause it does not explain.
2. **The `Findings` block, last, one line per signal**, each carrying its check-id, severity, a
   value beginning with one of the three literal tokens (`measured ` / `no-datapoints` /
   `not-queried` — never a bare number, never "zero"/"clean"/"healthy"), its window, its source API,
   its `owner:<skill>` and a `https://docs.aws.amazon.com/…` URL. Where a sub-agent returned rows,
   this block is **transcribed from its table, not summarised** — re-wording a cell is dropping it,
   and a row you drop is named as `dropped: <row> — because <reason>`.
3. **Negative claims are source-bound.** An unqualified "zero API errors", "no throttling", "nothing
   service-side" may not appear in the prose. A negative lives in a `Findings` line, which forces
   the token, the window and the source API onto the same line as the claim. Not queried → the token
   is `not-queried` and the claim is that you did not look.

**Put every check-id inside a sentence, as well as in the `Findings` block.** Write the prose so
each finding sentence carries its id, severity and the value: "`InvocationClientErrors` measured 476
over 24h, which is LLM-INV-011 (HIGH)". Open the prose with the locus in words and its deciding id:
"The model-path evidence points to the application (locus APPLICATION, LLM-INV-011)". A block or
table can be dropped when the answer is summarized; a sentence usually survives.

**"Ruled out errors" requires three metric reads, named.** Read `InvocationClientErrors`,
`InvocationServerErrors` **and** `InvocationThrottles` from `AWS/Bedrock` over the stated window, each
with its own row; throttled requests are counted only in `InvocationThrottles`. A log scan
alone does not support it — the invocation log does not capture pre-flight rejects, so
`filter ispresent(errorCode) → 0 records` is true of the log and says nothing about the metric.

The detail for each step:

```
START: a question has been asked about whether a signal is failing, healthy, present, or
       whose fault it is — including a bare status check. See "ENTRANCE" above; a raised
       incident is one entrance, not the only one. The load condition has already been
       met: an LLM call or agent loop is confirmed in the failing path.

Step 0 — Bind the signal triple
  Resolve the hosting binding from evidence (references/hosting-bindings.md), then fill
  the three slots CLIENT_ERRORS / SERVER_ERRORS / THROTTLES with that binding's real
  metric names. Record which locus members the binding can even reach.
    → Bound?            Proceed. Every metric named below is the bedrock binding's;
                        substitute the bound names as you go.
    → Cannot bind?      STOP the ladder. Render locus=UNDETERMINED transience=UNKNOWN and
                        name the one fact that would resolve the binding (which service
                        serves the failing call). Do NOT pick a binding to keep going.
  NEVER infer the binding from the operator's vocabulary. "Agent" is not AgentCore, "model"
  is not Bedrock, and "endpoint" is not SageMaker. Evidence or UNDETERMINED.

Step 1 — Provider health
  health:DescribeEvents + Service Health Dashboard for ACTIVE events on the BOUND service
  in the affected region/time window.
    → Active matching event?  Strong PROVIDER + TRANSIENT signal. Continue to confirm.
    → No event?               Continue; absence is NOT proof of a customer-side fault.
    → Self-hosted binding?    Record not-applicable, NOT no-datapoints. There is no
                              provider to have an event; PROVIDER is unreachable and the
                              serving layer resolves to INFRASTRUCTURE.
    → third-party binding?    Record not-visible and name the provider's status page as the
                              evidence you cannot read.

Step 2 — SERVER_ERRORS rate across models/endpoints
  cloudwatch:GetMetricData for the bound SERVER_ERRORS slot, by model/endpoint, over window.
    → Server errors elevated above each model's own baseline in the window, across MULTIPLE
      UNRELATED models, SAME region?  Strong PROVIDER. AWS publishes no server-error
      threshold, so compare with the baseline; never apply a fixed percentage.
    → Elevated for only one model?  Weak signal; model-specific capacity or config.

Step 3 — Blast radius: one vs many
    → One model / one account?         Leans APPLICATION or INFRASTRUCTURE.
    → Many models / many accounts?     Leans PROVIDER.

Step 4 — Onset timing vs customer change
  Correlate error onset against deploy / CloudTrail config change history. The host
  investigation usually already holds this history — use what it established rather than
  re-deriving it, and say which you did.
    → Abrupt, NOT correlated with a customer deploy?     Leans PROVIDER.
    → Aligns with a deploy / IAM / model-ID change?      Leans APPLICATION.
  WINDOW GATE, checked on ONE value: is the FIRST bucket of your window already non-zero?
    → Yes?  The onset is OUTSIDE your window. You have not seen it. Report "non-zero
            throughout the window examined; onset not covered" and widen the window before
            ruling on timing. BARRED until you cover a zero/baseline bucket: "chronic",
            "newly triggered", "steady", "pre-existing", "no correlated change". Every
            bucket being non-zero is what a window opened after onset looks like, not
            evidence that the fault is old.
    → No?   The onset is in the window; correlate it against the change history.

Step 5 — Provider-side exception signatures
  Scan the bound log source for ServiceUnavailableException, ModelNotReadyException,
  InternalServerException. The bound source is the Bedrock invocation log for bedrock,
  the endpoint's CloudWatch log group for sagemaker, and the workload's own application
  log for a self-hosted binding — where no structured log exists, that is LLM-TEL-004
  firing and the step is recorded not-queried.
    → Present and dominant?   Provider-side → PROVIDER.
    → Absent?                 Continue.

Step 5b — Resolve every error to its CODE and its PRINCIPAL, never to its 4xx/5xx class
  Enumerate the DISTINCT errorCode values in the window and the count of each, one row per
  code PER CALLING PRINCIPAL (CloudTrail userIdentity). Two roles failing the same way are
  TWO rows: a one-principal answer to an N-principal fault leaves N-1 callers broken. The
  principal goes in the Observed value cell after the token: `measured 15 AccessDenied by
  role <role-name>`.
  Then reconcile: the per-code counts must SUM to the metric total over the same window
  (the bound CLIENT_ERRORS + SERVER_ERRORS + THROTTLES slots; on the bedrock binding a
  ThrottlingException is counted in InvocationThrottles, not in InvocationClientErrors).
    → Sum equals the metric?        Report the enumeration; each code gets its own cause
                                    and its own remediation.
    → Sum does NOT equal?           Say so, give both numbers, name what is unaccounted for,
                                    then RESOLVE the remainder — do not leave it or label it:
                                      cloudtrail:LookupEvents
                                        AttributeKey=EventSource
                                        AttributeValue=<bound service>.amazonaws.com
                                    (bedrock.amazonaws.com for the bedrock binding;
                                    sagemaker.amazonaws.com for sagemaker; for a
                                    self-hosted binding there is no control-plane event
                                    for a data-plane call and the remainder stays
                                    not-queried unless the app itself logged it)
                                    Pre-flight rejects (bad/unresolvable model id, denied
                                    caller) never reach the invocation log and carry NO
                                    ModelId dimension, so the metric sees them and the log
                                    does not — that gap IS the remainder. InvokeModel and
                                    Converse are CloudTrail management events, logged by
                                    default; query by EventSource, because EventName=InvokeModel
                                    misses every Converse call (measured: 0 vs 49 events).
                                    Count only eventType AwsApiCall. Read the codes and the
                                    principals off these events.
  NEVER name a code for the unaccounted remainder by inference. An unresolvable model id
  produces ValidationException and a denied caller produces AccessDenied; guessing
  ResourceNotFoundException because "the id must not resolve" is how a 403 gets reported as
  a 404 and the wrong fix gets shipped. If CloudTrail is unreadable, the remainder stays
  `not-queried` and is disclosed as such.
  FORBIDDEN unless the enumeration sums exactly: "all", "both", "only", "N of N", and any
  sentence of the form "the errors are <single code>". Two distinct codes with one shared
  label is the failure this step exists to prevent — one fix handed to a two-fix problem.

Step 6 — Rule. A TOTAL PRECEDENCE LADDER on COUNTS, never a share calculation.
  Walk R1→R5 against the three-state ledger. The FIRST rule satisfied is the ruling; stop
  there. No ratio test and no minimum-volume floor exists anywhere in this ladder.

  THE LADDER IS TOTAL. Exactly one of R1..R5 fires for EVERY question that got past Step 0,
  because R5 is a terminal catch-all with no condition left to fail. There is no
  fall-through, no "the ladder does not apply", and no exit from Step 6 without a token. A
  ledger of all-healthy signals does not escape the ladder — it lands on R5.

  The ladder rules on the BOUND SLOTS, never on a literal metric name. Substitute the
  binding's names from Step 0; the logic below does not change with the hosting.

  R1. CLIENT_ERRORS `measured N` or THROTTLES `measured N`, N >= 1, AND SERVER_ERRORS
      `measured 0` or `no-datapoints`                         → locus=APPLICATION.
      Client-error dominance is SATISFIED BY DEFINITION here, whatever N is relative to
      successes. One 4xx in 21 calls with zero 5xx is an APPLICATION ruling, not noise: a
      client error is a rejected request, and this slot pair cannot express a share.
      transience=PERSISTENT — a rejected request shape does not clear on retry. EXCEPTION:
      where THROTTLES is the only non-zero slot (ThrottlingException is counted there, not
      in CLIENT_ERRORS), transience=TRANSIENT if Step 4 shows the throttle cleared within
      the window, and the locus moves to INFRASTRUCTURE if quota posture rather than
      request shape is the cause.
      BINDING CAVEAT: on self-hosted-lambda the platform metric cannot split client from
      server (references/hosting-bindings.md). An undifferentiated error count does NOT
      satisfy R1 — go to R3 or R4 and name the un-splittable slot.
  R2. SERVER_ERRORS `measured N`, N >= 1, across multiple unrelated models, AND
      Step 4 found no correlated customer change               → locus=PROVIDER on a managed
      binding, locus=INFRASTRUCTURE on a self-hosted one (PROVIDER has no referent there),
      transience=TRANSIENT.
  R3. BOTH sides carry a `measured` signal and the two point opposite ways
                                                              → locus=UNDETERMINED
      transience=UNKNOWN, with the gate template below filled in literally. Cannot fill both
      blanks from `measured` signals? R3 does not apply — go to R4.
  R4. EVERY ledger signal is `no-datapoints` or `not-queried`, AND no customer-side signal
      (quota, config, request shape, invocation volume) has coverage either
                                                              → locus=UNDETERMINED
      transience=UNKNOWN as no-evidence: list all three bound slots with their states and
      name the one signal that would decide it. One `measured` row anywhere and
      R4 does not apply. If the customer-side set IS the only set with coverage — traffic is
      confirmed real while the error slots are blank — R4 does not apply
      either: go to R5. Blank error slots against live traffic are evidence, not an
      absence of it.
  R5. TERMINAL CATCH-ALL — reached whenever R1..R4 did not fire, and it can always be
      reached. The ledger carries at least one `measured` row and no error or throttle
      signal is >= 1                                           → locus=APPLICATION,
      transience=PERSISTENT.
      Clause: the signal is healthy and the customer side owns it — demand is within limits
      and NO provider-side fault is in evidence. R5 is the HEALTHY-LEDGER rule, and it is the
      reason "everything is fine" is an assessment rather than a non-answer.
      Worked example, the case that has failed twice: "are we being throttled?" with
      THROTTLES `measured 0` and SERVER_ERRORS `measured 0` against
      22-60 real invocations/hour. R1 needs a client error >= 1 — no. R2 needs a server
      error >= 1 — no. R3 needs a contradiction — no. R4 needs a blank ledger — no, the
      ledger is measured. R5 fires:
      `TRIAGE: binding=bedrock locus=APPLICATION transience=PERSISTENT — LLM-INV-007 (INFO)
      — InvocationThrottles measured 0 over 24h against 22-60 invocations/hour; demand is
      within quota and no provider-side throttling is in evidence`.

  FORBIDDEN exits from Step 6, each one observed producing a non-answer. Every one of these
  sentences is a ladder fall-through, and the ladder has none:
    - "there is nothing to classify as provider-side vs. customer-side"
    - "the classifier is not applicable / does not apply here"
    - "no suspected incident exists, so the ladder is not triggered"
    - "the check-ids require a non-zero <metric> before the classifier applies"
    - "NO <signal> DETECTED" or any token outside the two closed sets
  If you have written one of these, you are at R5 and have not noticed. Render R5.
  The ONE legitimate exit without a ladder ruling is Step 0 failing to bind, which renders
  locus=UNDETERMINED and says which fact is missing. That is not a fall-through: it is a
  disclosed inability to measure the right system, and it is stated as such.

END: render the `TRIAGE:` line, then the prose, then the `Findings` block — the output
     contract above. Then conclude: what the evidence supports, and the one next step.
```

Full procedure, API arguments, and rationale: `references/transient-vs-config-classifier.md`.

### The UNDETERMINED gate

Kept **inline on purpose** (see `## Guardrails` item 9). `UNDETERMINED` leaves the caller with
nothing to do, so it carries the **highest** bar, not the lowest. It has exactly two entrances and
they are not interchangeable:

**Entrance 1 — Step 0 could not bind.** The failing call's hosting was not established from
evidence. This is a legitimate and common outcome early in an investigation. Say which service
serves the failing call and that you need it, and stop. No gate template; there is nothing to
measure yet.

**Entrance 2 — Step 6 R3 or R4.** The binding is known, the signals were read, and they conflict.
R3 requires this template filled in with measured values and printed in the answer:

```
UNDETERMINED requires one MEASURED signal on EACH side, named, with its window:
  provider-side signal : ____________  = __________  over __________
  customer-side signal : ____________  = __________  over __________
  why they contradict  : ______________________________________________
```

Do not blur the two. "We could not determine the hosting" and "the evidence contradicts itself" lead
to different next actions, and reporting the first as the second sends an operator hunting for a
conflict that does not exist.

A blank you cannot fill from a signal whose state is `measured` means the gate is **not** satisfied.
These are never service-side signals and may never go in the first blank: a `no-datapoints` signal,
a `not-queried` signal, the absence of an AWS Health event, an uncovered window, missing telemetry,
"the failure window has no coverage". Each is **unavailable** — record it, disclose it as a gap, and
rule on what you did measure. Two forbidden constructions, both observed producing a wrong locus:

- "The failure window has no telemetry coverage, so neither side is favoured." Gaps are gaps. A 4xx
  measured anywhere in the queried window with no 5xx was already decided by R1 — `APPLICATION`.
- "The error count is small relative to successes, so it reads as noise rather than a true
  4xx-dominated pattern." No such share test exists. See R1.

### Step 5b — the error-code enumeration, and the check-id it maps to

Kept **inline on purpose** (see `## Guardrails` item 9): Step 5b must be runnable without fetching
anything. Produce this table before Step 6, one row per **distinct** `errorCode` actually observed —
never one row per error class:

| `errorCode` | Class | What it means — and what it does NOT mean | check-id | Remediation owner |
|---|---|---|---|---|
| `ValidationException` | 4xx | Malformed request, unsupported parameter, context too long, or a **model id that does not exist**. Not an entitlement problem. | LLM-INV-011 | caller's request shape / model id |
| `ResourceNotFoundException` | 4xx | The named resource (model, agent, alias, KB) **does not resolve in this region**. Distinct from being entitled-but-denied. | LLM-INV-003 | `bedrock-configuration` (model/alias lifecycle) |
| `AccessDeniedException` | 4xx | The model or action **exists** but the caller is **not entitled** — IAM, SCP, or model access not granted. Never a service fault. | LLM-INV-004 | `bedrock-configuration` (access) |
| `ThrottlingException` | 4xx | Quota or capacity pressure. Check backoff before quota. | LLM-INV-007 | quota/backoff |
| `ModelNotReadyException` | 4xx (429) | The model is not ready to serve inference requests; the AWS SDK retries it automatically, up to 5 times ([Converse errors](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)). Provider-side readiness, not the caller's request shape, despite the 4xx status. | LLM-INV-005 | retry/backoff |
| `ServiceUnavailableException` / `InternalServerException` | 5xx | Service-side transient. | LLM-INV-007 | retry/backoff/failover |

Three distinctions are load-bearing and must survive into the output, because each one changes the
fix handed to the user:

- **Does not exist** (`ValidationException` on a malformed or unknown model id) versus **exists but
  not entitled** (`AccessDeniedException`) versus **does not resolve here** (`ResourceNotFoundException`).
  These three are distinguished by **reading the code**, never by reasoning about the id. A bad model
  id in a `Converse` call returns `ValidationException`, not `ResourceNotFoundException`.
- **Each row names its calling principal.** The same code under two roles is two rows with two
  owners; the metric cannot tell you who called, and only CloudTrail `userIdentity` can.
- Each observed code gets **its own cause sentence and its own remediation**. Two codes sharing one
  remediation is a reportable contradiction, not a simplification.
- The 4xx/5xx **class** is an input to Step 6 only. It is never the answer to "what errors are you
  seeing" — codes are.

### Verdicts and what to prescribe

**`locus=PROVIDER`, `transience=TRANSIENT`** — active Health event, broad 5xx across unrelated
models, many-account blast radius, onset uncorrelated with any customer change, or
`ServiceUnavailableException` / `ModelNotReadyException` dominant. **Do NOT prescribe customer
configuration fixes.** Report:

> The LLM-path evidence points to a transient provider-side condition in **[region]**. Retry with
> exponential backoff, or fail over to another region via a cross-region inference profile. No
> customer-side configuration change is indicated by the model-path signals.

Optionally frame cross-region inference profiles and backoff-with-jitter as resilience hardening for
the *next* event — not as a fix for a customer mistake.

**On a self-hosted binding this outcome is reported as `locus=INFRASTRUCTURE`.** The serving layer
failed and the customer owns the serving layer; there is no AWS Health event to point at and no
cross-region inference profile to fail over to. Prescribe nothing about the compute — name
`INFRASTRUCTURE` and investigate that stage with your general tools, not with Bedrock checks.

**On a `third-party` binding, `PROVIDER` rests on absence.** No AWS read can confirm a vendor
incident. Say that the locus is `PROVIDER` because no customer-side signal accounts for the failure,
set `transience=UNKNOWN`, and name the vendor's status page as the evidence you cannot read.

**`locus=APPLICATION`** — client-error dominance, single-model/single-account blast radius, onset
aligned with a customer deploy or IAM/model-ID change, no provider event. Name the owning
remediation track rather than performing it: access/IAM, model lifecycle, wrong model ID, inference
profiles → `bedrock-configuration`; quota posture → `capacity-and-quota`; empty output from the loop
→ `agent-runtime` on an `agentcore` binding, or the loop's own logs on a self-hosted one; retrieval →
`retrieval`. Then follow *Related skills (optional)* for that track.

**`locus=INFRASTRUCTURE`** — the customer's own serving or network layer: endpoint under-provisioned
or not scaling, container failing, VPC endpoint or egress path broken, ingress returning 5xx before
the loop runs, quota posture too low for real demand. Distinguished from `APPLICATION` by the stage
the evidence sits at, not by severity: stage 2 and the serving half of stage 4 are
`INFRASTRUCTURE`, stages 1, 3, 5, 6 and 7 are `APPLICATION`.

**`locus=UNDETERMINED`** — either Step 0 could not bind, or **present and contradictory** signals
with one measured on each side, reached via Step 6 R3 with its template filled in, or R4 where
nothing at all was measured. Never reached because evidence was thin, because a window was
uncovered, or because a signal was not queried — that is an unavailable signal, not a contradiction,
and the other rules of the ladder still apply to what *was* measured. Where the R3 gate is genuinely
met: present both tracks clearly labeled so the customer is never told their configuration is broken
as if it were certain, state explicitly that the cause is not isolated, and name the single
additional signal that would resolve it.

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
  window and source API, or becomes `not-queried`. Before any "ruled out errors", confirm **both**
  the bound `CLIENT_ERRORS` and `SERVER_ERRORS` slots were read, each with its own row.
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
  datapoints" (`references/api-quirks.md` §10). A signal with no finding still gets a row with its
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
  three blocks with short prose. `assets/triage-report-template.md` is the long form of the same
  shape, for when a full written report is wanted.

If any item cannot be satisfied, say so explicitly in the output rather than quietly dropping it.

## Incident Signatures

Match a symptom to its first signal and likely locus, then confirm with the classifier. Full table
with API calls and traps: `references/incident-signatures.md`.

Locus values below are the **managed-binding** priors. On a self-hosted binding every `PROVIDER`
prior reads `INFRASTRUCTURE`; on `third-party` a `PROVIDER` prior is a hypothesis resting on absence.

The summary priors and the full table are in `references/incident-signatures.md`; read it when a symptom matches.


**This table is not a precondition on the classifier, and neither is any check-id row anywhere in
this skill.** The rows select *which* evidence to gather and give a prior on the likely locus;
they never gate whether a locus is rendered. A check-id whose detection rule needs a non-zero
signal is a rule about **whether that finding fires**, never a rule about whether Step 6 runs. No
symptom in this table has to match, and no signal has to be non-zero, for the ladder to be walked
and a token rendered: a ledger of zeroes is a complete ledger and it rules at R5.

## Telemetry Readiness

Triage only works if the signals exist. **Before** running the classifier, confirm the telemetry it
depends on is present. If these checks fail, say so plainly — their absence is frequently *why the
incident is hard to diagnose at all*, and that is itself the most actionable finding you can return.

| check-id | What it verifies | Severity | If missing |
|---|---|---|---|
| LLM-TEL-001 | Stage-level telemetry across retrieval → inference → tool → response generation | CRITICAL | Slowness/failure cannot be isolated to a stage — triage is blind. |
| LLM-TEL-002 | CloudWatch metric filter on `stopReason` / `finish_reason` | HIGH | Truncation/quality drift (`max_tokens` share) is invisible. |
| LLM-TEL-003 | Trace-context propagation (W3C `traceparent` / X-Ray) across agent→KB→model→tool | HIGH | A single request cannot be followed end-to-end. |
| LLM-TEL-004 | Structured JSON logs with consistent keys | MEDIUM | Logs Insights queries and metric filters are unreliable. |
| LLM-TEL-005 | A dashboard compositing Bedrock + guardrail + agent signals | MEDIUM | No single operational view during an incident. |
| LLM-TEL-006 | Invocation-log PII masking on sensitive paths | MEDIUM | Raw prompt/response text delivered unmasked. |
| LLM-TEL-007 | Custom metric filters beyond the default namespace | LOW | Cannot slice per-use-case / per-caller. |
| LLM-TEL-008 | Explicit log-group retention | INFO | Logs accumulate indefinitely; cost grows unbounded. |

Full detection rules and remediations: `references/checks-telemetry.md`. The "can I even see what my
agent is doing?" question maps directly to LLM-TEL-001 and LLM-TEL-003.

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

   `assets/delegation-payload.json` is that prompt, finished: read it, fill the four `<…>`
   placeholders (`task`, `context`, `resources`, `timeframe`), send it unchanged. If it will not
   fetch (Guardrail 10), the column list above plus these four constraints is the whole of it:
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
9. **Decision-critical content is inline on purpose — never move it out.** The six classifier steps
   and their decision rules, the ENTRANCE rule, the output contract, Step 6's ladder R1→R5 with its
   forbidden exits, the UNDETERMINED gate, Step 5b's error-code table, the locus and transience
   definitions, the load condition, the signal triple,
   the severity scale, the `LLM-TEL-001..008` table and the read-only rule are all inline **by
   design**. Do not relocate them into `references/` to save tokens: reference fetches do fail at
   runtime, and when they do a correct locus must still be reachable from this file alone.
10. **Make reference loss loud.** On an `Error fetching resource`, or any failed reference read:
    retry that **single** path once, on its own — never batched with another path. If it fails
    again, continue the classifier from the inline content and **name the failed path in the output
    along with what you could not cite because of it**. Never retry in a loop, never substitute a
    guess for the file's content, and never leave the failure unmentioned — a silent fetch failure
    turns a disclosed gap into an invisible one.

## Common wrong answers

- "There is a 5xx in the logs, so prescribe a config change." A single 5xx among hundreds of successful invocations is transient noise. Measure the server-error rate across the window before ruling, and do not send a customer to fix configuration for a one-off blip.
- "The metric shows no datapoints, so the value is zero." No datapoints usually means no traffic or the metric was not emitted, not a measured zero (`references/api-quirks.md` §10). Distinguish "nothing reported" from "zero measured" before calling a signal healthy.
- "Throttling appeared, so the quota is too low." A `ThrottlingException` that cleared on retry is not a quota problem. Check whether backoff with jitter is present and whether the throttle climbs with your own traffic before touching quota (`references/incident-signatures.md`, LLM-INV-007).
- "No AWS Health event is showing, so it must be the customer's config." Absence of a Health event is not proof of customer config. Keep working the classifier; let 5xx rate, blast radius and onset timing rule.
- "The agent returns empty, so Bedrock is failing." `PREPARED` status is not what the alias serves (`references/api-quirks.md` §6), and a guardrail intervention looks like empty output but is the guardrail working (§11). Resolve alias to version and check interventions first.
- "The knowledge base is ACTIVE, so retrieval should work." KB `ACTIVE` only means the wiring is valid (`references/api-quirks.md` §8). Verify a `StartIngestionJob` completed before blaming the service for an empty KB.
- "5xx dominate, so it is definitely provider-side." Confirm the onset is not correlated with a customer deploy or IAM/model-ID change (classifier Step 4) before landing `PROVIDER`; a correlated onset leans `APPLICATION`.
- "The operator said agent, so this is AgentCore." An agent loop runs in a Lambda, a container, an EC2 process, or off AWS. Bind from evidence (`references/hosting-bindings.md`); an unbindable path is `locus=UNDETERMINED`, not a Bedrock answer.
- "The model is self-hosted and the serving layer failed, so this is PROVIDER." The customer is the provider on a self-hosted binding. `PROVIDER` has no referent and the locus is `INFRASTRUCTURE`; reporting otherwise sends the operator looking for a Health event that cannot exist.
- "No LLM has been found yet, but the symptom sounds like one." Localize the failing component first. Loading this skill before the load condition holds produces a Bedrock-shaped answer to an unscoped question.

## Severity Definitions

| Severity | Meaning | Response SLA (derived) |
|---|---|---|
| **CRITICAL** | Active production impact or total triage blindness | 24–48 hours |
| **HIGH** | Serious reliability/observability risk | Within 1 week |
| **MEDIUM** | Meaningful gap vs best practice | Within 30 days |
| **LOW** | Minor hardening | When convenient |
| **INFO** | Observation with no AWS-published threshold | N/A — document / monitor |

SLAs are operational guidance (derived), not AWS-published commitments.

## Error Handling

Before interpreting any response, consult `references/api-quirks.md` — it enumerates the misleading
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
3. End the answer with one line recommending the missing skill and what it would add. Add it only when
   that skill would have changed the answer, and only once.

## Appendix — Reference Links

Triage references under `references/`:

- `references/hosting-bindings.md` — **Step 0**: the signal triple, the binding table, which locus
  members each binding can reach, and what to say when the path leaves AWS
- `references/request-path.md` — the seven stages, symptom → first stage, stage → owner track
- `references/transient-vs-config-classifier.md` — the full classifier decision procedure (primary)
- `references/incident-signatures.md` — symptom → first signal → APIs → likely locus → traps
- `references/checks-telemetry.md` — LLM-TEL-001..008 telemetry-readiness checks
- `references/metrics-and-logs.md` — CloudWatch metric set + invocation-log error-pattern table
- `references/api-quirks.md` — misleading read-only API responses
- `references/collection-reference.md` — the exact read-only APIs used per classifier step

The first two are the ones that keep this skill honest about hosting. Load
`hosting-bindings.md` before any measurement; load `request-path.md` when the symptom does not
already name a stage.

Output template under `assets/`:

- `assets/triage-report-template.md` — consolidated triage output format (triage line, classifier
  evidence, findings with check-ids and severities, prescription, telemetry gaps, disclosed scope)

AWS documentation:

- [Bedrock API error codes](https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html)
- [Bedrock runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)
- [Bedrock model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [Cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [AWS Health API — DescribeEvents](https://docs.aws.amazon.com/health/latest/APIReference/API_DescribeEvents.html)
- [Agentic AI Lens — observability (AGENTREL08-BP02)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel08-bp02.html)
