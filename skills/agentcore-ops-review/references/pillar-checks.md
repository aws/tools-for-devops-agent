# AgentCore Check Definitions — Detailed Reference

All checks are read-only. They derive from control-plane APIs and CloudWatch metrics, plus a single data-plane call — `bedrock-agentcore:ListMemoryRecords` — used **only** to count long-term memory records (its `content` field is never read; see "Memory record data handling" in `SKILL.md`). No agent is invoked (`InvokeAgentRuntime`), and no prompts or responses are read. A finding is produced ONLY when the underlying signal is complete; incomplete signals become visibility limits, never false positives.

APIs authorize under the single IAM service prefix `bedrock-agentcore:` (this covers control-plane actions such as `ListAgentRuntimes`/`GetGateway` and the data-plane `ListMemoryRecords`). `bedrock-agentcore-control` is the SDK client name, not an IAM prefix. This namespace is NOT part of the standard `AIDevOpsAgentAccessPolicy`. See `iam-policy-linked-account.json`.

---

## Runtime Resilience Pillar — Reliability (4 checks)

Data collection:
- `bedrock-agentcore:ListAgentRuntimes` → `GetAgentRuntime` (status, `failureReason`, `networkConfiguration`, timestamps)
- `bedrock-agentcore:ListAgentRuntimeEndpoints` (status, `liveVersion`, `targetVersion`, name)
- `bedrock-agentcore:ListAgentRuntimeVersions` (latest version + count)
- `ec2:DescribeSubnets` (map VPC subnet IDs → AZ)

### AC-RUN-1: Runtime or Endpoint in Failed State
- **Source**: runtime `status`; endpoint `status`; `lastUpdatedAt`/`createdAt`
- **Failed states**: `CREATE_FAILED`, `UPDATE_FAILED`, `DELETE_FAILED`, `FAILED`
- **Transitional states**: `CREATING`, `UPDATING`, `DELETING`
- **Critical if**: runtime or any endpoint is in a failed state; OR stuck in a transitional state for > 1 hour
- **Evidence**: include `failureReason` when present
- **Remediation**: Investigate the failure reason, fix the root cause, redeploy or roll back to the last healthy version.

### AC-RUN-2: VPC Runtime Without Multi-AZ Subnets
- **Source**: `networkConfiguration.networkMode`; `networkModeConfig.subnets`; `ec2:DescribeSubnets` → `availabilityZone`
- **Applies to**: runtimes with `networkMode == VPC` and at least one subnet
- **N/A if**: `networkMode == PUBLIC` (AWS manages availability)
- **High if**: all resolved subnets are in a single AZ
- **Visibility limit if**: subnet details unreadable, or a subnet has no resolvable AZ
- **Key fact**: endpoints carry NO AZ data — AZ fault tolerance comes exclusively from VPC subnet placement
- **Remediation**: Add subnets in ≥ 1 additional AZ to the runtime's network configuration.

### AC-RUN-3: Endpoint Version Drift
- **Source**: endpoint `liveVersion` vs latest runtime version (from `ListAgentRuntimeVersions`)
- **Calculation**: `drift = latestVersion - liveVersion`
- **Medium if**: any live endpoint is `drift >= 3`
- **N/A if**: latest version cannot be determined (versions call incomplete)
- **Remediation**: Adopt a promotion cadence — validate new versions on a staging endpoint, promote production endpoints regularly to pick up fixes.

### AC-RUN-4: DEFAULT-Endpoint-Only Deployment
- **Source**: endpoint names; runtime `versionCount`
- **Low if**: the runtime's only endpoint is `DEFAULT` (auto-tracks latest) AND the runtime has 2+ versions (i.e. actively updated)
- **Rationale**: no environment-promotion strategy — every published version goes live to consumers immediately
- **Remediation**: Create pinned endpoints per environment (dev/staging/prod) so new versions are validated before serving production traffic.

---

## Gateway Health — Reliability (1 check, multi-signal)

Data collection:
- `bedrock-agentcore:ListGateways` → `GetGateway` (status, protocolType, authorizerType, `policyEngineConfiguration`)
- `bedrock-agentcore:ListGatewayTargets` → `GetGatewayTarget` (status, `targetConfiguration`, `lastSynchronizedAt`, `credentialProviderConfigurations`)

Target type derived from `targetConfiguration.mcp`: `lambda` → LAMBDA, `mcpServer` → MCP_SERVER, `apiGateway` → API_GATEWAY, `openApiSchema` → OPEN_API_SCHEMA, `smithyModel` → SMITHY_MODEL.

### GW-01: Gateway Health & Target Redundancy
- **Unhealthy target statuses**: `FAILED`, `UPDATE_UNSUCCESSFUL`, `SYNCHRONIZE_UNSUCCESSFUL`
- **Healthy target status**: `READY`
- **Stale sync**: `lastSynchronizedAt` older than 7 days
- **Policy engine attached**: `policyEngineConfiguration.arn` is present

Risk levels:
- **Critical**: gateway status != `READY`, OR total targets == 0, OR healthy targets == 0
- **Warning**: any unhealthy target, OR single target (no redundancy), OR no policy engine attached, OR stale sync detected
- **Healthy**: multiple READY targets, policy engine attached, recent synchronization

Best-practice signals:
- ≥ 2 targets per gateway to avoid a single point of failure
- Policy engine attached for authorization/rate limiting
- Target type diversity (e.g. Lambda + MCP Server) for failover
- Short-lived credentials with rotation on credential providers

**Remediation**: add a second target (ideally a different target type), attach a policy engine, and investigate stale-sync targets (broken connectivity or expired credentials).

---

## Memory & Knowledge Effectiveness — Performance Efficiency (4 checks)

**Strategy-aware:** read `GetMemory` strategies FIRST. Record-count rules (AC-MEM-2) apply only to memories with ≥ 1 long-term strategy. Short-term-only memories are exempt and reported as a "ShortTermOnly" observation, never a finding.

Data collection:
- `bedrock-agentcore:ListMemories` → `GetMemory` (status, createdAt, strategies)
- `bedrock-agentcore:ListMemoryRecords` — **data-plane, count only** (long-term-strategy memories; read the record count, never the `content` field)
- `cloudwatch:GetMetricData` (namespace `AWS/Bedrock-AgentCore`, 30-day window):
  - `Ingestion` operation: `Invocations`, `Errors` (long-term memories)
  - `CreateEvent` operation: `Invocations` (ALL memories — short-term memories receive events too)

Thresholds: `ERROR_RATE_THRESHOLD = 0.20`, `NEAR_EMPTY_THRESHOLD = 10 records`, `MIN_AGE_DAYS = 7`.

### AC-MEM-1: Extraction / Consolidation Errors
- **Applies to**: memories with ≥ 1 long-term strategy
- **High if**: ingestion `Errors > 0` over the lookback window
- **Confidence**: High if metrics complete, else Medium
- **Remediation**: Check ingestion application logs (if log delivery enabled). Common causes: incompatible event format, extraction-model permission errors, strategy misconfiguration.

### AC-MEM-2: Empty or Near-Empty Long-Term Memory
- **Applies to**: memories with ≥ 1 long-term strategy
- **Medium if**: record count < 10
- **Escalates to High if**: record count == 0 AND age > 7 days
- **Short-term-only**: emit `ShortTermOnly` observation instead (zero long-term records is expected)
- **Remediation**: Verify events are flowing and extraction is producing records. Check ingestion metrics and logs.

### AC-MEM-3: High Extraction Error Rate
- **Applies to**: long-term memories with ingestion `Invocations > 0`
- **Calculation**: `error_rate = Errors / Invocations`
- **High if**: `error_rate > 0.20`
- **Remediation**: A significant portion of knowledge is being lost. Review extraction logs and the event shapes causing failures.

### AC-MEM-4: Provisioned but Never Populated
- **Applies to**: ALL memories (evaluates event ingestion, not records)
- **Medium if**: `CreateEvent` invocations == 0 AND age > 7 days
- **Skipped if**: the `CreateEvent` metric was unreadable — event count is set to `None` (not 0), so an unreadable signal never reports "never populated"
- **Remediation**: Confirm the memory is still intended for use. If abandoned, decommission it to reduce operational surface.

---

## Resource Utilization & Operational Hygiene — Operational Excellence (3 checks)

**Framing:** AgentCore runtime billing is consumption-based (idle time is free). Findings are framed as operational hygiene and security surface, NOT wasted spend. Exception: memories holding stored long-term records DO accrue standing storage cost — noted per-resource via `hasStandingCost`.

Data collection:
- Inventory: `ListAgentRuntimes`, `ListMemories`, `ListGateways`, `ListBrowsers`, `ListCodeInterpreters`, `ListWorkloadIdentities`
- Activity: `cloudwatch:GetMetricData` (`Invocations`, namespace `AWS/Bedrock-AgentCore`, 30-day window) keyed by per-type dimension:
  - Runtime → `AgentRuntimeId`, Memory → `MemoryId`, Gateway → `GatewayId`
  - Browser / CodeInterpreter / WorkloadIdentity → no queryable per-resource metric (activity signal incomplete)

For the runtime idle signal, prefer the real-time `ActiveSessionCount` gauge where available; fall back to the cumulative `SessionCount` / `Invocations` counters over the 30-day window otherwise.

Thresholds: `UTILIZATION_THRESHOLD = 0.60`, `SPRAWL_REGION_ACTIVITY_THRESHOLD = 0.05`, `MIN_AGE_DAYS = 7`, `RECENTLY_CREATED_DAYS = 7`.

Classification (per resource):
- **Active** — has activity, complete signal
- **Idle** — zero activity, complete signal
- **Active (partial)** — signal incomplete (no queryable metric, or CloudWatch call failed) — NEVER classified Idle
- **RecentlyCreated** — age < 7 days; excluded from idle flagging AND from the utilization ratio

### AC-UTIL-1: Idle Provisioned Resources
- **Medium if**: zero activity over the 30-day window AND age ≥ 7 days AND signal complete (status == Idle)
- **Escalate messaging** (not severity) where standing cost exists (e.g. idle memory holding long-term records)
- **Remediation**: Review whether the resource is still needed. Idle resources carry IAM roles and configuration that expand operational and security surface.

### AC-UTIL-2: Consolidation Opportunities
- **Duplicates**: within a region, group by (type, region, config hash); flag clusters of 2+ near-identical resources
- **Regional residue**: when resources span 3+ regions, flag regions with < 5% of total activity
- **Informational** by default; **Medium** when broad (3+ duplicate clusters, or multiple issues)
- **Remediation**: Consolidating duplicates and retiring low-activity regions simplifies architecture and reduces operational overhead.

### AC-UTIL-3: Low Overall Utilization
- **Calculation**: `active / assessable`, where assessable excludes RecentlyCreated resources
- **Informational if**: ratio < 0.60
- **Reported summary**: total, assessable, recentlyCreated, active, idle, ratio
- **Remediation**: Review the estate for resources that can be retired. An accurate inventory makes incidents and audits easier.

---

## Runtime Observability — cross-pillar signals

Data collection (namespace `AWS/Bedrock-AgentCore`):
1. `cloudwatch:ListMetrics` to discover resources — extract unique `Resource` (ARN) + `Name` dimensions
2. `cloudwatch:GetMetricData` per resource:

| Metric | Dimensions | Period | Statistic |
|--------|-----------|--------|-----------|
| CPUUsed-vCPUHours | Resource, Service=`AgentCore.Runtime`, Name | 3600s | Sum |
| MemoryUsed-GBHours | Resource, Service=`AgentCore.Runtime`, Name | 3600s | Sum |
| SessionCount | Resource, Operation=`InvokeAgentRuntime`, Name | 300s | Sum |
| Invocations | Resource, Operation=`InvokeAgentRuntime`, Name | 300s | Sum |
| Throttles | Resource, Operation=`InvokeAgentRuntime`, Name | 300s | Sum |

`SessionCount` is a cumulative counter of new sessions per period. `ActiveSessionCount` (added June 2026) is a real-time gauge of currently-running sessions, filterable by the `Service` dimension — prefer it where a live "is anything running" read is needed.

Derived:
- **Throttle rate** = `Throttles / Invocations × 100` (`0.00%` when no invocations)
- **Health status** = "Throttling Detected" if `Throttles > 0`, else "Healthy"
- Report only resources with activity (any of vCPU-hours, GB-hours, invocations, session count > 0)

This pillar requires only `cloudwatch:*` — it works in observability-only mode with no `bedrock-agentcore:` permissions. When an account isn't using AgentCore, the namespace is empty → "no activity detected" (not a failure).
