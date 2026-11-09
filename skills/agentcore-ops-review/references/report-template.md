# Artifact Report Template

The artifact produced by this agent should be titled:
**"Bedrock AgentCore Operational Review — [Account ID] — [YYYY-MM-DD]"**

## Required Sections (in order)

All sections MUST appear in the artifact. If no data is available for a section, include the section header with text: "No data available — check was not executed or returned no results."

### 1. Executive Summary

**Table format:**

| Pillar | Status | Key Finding | Severity |
|--------|--------|-------------|----------|
| Runtime Resilience | ✅ / ⚠️ / ❌ | One-line summary | Critical/Warning/Pass |
| Gateway Health | ✅ / ⚠️ / ❌ | One-line summary | Critical/Warning/Pass |
| Memory & Knowledge Effectiveness | ✅ / ⚠️ / ❌ | One-line summary | Critical/Warning/Pass |
| Resource Utilization & Hygiene | ✅ / ⚠️ / ❌ | One-line summary | Critical/Warning/Pass |

Status logic:
- ✅ Pass: All checks in pillar pass
- ⚠️ Warning: At least one Warning/Medium/Low, no Critical/High
- ❌ Critical: At least one Critical or High finding

### 2. Prioritized Findings

**Table format:**

| # | Priority | Rule | Action | Pillar | Impact | Effort |
|---|----------|------|--------|--------|--------|--------|
| 1 | Critical | AC-RUN-1 | [Remediation action] | Runtime Resilience | High | Low |
| 2 | High | AC-MEM-3 | [Remediation action] | Memory Effectiveness | High | Medium |

Sort by severity: Critical → High → Medium → Low → Informational, then by Impact.

### 3. KPI Summary

**Table format:**

| Metric | Value |
|--------|-------|
| Accounts scanned | N |
| Regions active | N |
| Runtimes | N |
| Gateways | N |
| Memories | N |
| Total invocations (30d) | N |
| Throttle rate | N% |
| Idle resources | N |
| Overall utilization | N% |
| Total findings | N (X Critical, Y High, Z Medium) |

### 4. Runtime Inventory & Observability

**Table format:**

| Runtime Name | Runtime ID | Status | Network Mode | Subnet AZs | Endpoints | Latest Version | Max Drift | Session Count (30d) | Invocations (30d) | Throttle Rate | vCPU-Hours | GB-Hours | Health |
|--------------|-----------|--------|--------------|-----------|-----------|----------------|-----------|---------------------|-------------------|---------------|-----------|----------|--------|

### 5. Gateway Health

**Table format:**

| Gateway ID | Status | Protocol | Authorizer | Total Targets | Healthy | Unhealthy | Single Point of Failure | Policy Engine | Stale Sync | Risk Level |
|------------|--------|----------|------------|---------------|---------|-----------|-------------------------|---------------|------------|------------|

### 6. Memory & Knowledge Effectiveness

**Table format:**

| Memory ID | Memory Name | Status | Strategies | Total Records | Days Since Creation | Ingestion Invocations | Ingestion Errors | Error Rate | Findings | Severity |
|-----------|-------------|--------|-----------|---------------|---------------------|-----------------------|------------------|-----------|----------|----------|

Note: "Total Records" = N/A for short-term-only memories.

### 7. Resource Utilization Summary

**Per-type table:**

| Resource Type | Total Provisioned | Active | Idle | Active (partial) | Recently Created | Utilization % | Regions Used |
|---------------|-------------------|--------|------|------------------|------------------|---------------|--------------|

**Per-resource inventory (idle/flagged only):**

| Resource Type | Resource ID | Region | Age (days) | Activity Count | Signal Source | Status | Standing Cost? | Findings |
|---------------|------------|--------|-----------|----------------|---------------|--------|----------------|----------|

### 8. Per-Pillar Detailed Findings

For each pillar, include a sub-section:

#### [Pillar Emoji] [Pillar Name]

| Check ID | Check Name | Status | Current State | Expected State | Remediation |
|----------|------------|--------|---------------|----------------|-------------|

Pillar emojis: Runtime Resilience=🛡️, Gateway Health=🚪, Memory & Knowledge Effectiveness=🧠, Resource Utilization=♻️

### 9. Visibility Limits

**Table format:**

| Scope | Summary | Affected Resources |
|-------|---------|--------------------|

List every check that was skipped or degraded due to missing permissions or incomplete signals (e.g. `bedrock-agentcore` access denied, `ec2:DescribeSubnets` missing, CloudWatch signal incomplete for Browser/CodeInterpreter). This section makes the "not covered" scope explicit and prevents incomplete signals from being read as passes.

### 10. Methodology

**Text block:**

```
Assessment conducted: [Date]
Account(s): [List]
Regions: [List]
Pillars: Runtime Resilience, Gateway Health, Memory & Knowledge Effectiveness, Resource Utilization
Mode: [Full control-plane / Observability-only]
Time windows: 30-day activity + memory ingestion, 14-day health events
Tools: use_aws (bedrock-agentcore, cloudwatch, ec2, ce, health)
Checks executed: [N] / [Total]
Checks skipped: [List any skipped due to access issues — cross-reference Visibility Limits]
```

## Recommendation Format

For each finding with severity Warning/Medium or higher, create a separate recommendation:

**Title**: `[RULE-ID] [Check Name] — [Resource identifier]`

**Summary**:
```
Pillar: [Name]
Check: [Rule ID — Check Name]
Resource: [ARN or identifier]
Current state: [What was found]
Expected state: [What should be]
Impact: [Operational/reliability impact of the gap]
Remediation:
1. [Step 1]
2. [Step 2]
3. [Step 3]
Conversation starter: [TAM-ready, plain-language framing of the finding]
Priority: [Critical/High/Medium/Low]
Effort: [Low/Medium/High]
```

### Example conversation starters (from the check design)

- **AC-RUN-1**: "One of your agent runtimes is in an UPDATE_FAILED state. Are you aware of this? Let's investigate and get it back to healthy."
- **AC-RUN-2**: "Your runtime reaches your VPC through subnets in a single availability zone. An AZ disruption would cut the agent off from your VPC resources. Adding a subnet in a second AZ restores fault tolerance."
- **AC-MEM-1**: "CloudWatch shows extraction errors on this memory — your agent isn't learning from that data. Have you reviewed the source event format or extraction-model permissions?"
- **AC-UTIL-1**: "This runtime shows no activity in 30 days. Since AgentCore only bills active consumption it's not a direct cost, but it still carries IAM roles and config nobody is maintaining. Can we decommission it?"
