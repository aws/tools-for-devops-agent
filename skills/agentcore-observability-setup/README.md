# AgentCore Observability Setup & Validation — AWS DevOps Agent Skill

A readiness-checklist skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html)
that validates and bootstraps observability for Amazon Bedrock AgentCore workloads, aligned with the
[AgentCore observability documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html).

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Users should validate in a non-production environment first.

## What It Does

Given an AgentCore deployment, the skill instructs the agent to report **what is configured vs. what
should be** for observability, and to generate the exact remediation for each gap. It operates on a
single principle: **verify where reachable; prescribe everywhere else.**

- **VERIFY** — confirm via read-only APIs that log groups exist and receive data, spans flow,
  session metrics emit, CloudWatch Transaction Search is enabled, runtime tracing is on,
  Memory/Gateway log & trace deliveries exist, and the X-Ray log-group resource policy is present.
- **PRESCRIBE** — for code-level OTEL instrumentation (which cannot be read directly), validate the
  *effect* (are spans arriving?) and emit the exact steps. The skill does **not** claim to read
  source code.

Covers AgentCore **Runtime** agents (primary), **Memory** and **Gateway** resources, **built-in
tools**, and agents hosted **outside the runtime** (Lambda, ECS, EKS, on-prem, multi-cloud).

It is **read-only**: it validates and generates config/commands. The customer decides whether to
apply them. It never mutates IAM, resources, or configuration.

Output: a shareable report artifact `agentcore-observability-review-<target>-<YYYY-MM-DD>.md`.

## Agent Types

- **On-demand (Chat)** — "is AgentCore observability configured correctly?", "why can't I see traces
  for my agent?", "set up OTEL for my agent".
- **Evaluation** — proactive observability-readiness recommendations.

Select **Generic** to make it available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account configured as a cloud source.

### 2. IAM — three read-only tiers (customer-applied)

The skill degrades gracefully by tier and reports the exact policy to attach to unlock more checks.
Tier 1 is generally covered by the standard DevOps Agent managed access policy
([AWS-managed policies for DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/security-iam-awsmanpol.html)).
Attach the Tier 2/3 permissions as a **scoped inline policy on the DevOps Agent role** in your
account. The shared managed policy is cross-tenant and is not modified per-skill.

| Tier | Unlocks | Key permissions |
|---|---|---|
| **1 — Standard** | telemetry-arrival verification (any host) | `logs:DescribeLogGroups`, `logs:FilterLogEvents`, `logs:GetLogEvents`, `logs:StartQuery`, `cloudwatch:GetMetricData`, `cloudwatch:ListMetrics`, `cloudwatch:DescribeAlarms` |
| **2 — Runtime config** | Transaction Search state, runtime tracing/env, Memory/Gateway delivery, X-Ray resource policy | `bedrock-agentcore:GetAgentRuntime`, `xray:GetTraceSegmentDestination`, `logs:DescribeDeliveries`, `logs:DescribeResourcePolicies` |
| **3 — Non-runtime host** | Lambda / ECS / EKS host config | `lambda:GetFunctionConfiguration`, `ecs:DescribeTaskDefinition`, `eks:DescribeCluster` |

Full policy JSON: [`references/iam-tiers.md`](references/iam-tiers.md). All permissions are read-only.

### 3. Capability providers connected to the Agent Space

CloudWatch Logs + Metrics (Tier 1, required baseline); AWS X-Ray and AgentCore control plane
(Tier 2); Lambda / ECS / EKS (Tier 3). Source-repository file read is **not** required — code-level
checks are prescriptive.

## Usage

In the DevOps Agent Chat, describe the problem in natural language (don't name the skill):

- *"Validate that AgentCore observability is correctly configured for this account."*
- *"Why can't I see any traces for my Bedrock agent?"*
- *"My agent runtime has no spans in CloudWatch — what's wrong?"*
- *"Set up observability for my agent running on Lambda."*
- *"Run an AgentCore observability readiness review."*

The agent will detect the permission tier, determine the host and surfaces (prompting where it can't
auto-detect), run the checks the tier allows, and produce the report artifact plus any policy JSON
needed to unlock more checks.

## Skill Contents

```
agentcore-observability-setup/
├── SKILL.md                                  # main instructions (frontmatter + decision tree)
├── README.md                                 # this file
├── CHANGELOG.md                              # version history
├── references/
│   ├── checks-catalog.md                     # full per-check catalog (API, logic, severity)
│   ├── iam-tiers.md                          # three read-only tiers + scoped inline policy JSON
│   ├── remediation-runtime.md                # Transaction Search, ADOT, tracing, X-Ray policy
│   ├── remediation-memory-gateway.md         # log delivery + tracing (console + SDK)
│   └── remediation-non-runtime.md            # Lambda / ECS / EKS / on-prem OTEL env
└── evals/                                    # evaluation data (not included in upload zip)
    ├── evals.json
    └── eval_queries.json
```

## Severity Definitions

| Severity | Definition |
|---|---|
| CRITICAL | Observability is broken — telemetry cannot flow (e.g. Transaction Search disabled). |
| HIGH | Significant gap — a required piece is missing (log group, delivery, resource policy, host env). |
| MEDIUM | Notable gap — metrics/traces partially configured or best-practice not met. |
| LOW | Minor hardening or optimization. |
| INFO | Observation, no action required. |

## Limitations

- **Code-level instrumentation** (ADOT distro, `opentelemetry-instrument`, framework tracing) is
  prescriptive — validated by effect (spans arriving), not by reading source.
- **EKS pod-level env** is governed by Kubernetes RBAC and is not verifiable via IAM; the skill
  verifies telemetry arrival and prescribes the pod/ConfigMap configuration.
- **On-prem / multi-cloud** agents are outside the DevOps Agent's reach — prescriptive only.
- **Read-only** — the skill validates and generates config/commands; the customer applies changes.
