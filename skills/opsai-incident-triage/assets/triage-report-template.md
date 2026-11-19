# OpsAI Incident Triage Report

Fill in every `<placeholder>`. Delete a row only when the step/section genuinely does
not apply, and when you do, say why in **Scope not covered**. Never leave a placeholder
unresolved in a delivered report.

## Incident

- **Symptom:** `<symptom>` (e.g. intermittent `InternalServerError` on the model call)
- **Hosting binding:** `<bedrock | sagemaker | agentcore | self-hosted-alb | self-hosted-lambda | third-party | UNDETERMINED>`
- **How the binding was established:** `<the evidence — not the operator's wording>`
- **Failing stage:** `<1 caller | 2 ingress | 3 agent loop | 4 model endpoint | 5 retrieval | 6 tools | 7 output filter>`
- **Region examined:** `<region>`
- **Time window examined:** `<start-ts>` → `<end-ts>` (`<tz>`)
- **Models / accounts / endpoints in scope:** `<ids>`

## Triage line

**The `TRIAGE:` line is the FIRST line of what you send — above this heading, above the title,
above any pleasantry.** The report body below is what follows it. A response whose first line does
not match `^TRIAGE: binding=\S+ locus=(PROVIDER|INFRASTRUCTURE|APPLICATION|UNDETERMINED) transience=(TRANSIENT|PERSISTENT|UNKNOWN)`
is malformed and is rewritten before sending:

```
TRIAGE: binding=<binding> locus=<PROVIDER | INFRASTRUCTURE | APPLICATION | UNDETERMINED> transience=<TRANSIENT | PERSISTENT | UNKNOWN> — <deciding check-id> (<SEVERITY>) — <deciding signal>
DIRECT ANSWER: <the narrower yes/no the user literally asked for, when the line answers a broader question>
```

Deciding signal: `<name the single Step 0-6 signal that decided it>`
(e.g. "Step 2 — server-error rate >5% across 3 unrelated models in the same region").

**This line covers the model path.** Weigh it with everything else the investigation found, then
state the conclusion and the one next step below it.

The report then **ends** with the terminal `Findings` block from `SKILL.md`, which is a
**copy-forward of the gatherer's table** — every returned row, every cell, or an explicit
`dropped from the gatherer's report:` line for each one that did not survive, so that
`N + dropped == M` on the page:

```
Findings (N carried of M gatherer rows)
<check-id> (<SEVERITY>) — <measured <value> | no-datapoints | not-queried> — <window> — <source API> — owner:<skill> — <doc URL>
dropped from the gatherer's report: <row or cell> — because <reason>
```

> If `locus=UNDETERMINED`, say which of the two entrances applies — Step 0 could not bind (name the
> missing fact: which service serves the failing call), or Step 6 R3/R4 (name the one additional
> signal that would resolve the conflict): `<entrance + missing signal>`.

## Classifier evidence

| Step | Signal observed | Points to |
|---|---|---|
| 0 — Binding | `<binding + the three bound slot metric names / UNDETERMINED>` | `<proceed / stop at UNDETERMINED>` |
| 1 — Provider health | `<active event id / none / not-applicable (self-hosted) / not-visible (third-party) / not checked>` | `<PROVIDER / neutral>` |
| 2 — SERVER_ERRORS rate | `<rate% across N models / no datapoints>` | `<PROVIDER / weak>` |
| 3 — Blast radius | `<one model-account / many>` | `<APPLICATION or INFRASTRUCTURE / PROVIDER>` |
| 4 — Onset vs customer change | `<correlated with deploy @ ts / uncorrelated / onset not covered>` | `<APPLICATION / PROVIDER>` |
| 5 — Exception signatures | `<ServiceUnavailable/ModelNotReady dominant / absent / no structured log>` | `<PROVIDER / neutral>` |
| 6 — CLIENT vs SERVER dominance | `<client dominant / server dominant / mixed / not-separable>` | `<APPLICATION / PROVIDER / UNDETERMINED>` |

> Each cell must be an *observed* value. Write `no datapoints` (not `0`) when the metric
> emitted nothing, `not checked` when the step was blocked, `not-applicable` where the binding has
> no such signal, and `not-separable` where the binding cannot split the slot.
> Every metric name in this table is the one bound at Step 0. A row naming `AWS/Bedrock` on a
> non-Bedrock binding is a report about the wrong system.

## Findings

| check-id | Severity | Observed value | Window | Source API | Remediation owner | AWS doc | Remediation |
|---|---|---|---|---|---|---|---|
| `<LLM-TEL-NNN / LLM-INV-NNN / LLM-AGT-NNN / LLM-KB-NNN / LLM-GRD-NNN / LLM-SM-NNN>` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<measured <value> / no-datapoints / not-queried>` | `<start → end UTC>` | `<cloudwatch:GetMetricData / health:DescribeEvents / logs:StartQuery / …>` | `<owning skill / caller / host-investigation>` | `<https://docs.aws.amazon.com/…>` | `<exact read-only-recommended fix>` |
| `<boundary row, where the path leaves AWS>` | `INFO` | `not-queried` | `<window>` | `—` | `<who holds the evidence>` | `—` | `<what would be needed to see past it>` |
| `<LLM-...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` | `<...>` |

> No freelance findings — every row cites a catalog `check-id` and that check's severity.

> **All eight columns are mandatory and the first seven are the gate.** The observed-value cell
> begins with one of `measured `, `no-datapoints`, `not-queried`; a bare number there is malformed.
> `Remediation owner` names the track that owns the fix (`references/related-skills.md`), and keeping a
> remediation you attributed to another track is the contradiction that column exists to expose. The `check-id` and its
> `Severity` must sit in the **same row**; a severity gathered into a trailing summary is detached
> and does not count. A row that cannot name its window, the read-only API that produced the value,
> and an AWS doc URL is not ready to present — fill it, or move the signal to **Scope not covered**
> with the reason. Prose does not substitute for the table.

## Prescription

Differs by locus — keep only the matching block. Each one *names* the owner; the host
investigation offers the load and the operator applies the change.

- **`PROVIDER`** (managed binding): `<retry with exponential backoff / fail over via cross-region
  inference profile in region <alt-region>>`. **No customer-side configuration change is indicated
  by the model-path signals.** Resilience hardening for the next event is optional, not a fix.
- **`PROVIDER`** (`third-party` binding): name the vendor's status page as the evidence you cannot
  read, and say the locus rests on the absence of a customer-side signal rather than on a
  provider-side one.
- **`INFRASTRUCTURE`:** `<the serving or network gap>`; owner is
  `<capacity-and-quota for quota posture / sagemaker-serving for endpoint sizing /
  host-investigation for compute, container and network>`.
- **`APPLICATION`:** `<the specific change>`; owner is `<bedrock-configuration for access,
  model lifecycle and inference profiles / agent-runtime for an agentcore loop /
  retrieval for retrieval / guardrails for filter behaviour /
  output-quality for output quality / caller for request shape>`.
- **`UNDETERMINED`:** name the entrance and the missing fact. Do not assert the configuration is
  broken and do not pick a binding to make the report feel complete.

## Telemetry gaps that limited this triage

| check-id | gap | impact on triage |
|---|---|---|
| `<LLM-TEL-...>` | `<what was missing>` | `<what could not be isolated as a result>` |

> If none limited the triage, state "No telemetry gaps affected this triage."

## Scope not covered

- Regions skipped: `<regions / none>`
- Checks blocked by permissions: `<API + resource you could not read / none>`
- Metrics with no datapoints: `<metric names / none>`
- Other disclosed assumptions: `<region-unsupported feature, budget bound, etc. / none>`
