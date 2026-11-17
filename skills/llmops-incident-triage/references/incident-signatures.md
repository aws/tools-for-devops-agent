# LLM Incident Signatures

A lookup table from an observed symptom to the first signal to check, the read-only APIs that produce
that signal, the likely fault locus from the classifier, and the trap that most often
causes a misread. **This is a starting-point index, not a shortcut around the classifier** — always
confirm by running `transient-vs-config-classifier.md` end to end. A "likely locus" here
is the prior, not the ruling.

**Every metric name below is the `bedrock` binding's.** Bind at Step 0 (`hosting-bindings.md`) and
substitute. The locus column gives the **managed-binding** prior: on a self-hosted binding every
`PROVIDER` prior reads `INFRASTRUCTURE`, because the customer is the provider there; on `third-party`
a `PROVIDER` prior is a hypothesis resting on absence of a customer-side signal.
**No row here is a precondition on the classifier.** These rows select which evidence to gather; they
never gate whether a locus is rendered. A check-id whose detection rule needs a non-zero signal is a
rule about whether that *finding* fires, never a rule about whether the ladder runs — a ledger of zeroes
is a complete ledger and rules at R5. No symptom has to match for a locus to be required.

Locus: `PROVIDER` (the entity serving the model; retry/failover) · `INFRASTRUCTURE` (the customer's own
serving or network layer) · `APPLICATION` (caller, request shape, orchestration, identity) ·
`UNDETERMINED` (Step 0 could not bind, or R3/R4 fired). See `transient-vs-config-classifier.md`.

| Symptom | First signal to check | APIs to call | Likely locus | Notes / trap |
|---|---|---|---|---|
| `ThrottlingException` in logs/responses | `THROTTLES` trend vs applied quota; is backoff present? | `cloudwatch:GetMetricData` (`InvocationThrottles`, `EstimatedQuotaConsumption`), invocation-log scan | APPLICATION, or INFRASTRUCTURE if quota posture | Throttling is a 4xx client signal — under-provisioned quota or missing backoff/jitter. Only leans service-side if it coincides with a broad regional event. Remediate via inference profile / backoff (LLM-INV-002, LLM-INV-007). |
| `THROTTLES` climbing steadily | Rate of climb vs traffic growth; single vs many models | `cloudwatch:GetMetricData` (`InvocationThrottles`, `Invocations` by `ModelId`) | INFRASTRUCTURE | Climbing with your own traffic growth = quota pressure (your config). Simultaneous climb across unrelated models in a region can indicate regional capacity → check Health. |
| `ThrottlingException` but `AWS/Bedrock` shows no `InvocationThrottles` | Guardrail throttling on `ApplyGuardrail` | `cloudwatch:GetMetricData` (`AWS/Bedrock/Guardrails` `InvocationThrottles`, dimension `Operation=ApplyGuardrail`), `bedrock:GetGuardrail` | INFRASTRUCTURE | The model's own metrics stay clean while the guardrail's rate quota throttles, so a check of `AWS/Bedrock` alone reports "no throttling" and is wrong. Remediation owner: `llmops-guardrails` (guardrail limits) or `llmops-capacity-cost` (quota increase). |
| 5xx / 503 from a self-hosted model server | Target 5xx and target health on the load balancer in front of it | `cloudwatch:GetMetricData` (`AWS/ApplicationELB` `HTTPCode_Target_5XX_Count`, `UnHealthyHostCount`) | INFRASTRUCTURE | The customer is the provider, so `PROVIDER` has no referent and there is no AWS Health event for the model. Never prescribe cross-Region inference for a self-hosted model. |
| `InternalServerError` / generic 5xx | Server-error rate across multiple models; AWS Health | `health:DescribeEvents`, `cloudwatch:GetMetricData` (`InvocationServerErrors` by `ModelId`) | PROVIDER | 5xx dominating with no correlated customer change and broad blast radius → service-side. Do NOT prescribe config fixes. Confirm onset is uncorrelated with a deploy (classifier Step 4). |
| `ServiceUnavailableException` | Presence/dominance of the exception; Health events | `health:DescribeEvents`, invocation-log error-pattern scan | PROVIDER | This is a service-side exception signature (classifier Step 5). Recommend retry with exponential backoff + jitter, or cross-region failover. |
| `ModelNotReadyException` | Whether it clusters at cold-start / low-traffic model; is it one model? | invocation-log scan, `cloudwatch:GetMetricData` (`Invocations`, `TimeToFirstToken`) | PROVIDER | Model warm-up / readiness is service-side. Transient and self-resolving; retry/backoff. If persistent for one model only, cross-check model lifecycle (could be deprecation/EOL, LLM-INV-003). |
| `ValidationException` | Request shape, parameter support, context length | invocation-log error-pattern scan (`ValidationException`) | APPLICATION | Malformed request / unsupported parameter / context too long. Purely client-side; never a service transient. Fix the request (LLM-INV-011). |
| Intermittent timeouts | Latency distribution (p90/p99) vs baseline; stage isolation | `cloudwatch:GetMetricData` (`InvocationLatency` p50/p90/p99), AgentCore spans | UNDETERMINED | Could be service-side latency or a client timeout set too low. Isolate the stage (telemetry) before ruling. "No datapoints" ≠ zero (api-quirks §10). |
| Agent loop returning empty / blank responses | **Bind first.** `agentcore`: alias → version resolution, guardrail intervention, finish reason. Self-hosted: the loop's own logs | `bedrock-agent:GetAgent`/`GetAgentAlias`, `cloudwatch:GetMetricData` (`AWS/Bedrock/Guardrails` `InvocationsIntervened`), log `stopReason` scan | APPLICATION | `PREPARED` status ≠ what the alias serves (api-quirks §6) — resolve alias→version **on an `agentcore` binding**. There is no alias on any other binding, and reaching for one is a category error. Guardrail blocking (`guardrail_intervened`) looks like "empty" but is the guardrail working (api-quirks §11). |
| Not responding at all / hangs | Ingress 5xx before the loop runs, then model latency | load-balancer or API Gateway metrics, then the bound latency metric | INFRASTRUCTURE | An unreached model and a slow model look identical from the caller. Start at request-path stage 2, not stage 4 (`request-path.md`). |
| Retrieval returning nothing | Ingestion-job history, not resource status | `bedrock-agent:ListIngestionJobs`/`GetIngestionJob`, `bedrock-agent:GetKnowledgeBase` | APPLICATION | KB `ACTIVE` ≠ data ingested (api-quirks §8). Empty vector store returns nothing even when wiring is valid. Verify a `StartIngestionJob` completed (LLM-KB-001). |
| Latency spike with no config change | Server latency vs AWS Health; blast radius | `health:DescribeEvents`, `cloudwatch:GetMetricData` (`InvocationLatency`, `InvocationServerErrors`) | PROVIDER | "No config change" + abrupt onset + broad blast radius leans service-side (classifier Steps 3–4). Confirm against deployment markers that nothing changed customer-side. |
| `TimeToFirstToken` degradation (streaming) | `TimeToFirstToken` trend; one model vs many | `cloudwatch:GetMetricData` (`TimeToFirstToken` by `ModelId`) | UNDETERMINED | Degradation across many models/accounts → service-side capacity. For one model only, could be regional capacity for that model or prompt bloat inflating queue time — isolate with token-count metrics before ruling. |

## How to use this table

1. Match the observed symptom to a row.
2. Pull the **first signal** using the listed read-only APIs.
3. Treat the **likely locus** as a prior, then run the full `transient-vs-config-classifier.md`
   decision tree to render the actual locus — the classifier's blast-radius, onset-timing, and
   client-vs-server steps override the prior whenever they disagree. Step 0's binding overrides the
   metric names in the row.
4. Before interpreting any API response, consult `api-quirks.md` for the traps noted in the row —
   several of these symptoms (empty agent response, empty KB, "no datapoints") are routinely misread.

## AWS-doc-citation

https://docs.aws.amazon.com/bedrock/latest/userguide/troubleshooting.html
