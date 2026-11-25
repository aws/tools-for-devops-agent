# The request path — stages, ownership, and what each contributes

## Contents

- [Why a path replaces a service list](#why-a-path-replaces-a-service-list)
- [The seven stages](#the-seven-stages)
- [Walking the path](#walking-the-path)
- [Symptom to first stage](#symptom-to-first-stage)
- [Stage to peer skill](#stage-to-peer-skill)
- [What this skill does not do](#what-this-skill-does-not-do)

## Why a path replaces a service list

Organising triage by AWS service answers "what could be wrong with Bedrock". Operators do not ask
that. They say a thing stopped working and expect the question "where in the path did it stop" to be
answered before any service is named.

The path is hosting-independent. Every LLM workload has these stages whether the model runs in
Bedrock, on a SageMaker endpoint, in a container the customer built, or behind someone else's API.
Binding the stages to metric names is `references/hosting-bindings.md`; this file is the shape.

## The seven stages

| # | Stage | Fails as | Locus when it fails |
|---|---|---|---|
| 1 | **caller** — the client or upstream service issuing the request | timeouts never reaching the model, retry storms, malformed requests | `APPLICATION` |
| 2 | **ingress** — ALB, API Gateway, CloudFront, service mesh | 5xx before the agent runs, TLS failures, connection rejection | `INFRASTRUCTURE` |
| 3 | **agent loop** — orchestration: prompt assembly, tool selection, turn management | empty output, infinite loops, context overflow, no traces | `APPLICATION` |
| 4 | **model endpoint** — the inference call itself | throttles, server errors, latency, access denial | `PROVIDER` or `INFRASTRUCTURE`, by binding |
| 5 | **retrieval** — vector search, knowledge base, any context fetch | empty or stale context, retrieval latency, ingestion staleness | `APPLICATION` |
| 6 | **tools / actions** — functions and APIs the loop calls | tool errors surfacing as model failure, tool latency dominating | `APPLICATION` |
| 7 | **output filter** — guardrail, moderation, post-processing | blocked or masked output read as an outage | `APPLICATION` |

Stage 4 is the only stage whose locus depends on the binding, which is why the binding is
established before the walk rather than during it.

## Walking the path

**Walk from the symptom, not from stage 1.** The symptom names where the operator is standing; the
walk establishes how far in the failure reaches. Three rules:

1. **Stop at the first stage carrying measured evidence.** A stage with a measured failure signal is
   where triage reports. Continuing past it to collect a complete picture of every stage is how a
   single turn runs out without a finding.
2. **A stage with no telemetry is a finding, not a pass.** An agent loop emitting nothing is
   `LLM-TEL-001`. Record it; do not treat the silence as health and move on.
3. **Never attribute across a stage you did not read.** If stages 3 and 4 both lack signal, the
   locus is `UNDETERMINED`, not "probably the model".

## Symptom to first stage

| The operator says | Start at | Because |
|---|---|---|
| "not responding", "hangs", "times out" | 2, then 4 | an unreached model and a slow model look identical from the caller |
| "returns nothing", "empty answer" | 3, then 7, then 5 | an empty body with a successful call is assembly, filtering or missing context — not an error |
| "errors", "5xx", "429" | 4 | the only stage that emits a provider-shaped error code |
| "slow" | 4, then 6 | tool latency is routinely mistaken for model latency |
| "slower since we moved the app to another Region than the model" | 1, then 4 | the cross-Region hop is paid by the caller on every call and multiplies across sequential calls; `InvocationLatency` (request sent to last token received) cannot rule it in or out alone, and missing client-side timing is LLM-TEL-001. Options: call Bedrock in the caller's Region, or a geographic [cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) profile for the caller's geography (requests may be routed within that geography) |
| "wrong or stale answers" | 5 | retrieval before the model; this is also where the `output-quality` track takes over |
| "blocked", "refused to answer" | 7 | a working filter presents as an outage |
| "worked in test, not in production" | 3, then 4 | configuration divergence between environments, not a service fault |

"Returns nothing" is the entry most often misrouted, and the row above is the tiebreak: **an empty
body on a successful call is not an error**, so it starts at the assembly and filtering stages rather
than the model.

## Stage to owner track
Depth on one stage is optional. This table names the owner track for each stage; `related-skills.md`
maps each track to the skill that covers it and the fallback to run when that skill isn't installed.
| Stage | Binding | Owner track | Returns (only from that skill) |
|---|---|---|---|
| 3 agent loop | `agentcore` | `agent-runtime` | `LLM-AGT` rows |
| 3 agent loop | self-hosted | `host-investigation`: investigate the compute with general tools | — |
| 4 model endpoint | `bedrock` | `bedrock-configuration` | `LLM-INV` rows |
| 4 model endpoint | `sagemaker` | `sagemaker-serving` | `LLM-SM`, `LLM-SM-SERVE` and `LLM-SM-BATCH` rows |
| 4 model endpoint | any, capacity or quota | `capacity-and-quota` | quota and spend rows |
| 5 retrieval | `bedrock` knowledge base | `retrieval` | `LLM-KB` rows |
| 7 output filter | Bedrock Guardrails | `guardrails` | `LLM-GRD` rows |
| output quality, truncation | any | `output-quality` | `LLM-EVAL` rows |
| who may call the model | `bedrock` | `caller-identities` | access rows |

Two kinds of row have no skill behind them. A self-hosted agent loop and the compute beneath it are
investigated with general tools, not with this library. Saying so is more useful than
stretching a Bedrock-shaped check over a container.

## What this skill does not do

- **It does not discover the workload.** Topology, entry points and recent change history come
  first, from general investigation, before this skill applies.
- **Its locus is not the whole root cause.** The model-path locus is weighed with everything else
  the investigation found before you conclude.
- **It does not cover every stage.** It names which stage needs depth and which skill owns it; load
  that skill when the evidence points there.
