# AgentCore Observability — Check Catalog

Full catalog of checks the skill runs. Each check is tagged **VERIFY** (confirmable via a read-only
API) or **PRESCRIBE** (cannot be read; validate the effect and emit steps). Every finding gets a
severity: CRITICAL / HIGH / MEDIUM / LOW / INFO.

All operations are read-only. Never mutate IAM, configuration, or resources.

---

## Account-level prerequisites

| # | Check | Type | API / signal | Pass condition | Fail severity |
|---|-------|------|--------------|----------------|---------------|
| A1 | CloudWatch Transaction Search enabled | VERIFY (Tier 2) | `xray:GetTraceSegmentDestination` | `Destination = CloudWatchLogs` and `Status = ACTIVE` | CRITICAL |
| A2 | Transaction Search (inferred) | VERIFY (Tier 1) | span log streams receiving data | spans present after invocations | CRITICAL (inferred) |

Transaction Search is the most common silent root cause: without it, AgentCore cannot deliver spans
to CloudWatch Logs, so traces never appear even when the agent runs and instrumentation is correct.

---

## Runtime agents (`/aws/bedrock-agentcore/runtimes/<agent_id>-<endpoint>`)

| # | Check | Type | API / signal | Pass condition | Fail severity |
|---|-------|------|--------------|----------------|---------------|
| R1 | Agent log group exists | VERIFY (Tier 1) | `logs:DescribeLogGroups` prefix `/aws/bedrock-agentcore/runtimes/` | log group present | HIGH |
| R2 | Runtime logs arriving | VERIFY (Tier 1) | `logs:FilterLogEvents` on `runtime-logs` stream, last 24h | recent events after invocations | HIGH |
| R3 | Spans flowing | VERIFY (Tier 1) | `spans` stream in agent log group **or** shared `aws/spans` | spans present after invocations | CRITICAL |
| R4 | Session metrics emitting | VERIFY (Tier 1) | `cloudwatch:ListMetrics` namespace `bedrock-agentcore` | metrics present | MEDIUM |
| R5 | Runtime tracing / ADOT not disabled | VERIFY (Tier 2) | `bedrock-agentcore:GetAgentRuntime` env | `DISABLE_ADOT_OBSERVABILITY` not unintentionally `true` | HIGH |
| R6 | Span destination mode | VERIFY (Tier 2) | `GetAgentRuntime` env `UNIFIED_TRACES_DESTINATION_ENABLED` | matches intended destination | INFO/LOW |
| R7 | X-Ray resource policy on log group | VERIFY (Tier 2) | `logs:DescribeResourcePolicies` | policy allows `xray.amazonaws.com` `logs:PutLogEvents` on the agent log group | HIGH — **only when the agent uses the unified span destination** (R6). If the agent delivers to the shared `aws/spans` group, this per-runtime policy is not required — mark N/A, do not flag. |
| R8 | ADOT distro in requirements | PRESCRIBE | — | `aws-opentelemetry-distro>=0.10.0` (≥0.18.0 for unified spans) present | HIGH (if spans absent) |
| R9 | `opentelemetry-instrument` launch | PRESCRIBE | — | agent launched via `opentelemetry-instrument python main.py` | HIGH (if spans absent) |
| R10 | Framework tracing + auto-instrumentor | PRESCRIBE | — | framework emits OTEL (Strands tracer / `opentelemetry-instrumentation-langchain` / OpenInference / Openllmetry / OpenLit / Traceloop) | MEDIUM |
| R11 | Session-id propagation | PRESCRIBE | — | `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id` set on invoke | LOW |

---

## Memory & Gateway resources

Default vended log group: `/aws/vendedlogs/bedrock-agentcore/{memory|gateway}/APPLICATION_LOGS/{resource-id}`

| # | Check | Type | API / signal | Pass condition | Fail severity |
|---|-------|------|--------------|----------------|---------------|
| M1 | Log delivery configured | VERIFY (Tier 2) | `logs:DescribeDeliverySources` / `DescribeDeliveries` | `APPLICATION_LOGS` source bound to the resource ARN with an active delivery | HIGH |
| M2 | Logs arriving | VERIFY (Tier 1) | `logs:FilterLogEvents` on the vended log group | recent events | MEDIUM |
| M3 | Tracing delivery configured | VERIFY (Tier 2) | `DescribeDeliveries` for a `TRACES`→XRAY delivery | traces delivery present | MEDIUM |
| M4 | Tracing enabled (resource) | PRESCRIBE | — | tracing toggle enabled on the memory/gateway resource | MEDIUM |

---

## Built-in tools (code interpreter, browser)

| # | Check | Type | Pass condition | Fail severity |
|---|-------|------|----------------|---------------|
| B1 | Custom log output configured | PRESCRIBE | customer emits logs from tool code to a log destination | MEDIUM |
| B2 | Telemetry arriving | VERIFY (Tier 1) | target log group receiving data (only if B1 present) | LOW |
| B3 | Trace headers on tool APIs | PRESCRIBE | `X-Amzn-Trace-Id` / `traceparent` passed to Start*/Invoke*/Stop* APIs | LOW |

---

## Non-runtime hosts

| # | Check | Type | API / signal | Pass condition | Fail severity |
|---|-------|------|--------------|----------------|---------------|
| L1 | Lambda OTEL layer + wrapper | VERIFY (Tier 3) | `lambda:GetFunctionConfiguration` | OTEL Layer attached and `AWS_LAMBDA_EXEC_WRAPPER=/opt/otel-instrument` | HIGH |
| L2 | Lambda agent log-group env | VERIFY (Tier 3) | `GetFunctionConfiguration` env | agent log group + OTEL vars set | HIGH |
| E1 | ECS OTEL env in task def | VERIFY (Tier 3) | `ecs:DescribeTaskDefinition` | container env carries the OTEL variable set | HIGH |
| K1 | EKS telemetry arriving | VERIFY (Tier 1) | agent log group receiving data | events present | HIGH |
| K2 | EKS pod/ConfigMap OTEL env | PRESCRIBE | — | not IAM-verifiable (K8s RBAC); prescribe only | MEDIUM |
| X1 | On-prem / multi-cloud OTEL env + creds | PRESCRIBE | — | full ADOT SDK env + IAM creds/Roles Anywhere + outbound HTTPS to OTLP endpoint | MEDIUM |

---

## Notes

- **ADOT Collector is not supported** for agent observability. Use the ADOT SDK or the AWS Lambda
  Layer for OpenTelemetry only.
- Unified span destination (spans in the agent's own log group instead of shared `aws/spans`)
  requires **ADOT ≥ 0.18.0** and the X-Ray log-group resource policy (R7). Earlier versions ignore
  the setting and deliver to `aws/spans`.
- Cross-service trace correlation requires W3C Trace Context (`traceparent`) propagation.
