# Transient vs Configuration Classifier

This is **not** a check catalog. It is a decision procedure the agent applies to *every* question about whether a signal is failing, healthy, or present — and to every availability or invocation-failure finding — **before** attributing the cause to customer configuration.

**No precondition gates this procedure, once the binding is resolved and the load condition in `SKILL.md` holds.** It does not require a declared incident, a raised finding, a non-zero metric, or a matched signature row. A bare status check ("are we being throttled?") enters it the same way a declared outage does, and a ledger of all-zero signals is a complete ledger that rules at R5 — see `SKILL.md`, Step 6, which is the authority on the ladder. "There is nothing to classify" is never an outcome of this procedure.

## Purpose

LLM invocation failures and availability dips have fundamentally different root causes: a transient provider-side condition (regional capacity pressure, a service event, model warm-up), a gap in the customer's own serving or network layer, or an application-side problem (bad IAM scope, wrong model ID, throttle without backoff, malformed request). These demand opposite responses. Sending a customer to troubleshoot their own configuration when the cause is regional capacity wastes their time and erodes trust; conversely, telling a customer to "wait and retry" when their IAM policy is actually broken leaves them stuck. This classifier forces the agent to gather signal on each side first, render an explicit fault locus, and only then name a remediation owner.

**Bind before you measure.** The ladder rules on three abstract slots — `CLIENT_ERRORS`, `SERVER_ERRORS`, `THROTTLES` — whose real metric names differ per hosting. Resolve them at Step 0 from `hosting-bindings.md`. Every metric named in this file is the `bedrock` binding's; substitute the bound names as you go. A guessed binding rules confidently on metrics describing a different system.

Run this classifier whenever a finding involves elevated server errors, throttling, elevated latency, `ServiceUnavailableException`, `ModelNotReadyException`, `ThrottlingException`, or any "the model isn't responding / is failing" symptom — once the load condition in `SKILL.md` holds.

## Decision tree

```
START: a question has been asked about whether a signal is failing, healthy, or present,
       or whose fault it is — including a bare status check. A raised availability or
       invocation-failure finding is one entrance, not the only one, and not a requirement.

Step 0 — Bind the signal triple
  Resolve the hosting binding from evidence (hosting-bindings.md) and fill
  CLIENT_ERRORS / SERVER_ERRORS / THROTTLES with that binding's metric names.
    → Bound?        Proceed, substituting the bound names below.
    → Cannot bind?  STOP. locus=UNDETERMINED, transience=UNKNOWN, and name the one
                    fact that would resolve it: which service serves the failing call.
  Never infer the binding from the operator's vocabulary. "Agent" is not AgentCore.

Step 1 — Provider health
  Call health:DescribeEvents (AWS Health API) and check the Service Health Dashboard
  for ACTIVE events affecting the BOUND service in the affected region/time window.
    → Active matching event found?  Strong PROVIDER signal. Continue to confirm.
    → No event?                     Continue; absence is not proof of a customer fault.
    → Self-hosted binding?          not-applicable, NOT no-datapoints. There is no
                                    provider to have an event, and the serving layer
                                    resolves to INFRASTRUCTURE.
    → third-party binding?          not-visible. Name the vendor's status page as the
                                    evidence you cannot read.

Step 2 — SERVER_ERRORS rate across models/endpoints
  Call cloudwatch:GetMetricData for the bound SERVER_ERRORS slot, broken out
  by model/endpoint, over the incident window.
    → Server errors elevated above each model's own baseline across MULTIPLE UNRELATED
      models in the SAME region?    Strong PROVIDER signal. AWS publishes no server-error
                                    threshold; compare with the baseline, never a fixed
                                    percentage.
    → Elevated for only one model?  Weak signal; could be model-specific capacity or config.

Step 3 — Blast radius: one vs many
  Determine whether the error pattern affects only one model / one account, or many
  models / many accounts in the region.
    → One model, one account?       Leans APPLICATION or INFRASTRUCTURE.
    → Many models / many accounts?  Leans PROVIDER.

Step 4 — Onset timing vs customer change
  Correlate the error onset time against the customer's deployment / change history
  (CloudTrail config changes, deployment markers).
    → Started abruptly, NOT correlated with any customer deployment?
                                    Leans PROVIDER.
    → Onset aligns with a customer deploy / IAM change / model-ID change?
                                    Leans APPLICATION.
  If the investigation already established this history, use it rather than
  re-deriving it, and say which you did.

Step 5 — Provider-side exception signatures
  Scan the BOUND log source for ServiceUnavailableException, ModelNotReadyException,
  InternalServerException patterns — the Bedrock invocation log for bedrock, the
  endpoint log group for sagemaker, the workload's own application log when
  self-hosted. No structured log is LLM-TEL-004 firing, and the step is not-queried.
    → Present and dominant?         These are provider-side signals → PROVIDER.
    → Absent?                       Continue.

Step 6 — Rule on the TOTAL precedence ladder R1→R5.
  `SKILL.md` carries the authoritative ladder, including Step 5b and the R3 gate template;
  this is the same ladder in brief. Walk it in order, first rule satisfied wins, and note
  that it is TOTAL — exactly one rule fires for every question that got here, because R5 is
  a terminal catch-all. There is no fall-through and no "does not apply" exit.
    R1. CLIENT_ERRORS or THROTTLES `measured N>=1` AND SERVER_ERRORS `measured 0` or
        `no-datapoints`                                    → locus=APPLICATION,
        transience=PERSISTENT. Client-error dominance is satisfied by definition; there
        is no share or volume test. Where THROTTLES is the only non-zero slot (a ThrottlingException is
        counted there, not in CLIENT_ERRORS) and
        Step 4 shows it cleared, transience=TRANSIENT and the locus moves to
        INFRASTRUCTURE if quota posture rather than request shape is the cause.
        On self-hosted-lambda the platform metric cannot split client from server, so an
        undifferentiated count does NOT satisfy R1 — go to R3 or R4 and name the slot.
    R2. SERVER_ERRORS `measured N>=1` across multiple unrelated models AND Step 4
        found no correlated customer change                 → locus=PROVIDER on a managed
        binding, locus=INFRASTRUCTURE when self-hosted, transience=TRANSIENT.
    R3. BOTH sides carry a `measured` signal and they point opposite ways
                                                            → locus=UNDETERMINED, R3 gate
        template filled in from `measured` values only.
    R4. EVERY ledger signal is `no-datapoints`/`not-queried` and the customer-side set has
        no coverage either                                  → locus=UNDETERMINED as
        no-evidence.
    R5. TERMINAL CATCH-ALL — R1..R4 did not fire. At least one `measured` row and no error
        or throttle signal >= 1                             → locus=APPLICATION,
        transience=PERSISTENT: the signal is healthy, demand is within limits, and no
        provider-side fault is in evidence.

END: render the TRIAGE: line first, then the prose, then the Findings block.
     A healthy ledger lands on R5 and still gets a line. "Nothing to classify" is not an
     outcome this procedure can produce. Then conclude from it and everything else
     you found, and give the one next step.
```

## Fault-locus categories

The token set is closed at four members and does not vary with hosting. Which members a
binding can reach does vary — `hosting-bindings.md` has the per-binding table.

### PROVIDER

Signals point to the entity serving the model (active Health event, broad 5xx across unrelated models, many-account blast radius, onset uncorrelated with any customer change, `ServiceUnavailableException` / `ModelNotReadyException` signatures).

**Do NOT prescribe customer configuration fixes for this locus.** Report:

> The LLM-path evidence points to a transient provider-side condition in **[region]**. The recommended action is to retry with exponential backoff, or fail over to another region via a cross-region inference profile. No customer-side configuration change is indicated by the model-path signals.

Optionally note that adopting a cross-region inference profile (see `LLM-INV-002`) and exponential backoff with jitter (see `LLM-INV-007`) hardens the workload against the *next* transient event — framed as resilience, not as a fix for a customer mistake.

**Unreachable on a self-hosted binding.** The customer is the provider there, so this outcome is reported as `INFRASTRUCTURE`: there is no Health event to point at and no inference profile to fail over to. **On `third-party`, this locus rests on absence** — no AWS read confirms a vendor incident, so transience is `UNKNOWN` and the vendor's status page is named as the evidence you cannot read.

### INFRASTRUCTURE

Signals point to the customer's own serving or network layer: an endpoint not scaling or under-provisioned, a container failing, a broken VPC endpoint or egress path, ingress 5xx before the loop runs, or quota posture too low for real demand. Distinguished from `APPLICATION` by the request-path stage the evidence sits at, not by severity — stage 2 and the serving half of stage 4 are `INFRASTRUCTURE` (`request-path.md`). Name the owner: `capacity-and-quota` for quota posture, `sagemaker-serving` for endpoint sizing, general investigation for compute, container and network.

### APPLICATION

Signals point to the caller or the orchestration (client-error dominance, single-model/single-account blast radius, onset aligned with a customer deployment or IAM/model-ID change, no provider event). Name the owning remediation track — IAM scope (`LLM-INV-004`), model lifecycle / wrong model ID (`LLM-INV-003`), throttle handling and quota (`LLM-INV-007`), or AgentCore permission/VPC checks (`checks-agentcore.md`).

### UNDETERMINED

Two entrances, and they are not interchangeable.

**Step 0 could not bind.** The failing call's hosting was not established from evidence. Say which service serves the failing call and that you need it, then stop. There is no gate template and nothing to measure yet.

**Step 6 R3 or R4.** Signals are present and contradictory. Run **both** tracks in parallel and present them clearly labeled so the customer is never told their config is broken as if it were certain:

- **Provider-side track (possible):** summarize the transient signals observed and the retry / cross-region failover guidance, labeled as a possibility.
- **Customer-side track (possible):** summarize the config checks to run, labeled as a possibility.

State explicitly that the cause is not yet isolated and name the single additional signal that would resolve it (e.g., "an AWS Health event appearing for this region would confirm provider-side"). Reporting a failed bind as a contradiction sends an operator hunting a conflict that does not exist.

## API calls used

- `health:DescribeEvents` — active service events on the **bound** service in the affected region/time window (Step 1). `not-applicable` for a self-hosted binding.
- `cloudwatch:GetMetricData` — the bound `SERVER_ERRORS` and `CLIENT_ERRORS` slots, broken out across models or endpoints, over the incident window (Steps 2 and 6). `AWS/Bedrock` `InvocationServerErrors` / `InvocationClientErrors` for the `bedrock` binding; see `hosting-bindings.md` for the rest.
- Invocation log error-pattern scan — `ServiceUnavailableException`, `ModelNotReadyException`, `InternalServerException` (service-side) vs `AccessDeniedException`, `ValidationException`, `ThrottlingException`, `ResourceNotFoundException` (client-side) (Steps 5 and 6).

## AWS-doc-citation

https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting-api-error-codes.html
