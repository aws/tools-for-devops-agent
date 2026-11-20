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
| Throttling exception, throttled but quota looks fine | 4, then 7 | `THROTTLES` vs applied quota; backoff present. **If `AWS/Bedrock` shows no throttles**, read `AWS/Bedrock/Guardrails` `InvocationThrottles` (dimension `Operation=ApplyGuardrail`): an `ApplyGuardrail` rate quota throttles while the model's own metrics stay clean | `references/incident-signatures.md` (LLM-INV-007, LLM-INV-002) |
| Latency spiked with no config change | 4, then 6 | `InvocationLatency` p90/p99 vs baseline; blast radius then Health | `references/incident-signatures.md` (Steps 3-4) |
| TimeToFirstToken degraded | 4 | `TimeToFirstToken` trend, one model vs many | `references/metrics-and-logs.md` |
| Not responding / hangs / times out | 2, then 4 | ingress 5xx before the loop runs, then model latency | `references/request-path.md` |
| Agent loop returns nothing / empty responses | 3, then 7, then 5 | **bind first.** `agentcore`: resolve alias to version, then guardrail intervention and finish reason. Self-hosted: the loop's own logs — there is no alias | `references/api-quirks.md` (§6, §11), `references/request-path.md` |
| Retrieval returns nothing | 5 | Ingestion-job history, not resource status | `references/api-quirks.md` (§8) |
| Worked in test, not in production | 3, then 4 | configuration divergence between environments | `references/request-path.md` |
| Can I even tell what my agent is doing | all | Stage-level telemetry and trace-context propagation | `references/checks-telemetry.md` (LLM-TEL-001, LLM-TEL-003) |

The empty-response row is the one that used to assume its answer. "Resolve alias to version" is a
Bedrock Agents operation and means nothing for a loop running in a Lambda. Bind, then read.
