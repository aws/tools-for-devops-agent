# SageMaker Serverless & Asynchronous Inference — Health Report
> Read-only posture review of Amazon SageMaker serverless and asynchronous inference endpoints.
> Every finding carries an `LLM-SM-SERVE-*` check-id, a catalog severity, and the observed evidence.
> No endpoint was mutated. Account IDs and secret values are redacted.
## Scope
- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Endpoints reviewed:** `<count and names, by mode: serverless / async>`
- **Window:** `<metric lookback window, e.g. last 14 days>`
- **Not covered (disclosed):** `<endpoints / regions / checks skipped, with reason — permissions, budget, region-unsupported>`
## Per-Endpoint Config
| Endpoint | Mode | `ServerlessConfig` (`MaxConcurrency`, `ProvisionedConcurrency`) | `AsyncInferenceConfig.OutputConfig.NotificationConfig` (success / error topics) | Scaling on `ApproximateBacklogSizePerInstance`? | `CurrentInstanceCount` + recent `Invocations` |
|---|---|---|---|---|---|
| `<name>` | `<serverless / async>` | `<n / n or not set / n-a>` | `<both / one / none / n-a>` | `<yes / no / n-a>` | `<n, datapoints present / none>` |
> `InService` with `CurrentInstanceCount` = 0 is the scale-to-zero case, not proof of serving
> (api-quirks §2). Confirm instance count, backlog and recent `Invocations` before calling it healthy.
## Signals Read
| Signal | Source | Window | Observed value or "no datapoints" | Linked check |
|---|---|---|---|---|
| Cold start | `AWS/SageMaker` / `ModelSetupTime` | `<window>` | `<value / no datapoints>` | LLM-SM-SERVE-001 |
| Throttling vs `MaxConcurrency` | invocation throttle metrics | `<window>` | `<value / no datapoints>` | LLM-SM-SERVE-002 |
| Async queue depth | `AWS/SageMaker` / `ApproximateBacklogSizePerInstance` | `<window>` | `<value / no datapoints>` | LLM-SM-SERVE-004 |
> No datapoints ≠ zero (api-quirks §1). An absent `ModelSetupTime` is not "no cold start", and an
> absent backlog is not "empty queue".
## Fit Decision (LLM-SM-SERVE-005)
| Endpoint | Payload size | Invocation duration / latency | Traffic shape | Better fit | Evidence |
|---|---|---|---|---|---|
| `<name>` | `<observed>` | `<observed>` | `<steady / spiky / low-volume>` | `<real-time / async / serverless>` | `<config + metric values>` |
> This skill owns the serverless/async fit decision. The endpoints skill's LLM-SM-008 is only the
> real-time idle-cost signal.
## Findings
| check-id | severity | endpoint | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-SERVE-00X` | `<catalog severity>` | `<name>` | `<concrete observed value>` | `<exact CLI/IaC command>` |
Only findings backed by an observed value appear here (evidence or silence). Each severity is the
catalog severity; a tuning threshold AWS does not publish is marked `workload-specific`.
## Prioritized Recommendations
1. `<HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`
