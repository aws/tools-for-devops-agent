# SageMaker Inference Endpoint — Health Report

> Area: real-time endpoint. Serverless/async endpoints and batch transform jobs use their own report templates in this skill.

> Read-only posture and right-sizing review of Amazon SageMaker real-time inference endpoints.
> Every finding carries an LLM-SM `check-id`, a catalog severity, and the observed evidence.
> No endpoint was mutated. Account IDs and secret values are redacted.

## Scope

- **Account:** `<alias or "the account under review" — never a raw 12-digit ID>`
- **Region(s):** `<regions reviewed>`
- **Endpoints reviewed:** `<count and names>`
- **Window:** `<metric lookback window, e.g. last 14 days>`
- **Not covered (disclosed):** `<endpoints / regions / checks skipped, with reason — permissions, budget, region-unsupported>`

## Per-Endpoint State

| Endpoint | Variant | EndpointStatus | CurrentInstanceCount | Instance type | Serving? (status + count + recent Invocations) |
|---|---|---|---|---|---|
| `<name>` | `<variant>` | `<InService/…>` | `<n>` | `<type>` | `<yes/no — InService alone is NOT proof>` |

> `InService` is control-plane state only. A variant can be `InService` with `CurrentInstanceCount` = 0
> and serve nothing (api-quirks §1). "Serving?" is answered from status **and** instance count **and**
> recent `Invocations` datapoints.

## Findings

| check-id | severity | endpoint / variant | observed evidence | remediation (recommended — operator runs it) |
|---|---|---|---|---|
| `LLM-SM-00X` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<name/variant>` | `<concrete observed value>` | `<exact CLI/IaC command>` |

Only findings backed by an observed value appear here (evidence or silence). Thresholds AWS does not
publish are marked `workload-specific` at `INFO`.

## Right-Sizing Conclusion

State the conclusion **only** if both metric namespaces were read; otherwise disclose the gap.

- **Invocation metrics (`AWS/SageMaker`):** `<Invocations, InvocationsPerInstance, ModelLatency p90, OverheadLatency p90, Invocation5XXErrors over the window>`
- **Instance resource metrics (`/aws/sagemaker/Endpoints`):** `<CPUUtilization, MemoryUtilization, GPUUtilization, GPUMemoryUtilization averages/sustained>`
- **Conclusion:** `<oversized / under-used GPU / idle / appropriately sized / INDETERMINATE — one namespace unavailable>`
- **Supporting checks:** `<LLM-SM-003 / 005 / 008 / 010 as applicable>`

> No datapoints ≠ zero. An endpoint with no invocation datapoints at all is idle/abandoned, not a
> measured zero (api-quirks §3).

## Alarm Coverage

| recommended alarm | metric | present? | linked check |
|---|---|---|---|
| 5xx errors | `AWS/SageMaker` / `Invocation5XXErrors` | `<yes/no>` | LLM-SM-009 |
| Model latency | `AWS/SageMaker` / `ModelLatency` | `<yes/no>` | LLM-SM-009 |
| Resource saturation | `/aws/sagemaker/Endpoints` / `CPUUtilization`, `MemoryUtilization` | `<yes/no>` | LLM-SM-009 |

See `references/cloudwatch-alarm-reference.md` for statistics, periods, and threshold sources.

## Prioritized Recommendations

1. `<CRITICAL/HIGH first — check-id, what to change, exact command, SLA from the severity table>`
2. `<...>`

## Container Environment (if inspected)

Report environment variables on the model container by **key name only** — never a value.

- `<ENV_KEY_1>` — present
- `<ENV_KEY_2>` — present
