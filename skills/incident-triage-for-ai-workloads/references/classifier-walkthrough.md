# Classifier walkthrough

The detail behind the classifier checklist in `SKILL.md`: the entrance rule, the output contract, each step with its branches, the R1→R5 ladder, the UNDETERMINED gate and the verdicts. `SKILL.md` keeps the step checklist and the rules; this file holds the detail. The answer formats are in [triage-report-template.md](../assets/triage-report-template.md); the Step 5b error-code table is in [error-codes.md](error-codes.md).

## 1. Entrance

**ENTRANCE — not restricted to a declared incident.** Enter the classifier whenever the question
asks whether a signal is healthy, whether it is present, whether something is failing, or whose
fault it is — including a bare status check ("are we being throttled?", "is anything wrong with X?",
"do you see any errors?"). A status check is an incident question with the incident word removed, and
it takes the same Step 6 ladder with no exemption. **There is no informational-only path out of this
skill:** "the numbers look fine" with no attribution is the answer this skill exists to replace.
Scale the **prose** down for a small question if you like. **Do not scale the structure down** —
see the length rule under the output contract. A short answer is a short *explanation* wrapped in the
same three blocks, never three blocks collapsed into a paragraph.

## 2. Exit: the output contract

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

The three-block form is the *Short form* in [triage-report-template.md](../assets/triage-report-template.md).


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
`InvocationServerErrors` **and** `InvocationThrottles` from `AWS/Bedrock` over the stated window, each with
its own row. A throttled request is counted only in `InvocationThrottles`, never in the two error metrics
([Bedrock runtime metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)). A log scan
alone does not support it — the invocation log does not capture pre-flight rejects, so
`filter ispresent(errorCode) → 0 records` is true of the log and says nothing about the metric.

## 3. Steps 0-6 in detail

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
      threshold, so compare with the baseline; never apply a fixed percentage (SKILL.md Guardrail 6).
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
  throttled request is counted only in InvocationThrottles, not in InvocationClientErrors;
  a request rejected for exceeding a service quota is counted in InvocationClientErrors).
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
      where THROTTLES is the only non-zero slot (throttled requests are counted only there,
      not in CLIENT_ERRORS; a quota-exceeded rejection lands in CLIENT_ERRORS),
      transience=TRANSIENT if Step 4 shows the throttle cleared within the window, and the locus moves to INFRASTRUCTURE if quota posture rather than
      request shape is the cause.
      BINDING CAVEAT: on self-hosted-lambda the platform metric cannot split client from
      server (references/hosting-bindings.md). An undifferentiated error count does NOT
      satisfy R1 — go to R3 or R4 and name the un-splittable slot.
  R2. SERVER_ERRORS `measured N`, N >= 1, across multiple unrelated models (on a self-hosted
      binding: across the callers of the one serving endpoint), AND
      Step 4 found no correlated customer change               → locus=PROVIDER on a managed
      binding, locus=INFRASTRUCTURE on a self-hosted one (PROVIDER has no referent there),
      transience=TRANSIENT.
  R3. BOTH sides carry a `measured` signal and the two point opposite ways
                                                              → locus=UNDETERMINED
      transience=UNKNOWN, with the gate template (§4) filled in literally. Cannot fill both
      blanks from `measured` signals? R3 does not apply — go to R4.
  R4. EVERY ledger signal is `no-datapoints` or `not-queried`, AND no customer-side signal
      (quota, config, request shape, invocation volume) has coverage either
                                                              → locus=UNDETERMINED
      transience=UNKNOWN as no-evidence: list all three bound slots with their states and
      name the one signal that would decide it. One `measured` row anywhere and
      R4 does not apply. If the customer-side set IS the only set with coverage — traffic is
      confirmed real while the error slots are blank — R4 does not apply
      either: go to R5. Blank error slots against live traffic are evidence, not an
      absence of it. An OPERATOR-REPORTED observation is coverage too: when the account is
      not connected and the operator states the symptom ("503s across all services",
      "Bedrock metrics look normal"), record it `not-queried (operator-reported: …)` and
      rule on it as reported. R4 needs no read AND no report. Worked example: vLLM on EKS
      behind an ALB, operator reports 503s across all services for an hour, nothing
      queryable → R2 on the reported server errors → `locus=INFRASTRUCTURE`, never R4.
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
     contract (§2 of this file). Then conclude: what the evidence supports, and the one next step.
```

API arguments and rationale: [transient-vs-config-classifier.md](transient-vs-config-classifier.md).

## 4. The UNDETERMINED gate

`UNDETERMINED` leaves the caller with
nothing to do, so it carries the **highest** bar, not the lowest. It has exactly two entrances and
they are not interchangeable:

**Entrance 1 — Step 0 could not bind.** The failing call's hosting was not established from
evidence. This is a legitimate and common outcome early in an investigation. Say which service
serves the failing call and that you need it, and stop. No gate template; there is nothing to
measure yet.

**Entrance 2 — Step 6 R3 or R4.** The binding is known, the signals were read, and they conflict.
R3 requires this template filled in with measured values and printed in the answer:

The template is in [triage-report-template.md](../assets/triage-report-template.md) (*UNDETERMINED gate*).

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

## 5. Verdicts and what to prescribe

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

## 6. Incident signatures are not a gate

**This table is not a precondition on the classifier, and neither is any check-id row anywhere in
this skill.** The rows select *which* evidence to gather and give a prior on the likely locus;
they never gate whether a locus is rendered. A check-id whose detection rule needs a non-zero
signal is a rule about **whether that finding fires**, never a rule about whether Step 6 runs. No
symptom in this table has to match, and no signal has to be non-zero, for the ladder to be walked
and a token rendered: a ledger of zeroes is a complete ledger and it rules at R5.

## AWS documentation

- [Bedrock API error codes](https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html)
- [Bedrock runtime CloudWatch metrics](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html)
- [Bedrock model invocation logging](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html)
- [Bedrock and CloudTrail](https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html)
- [Cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [AWS Health API — DescribeEvents](https://docs.aws.amazon.com/health/latest/APIReference/API_DescribeEvents.html)
- [Agentic AI Lens — observability (AGENTREL08-BP02)](https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel08-bp02.html)
