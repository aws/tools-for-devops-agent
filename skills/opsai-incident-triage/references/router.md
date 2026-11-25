# Router

Match what the operator says to the first read and the files to load. Paths are relative to the skill root.

**Bind, then route.** Resolve the hosting binding from `references/hosting-bindings.md` before using
this table — every metric name below is the `bedrock` binding's, and the row is still correct for
another binding only once its triple is substituted. Which call to make is in
`references/collection-reference.md`; how to read each API and metric is in
`references/metrics-and-logs.md`. Load both with any row.

The `First read` column names the **stage** first, because a symptom points at a stage before it
points at a metric. Stage numbers are `references/request-path.md`.

| Operator says | Stage | First read (`bedrock` binding) | Load |
|---|---|---|---|
| Is this AWS or mine, is this on our side | 4 | `health:DescribeEvents` for an active provider event in the region | `references/transient-vs-config-classifier.md` (Steps 1-2) |
| Getting 500s / InternalServerError | 4 | `SERVER_ERRORS` rate by `ModelId` across models. **Self-hosted model** (vLLM, TGI, a container on EKS/ECS/EC2): the customer is the provider, so a serving-layer 5xx is `locus=INFRASTRUCTURE`, never `PROVIDER`, and there is no Health event to check | `references/transient-vs-config-classifier.md` (Steps 1-2), `references/hosting-bindings.md` |
| ServiceUnavailableException / ModelNotReadyException | 4 | Invocation-log scan for provider-side exception dominance | `references/incident-signatures.md` (Step 5) |
| Throttling exception, throttled but quota looks fine | 4, then 7 | `THROTTLES` vs applied quota; backoff present. Read `InvocationThrottles` per `ModelId` **and with no dimension**: requests that fail before model resolution are published without `ModelId`, so the per-model sum can undercount. Compare its climb with `Invocations` growth: throttles that rise with your own traffic are quota-driven (customer side); throttles across unrelated models with flat traffic plus a Health event lean service-side. **If `AWS/Bedrock` shows no throttles**, read `AWS/Bedrock/Guardrails` `InvocationThrottles` (dimension `Operation=ApplyGuardrail`): an `ApplyGuardrail` rate quota throttles while the model's own metrics stay clean | `references/incident-signatures.md` (LLM-INV-007, LLM-INV-002) |
| Latency spiked with no config change | 4, then 6 | `InvocationLatency` p90/p99 vs baseline; blast radius then Health | `references/incident-signatures.md` (Steps 3-4) |
| TimeToFirstToken degraded | 4 | `TimeToFirstToken` trend, one model vs many | `references/metrics-and-logs.md` |
| Slower after moving the app to another Region than the model / calling Bedrock in a different Region | 1, then 4 | `InvocationLatency` and `TimeToFirstToken` vs the pre-move baseline, plus the caller's own client-side timing. AWS defines `InvocationLatency` as the time from when a request is sent to when the last token is received, so never claim it excludes network time and never rule the cross-Region hop in or out from it alone; no client-side per-stage timing is LLM-TEL-001. Options: call Bedrock in the caller's Region, or a geographic [cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) profile. Locus `APPLICATION`, `PERSISTENT` | `references/incident-signatures.md`, `references/request-path.md` |
| Not responding / hangs / times out | 2, then 4 | ingress 5xx before the loop runs, then model latency | `references/request-path.md` |
| Agent loop returns nothing / empty responses | 3, then 7, then 5 | **bind first.** `agentcore`: resolve alias to version, then guardrail intervention and finish reason. Self-hosted: the loop's own logs — there is no alias | `references/api-quirks.md` (§6, §11), `references/request-path.md` |
| Model-backed feature failing while Bedrock metrics look normal; onset matches a dependency incident (vector store, retrieval, a downstream API) | 5 or 6, then 4 | The dependency, not the model: (1) `Invocations` across the onset, since a dip means requests failed before reaching the model; (2) the application's traces or logs for the **first failing span** (embedding call, vector query, prompt assembly, model call), and no per-stage spans is LLM-TEL-001; (3) the retrieval result itself: result count and prompt size on failing vs healthy requests, because an empty or partial context makes a successful model call return a bad answer; (4) after a restore or re-index, whether the query embedding model and vector dimension still match the index (general vector-search knowledge, no check-id); (5) a Bedrock knowledge base: ingestion-job history (LLM-KB-001), since its retrieval errors are not in the model invocation metrics. Locus `APPLICATION` (stage 5/6 is the customer's dependency); transience by whether failures stopped when the dependency recovered. Say whether the feature should degrade gracefully: a timeout and circuit breaker around the dependency with a defined fallback, and retries capped so the outage does not become model throttling | `references/request-path.md`, `references/api-quirks.md` (§8) |
| Retrieval returns nothing | 5 | Ingestion-job history, not resource status | `references/api-quirks.md` (§8) |
| Worked in test, not in production | 3, then 4 | configuration divergence between environments | `references/request-path.md` |
| Can I even tell what my agent is doing | all | Stage-level telemetry and trace-context propagation | `references/checks-telemetry.md` (LLM-TEL-001, LLM-TEL-003) |

The empty-response row is the one that used to assume its answer. "Resolve alias to version" is a
Bedrock Agents operation and means nothing for a loop running in a Lambda. Bind, then read.

## Routing triggers

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
| "do you see any errors", "any errors in the last N hours" | a status check is an incident question with the incident word removed — see the entrance rule in `classifier-walkthrough.md` §1 |
| "is anything wrong with our model calls", "is this on my side" | the core question this skill exists for |
| "is this signal healthy", "absent signal versus healthy signal", "is the metric just empty" | the `measured 0` / `no-datapoints` / `not-queried` distinction is this skill's, and a healthy ledger still rules at R5 |

A question on this list that reaches a different skill, or is answered with no `TRIAGE:` line, is a
routing failure and not a style choice. Two exclusions:

- Truncated or cut-off model output is **not** on this list — finish-reason work is the
  `output-quality` track (see *Related skills (optional)*).
- None of these rows fires before the load condition holds. "Do you see any errors" about a workload
  with no model call identified in its failing path is a general investigation question, not this
  skill's.

