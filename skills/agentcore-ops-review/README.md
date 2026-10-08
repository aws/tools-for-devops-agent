# Bedrock AgentCore Operational Review — AWS DevOps Agent Skill

A comprehensive Amazon Bedrock AgentCore operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with the [Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). Generates a shareable report artifact for the review.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover AgentCore resources in the configured account/regions — agent runtimes, endpoints, versions, memories (and their strategies), gateways and gateway targets, browsers, code interpreters, and workload identities.
2. Collect CloudWatch metrics from the `AWS/Bedrock-AgentCore` namespace for session counts, invocations, throttles, vCPU-hours, GB-hours, and memory ingestion errors.
3. Resolve VPC subnet placement to availability zones (via `ec2:DescribeSubnets`) to assess runtime AZ fault tolerance.
4. Analyze against four check areas mapped to the Well-Architected Framework — **Runtime Resilience** (Reliability), **Gateway Health** (Reliability), **Memory & Knowledge Effectiveness** (Performance Efficiency), and **Resource Utilization & Operational Hygiene** (Operational Excellence) — plus cross-pillar runtime observability signals.
5. Generate a shareable report artifact, titled `Bedrock AgentCore Operational Review — <account-id> — <YYYY-MM-DD>`.

All data is gathered through native AWS APIs (`bedrock-agentcore`, `cloudwatch`, `ec2`, `ce`, `health`). The skill never invokes an agent (`InvokeAgentRuntime`) and reads no prompts or responses. It makes **one** data-plane call — `bedrock-agentcore:ListMemoryRecords` — solely to count long-term memory records; that response can include potentially PII-bearing `content`, which the skill never reads, stores, or reproduces (see [Memory record data handling](#memory-record-data-handling)). It does not depend on any internal tooling.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("review my AgentCore runtimes", "AgentCore health check").
- **Evaluation** — proactive operational improvement recommendations.

Select **Generic** instead if you want the skill available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions — two modes

The standard `AIDevOpsAgentAccessPolicy` covers `bedrock:*` read actions but does **NOT** include the `bedrock-agentcore:*` namespace. (Note: `bedrock-agentcore-control` is the SDK client name, not an IAM prefix — every control-plane action such as `ListAgentRuntimes`, `GetMemory`, and `ListGateways` authorizes under the single service prefix `bedrock-agentcore:`.) The skill supports two modes:

**Runtime-observability-only mode** — relies exclusively on CloudWatch metrics against namespace `AWS/Bedrock-AgentCore`. Requires no `bedrock-agentcore:` additions. See `references/iam-policy-observability-only.json`:

- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`
- `health:DescribeEvents`, `health:DescribeEventDetails`
- `sts:GetCallerIdentity`
- `ce:GetCostAndUsage`, `ce:GetDimensionValues` (region discovery)

**Full control-plane mode** — adds the read-only `bedrock-agentcore:` set plus `ec2:DescribeSubnets` to enable the runtime/gateway/memory/utilization checks. See `references/iam-policy-linked-account.json` (and `references/iam-policy-management-account.json` for the payer/management account):

- `bedrock-agentcore:ListAgentRuntimes`, `GetAgentRuntime`, `ListAgentRuntimeEndpoints`, `ListAgentRuntimeVersions`
- `bedrock-agentcore:ListMemories`, `GetMemory` (control-plane), `ListMemoryRecords` (data-plane; record count only — see [Memory record data handling](#memory-record-data-handling))
- `bedrock-agentcore:ListGateways`, `GetGateway`, `ListGatewayTargets`, `GetGatewayTarget`
- `bedrock-agentcore:ListBrowsers`, `ListCodeInterpreters`, `ListWorkloadIdentities`
- `ec2:DescribeSubnets` (AC-RUN-2 multi-AZ check)

The skill operates in **read-only** mode: it never calls `Create*`, `Update*`, `Delete*`, or `InvokeAgentRuntime`. Its only data-plane call is `bedrock-agentcore:ListMemoryRecords`, used for a record count and nothing else (see [Memory record data handling](#memory-record-data-handling)). If a required permission is missing, the affected check degrades to a **visibility limit** ("signal unavailable — check skipped") rather than failing the review or producing a false finding.

### 3. AgentCore workloads with activity (recommended)

Most checks rely on `AWS/Bedrock-AgentCore` CloudWatch metrics and control-plane inventory, which only exist for accounts actively using AgentCore. Reviewing an account with no AgentCore activity produces "No AgentCore usage detected" rather than false findings.

### 4. Relationship to `agentcore-observability-setup`

This skill assesses operational posture from *existing* telemetry; it does not configure or validate observability wiring. Where telemetry is absent, it reports a visibility limit and defers the configuration gap to the `agentcore-observability-setup` skill, which owns the observability-wiring finding.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `skills/` directory in this repo, build the archive from **inside** the
skill directory so `SKILL.md` sits at the archive root (nesting it under a
subdirectory causes `Failed to get skill resource` errors at load time):

```bash
cd skills/agentcore-ops-review
zip -qrD ../agentcore-ops-review.zip . \
  -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' 'evals/*'
```

The resulting `agentcore-ops-review.zip` contains `SKILL.md` at the root plus the
`references/` files:

```
SKILL.md               # frontmatter + skill instructions (required, at root)
references/
├── pillar-checks.md
├── report-template.md
├── iam-policy.json
├── iam-policy-observability-only.json
├── iam-policy-linked-account.json
└── iam-policy-management-account.json
```

`README.md`, `CHANGELOG.md`, `.skilleval.yaml`, and `evals/` are excluded from the
upload — they are repo/offline-evaluation artifacts, not part of the runtime skill.

Constraints (enforced at upload time):

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `agentcore-ops-review.zip` (or browse to it).
4. Select agent types: **On-demand** and **Evaluation** (or leave **Generic** to make it available to all agent types).
5. Review the validation results.
6. Click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

- *"Run an AgentCore operational review for all regions."*
- *"Review my AgentCore runtimes in `us-east-1` for resilience."*
- *"Audit my agent memory pipelines for extraction errors."*
- *"Check my AgentCore gateway health and target redundancy."*
- *"ORR for our AgentCore workloads."*

The agent will:

- Collect all data automatically (no prompts for confirmation).
- Use only AWS read APIs — no agent invocation, no prompts/responses read; the sole data-plane call (`ListMemoryRecords`) is used for a record count only, never for `content`.
- Generate a report artifact titled `Bedrock AgentCore Operational Review — <account-id> — <YYYY-MM-DD>`.

## Skill Contents

```
agentcore-ops-review/
├── SKILL.md                            # main skill instructions (with frontmatter)
├── README.md                           # this file
├── CHANGELOG.md                        # version history
├── references/
│   ├── pillar-checks.md                # detailed check definitions, rules, thresholds
│   ├── report-template.md              # artifact report structure
│   ├── iam-policy.json                 # policy index / notes
│   ├── iam-policy-observability-only.json
│   ├── iam-policy-linked-account.json
│   └── iam-policy-management-account.json
└── evals/                              # evaluation data (not included in upload zip)
```

## Check Areas Covered

| Pillar (WA) | Check Area | Rule IDs | Reference |
|-------------|-----------|----------|-----------|
| Reliability | Runtime Resilience & Production Readiness | AC-RUN-1..4 | [AgentCore runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html) |
| Reliability | Gateway Health & Target Redundancy | GW-01 | [AgentCore gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html) |
| Performance Efficiency | Memory & Knowledge Effectiveness | AC-MEM-1..4 | [AgentCore memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) |
| Operational Excellence | Resource Utilization & Operational Hygiene | AC-UTIL-1..3 | [AgentCore observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) |
| Cross-pillar | Runtime Observability (session count, invocations, throttles, vCPU/GB-hours) | — | [AgentCore observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) |

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |

## Memory record data handling

The skill's only data-plane call is `bedrock-agentcore:ListMemoryRecords`, used to count records for long-term memories (check AC-MEM-2). Each `MemoryRecordSummary` in that response includes a required `content` field — the extracted facts, preferences, and summaries a long-term memory has stored, which can contain end-user PII.

This skill uses **only the record count**. It does not read, parse, log, store, transform, transmit, or reproduce the `content` field anywhere — not in findings, artifacts, recommendations, or logs.

If you prefer the skill make **zero** data-plane calls, omit `bedrock-agentcore:ListMemoryRecords` from the IAM policy. AC-MEM-2 (empty/near-empty long-term memory) then degrades to a documented visibility limit, while all other memory checks — which rely on CloudWatch ingestion metrics (`Errors`, `Invocations`, `NumberOfMemoryRecords`) — continue to work.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Users should validate it in a non-production environment first. It performs read-only operational analysis and makes no changes to your AWS resources, but you are responsible for reviewing the IAM permissions you grant and the findings it produces before acting on them.
