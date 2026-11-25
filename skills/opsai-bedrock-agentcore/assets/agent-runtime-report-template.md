# OpsAI Agent & Runtime Health Report

Fill in every `<placeholder>`. Delete a row only when the check genuinely does not apply, and when you
do, say why in **Scope not covered**. Never leave a placeholder unresolved in a delivered report.

## Scope

- **Service reviewed:** `<Bedrock Agents (LLM-AGT) | Bedrock AgentCore (LLM-AC) | both>`
- **Region examined:** `<region>`
- **Resources in scope:** `<agent ids / runtime ids — mask account segments in any ARN>`
- **Time window (for activity/idle checks):** `<start-ts>` → `<end-ts>` (`<tz>`)

## Agent / runtime identity

- **Bedrock Agent:** alias `<alias>` → resolved version `<version>` (NOT the DRAFT) — see LLM-AGT-007.
- **AgentCore runtime:** version `<version>`, status `<status>`, role `arn:aws:iam::<account>:role/<name>`.

> Resolve the alias to its served version before stating what production runs. A `PREPARED` DRAFT is
> not what the alias serves (`api-quirks.md` §6).

## Findings

| check-id | severity | observed value | remediation |
|---|---|---|---|
| `<LLM-AGT-### / LLM-AC-###>` | `<CRITICAL/HIGH/MEDIUM/LOW/INFO>` | `<concrete value that triggered it>` | `<exact read-only-recommended fix>` |
| `<...>` | `<...>` | `<...>` | `<...>` |

> No freelance findings — every row cites a catalog `check-id` and that check's severity. Never invent a
> threshold: no AWS-published number → `INFO`, marked `workload-specific`.

## Observability posture

| check-id | signal | present? | impact if missing |
|---|---|---|---|
| LLM-AC-005 | Stage-level OTLP telemetry | `<yes / no / not checked>` | Slowness cannot be isolated to a stage |
| LLM-AC-006 | Trace-context propagation across hops | `<yes / no / not checked>` | A request cannot be followed end-to-end |
| LLM-AC-007 | Structured JSON logs | `<yes / no / not checked>` | Logs Insights queries are unreliable |
| LLM-AGT-005 | Agent tracing enabled & persisted | `<yes / no / not checked>` | No record of orchestration/tool/KB reasoning |

## Prescription

For each finding, state the exact read-only-recommended change (CLI/IaC) and let the user run it. Order
by severity (CRITICAL first). Do not mutate any resource.

## Disclosed permission gaps

> AgentCore reads (`bedrock-agentcore` namespace) are NOT granted by the default
> `AIDevOpsAgentAccessPolicy`. If an AgentCore read was denied, record it here as a permission gap — not
> as an absent resource.

- APIs/resources denied: `<API + resource (masked) you could not read / none>`

## Scope not covered

- Regions skipped: `<regions / none>`
- Checks blocked by permissions: `<API + resource you could not read / none>`
- Metrics with no datapoints: `<metric names / none>`
- Other disclosed assumptions: `<region-unsupported feature, budget bound, etc. / none>`
