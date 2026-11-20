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

- **On-demand** (`CHAT`) — "is AgentCore observability configured correctly?", "why can't I see traces
  for my agent?", "set up OTEL for my agent".

Select **Generic** when you upload the zip to make it available to all agent types.

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

Full policy JSON: [`references/iam-tiers.md`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/agentcore-observability-setup/references/iam-tiers.md). All permissions are read-only.

### 3. Capability providers connected to the Agent Space

CloudWatch Logs + Metrics (Tier 1, required baseline); AWS X-Ray and AgentCore control plane
(Tier 2); Lambda / ECS / EKS (Tier 3). Source-repository file read is **not** required — code-level
checks are prescriptive.

## Uploading to AWS DevOps Agent

Complete the [prerequisites](#prerequisites) first (the IAM tiers and the capability providers connected to the Agent Space), or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs an on-demand observability readiness check that you ask for in chat, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add setup and remediation guidance those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `agentcore-observability-setup`, or filter by AWS service **Amazon Bedrock AgentCore**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust check severities in `references/checks-catalog.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/agentcore-observability-setup/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f agentcore-observability-setup.zip
   zip -r agentcore-observability-setup.zip agentcore-observability-setup/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l agentcore-observability-setup.zip | tail -1   # expect 6 files
   ```

2. Check that the zip has this structure:

   ```text
   agentcore-observability-setup.zip
   └── agentcore-observability-setup/
       ├── SKILL.md                          # required: frontmatter with name and description
       └── references/
           ├── checks-catalog.md
           ├── iam-tiers.md
           ├── remediation-runtime.md
           ├── remediation-memory-gateway.md
           └── remediation-non-runtime.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `agentcore-observability-setup.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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
