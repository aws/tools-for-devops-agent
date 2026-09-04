# Bedrock Operational Review — AWS DevOps Agent Skill

A comprehensive Amazon Bedrock operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with the [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). Generates a shareable report artifact for the review.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover Bedrock resources in the configured account/regions — foundation models, guardrails, inference profiles, prompt routers, provisioned throughput, custom models, model customization jobs, agents, knowledge bases, data sources, and prompts.
2. Collect CloudWatch metrics from the `AWS/Bedrock` namespace (also `CWAgent` namespaces) for invocations, latency, throttling, errors, token usage, guardrail interventions, and prompt-cache activity.
3. Pull service quota values from Service Quotas and compare against observed usage.
4. Analyze against six pillars — **Security, Performance, Service Quotas, Cost Optimization, Resilience** — plus check-specific guidance.
5. Generate a shareable report artifact, named `bedrock-review-<account-id>-<region>-<YYYY-MM-DD>.md`.

All data is gathered through native AWS APIs (`bedrock`, `bedrockagent`, `cloudwatch`, `servicequotas`, `ec2`). The skill performs **no data-plane model invocations** and reads no prompt or response content. It does not depend on Kubernetes, EKS, or any internal tooling.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("review my Bedrock account", "Bedrock health check").
- **Evaluation** — proactive operational improvement recommendations.

Select **Generic** instead if you want the skill available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

The Agent Space's IAM role must have read access to Bedrock, Bedrock Agent, CloudWatch, Service Quotas, and EC2 APIs. Verify these are present in your account before running the review:

- `bedrock:ListFoundationModels`, `bedrock:ListGuardrails`, `bedrock:GetGuardrail`
- `bedrock:GetModelInvocationLoggingConfiguration`
- `bedrock:ListInferenceProfiles`, `bedrock:GetInferenceProfile`
- `bedrock:ListPromptRouters`, `bedrock:GetPromptRouter`
- `bedrock:ListProvisionedModelThroughputs`, `bedrock:GetProvisionedModelThroughput`
- `bedrock:ListCustomModels`, `bedrock:GetCustomModel`
- `bedrock:ListModelCustomizationJobs`, `bedrock:GetModelCustomizationJob`
- `bedrock:ListAgents`, `bedrock:GetAgent`, `bedrock:ListAgentAliases` (Bedrock Agent control plane)
- `bedrock:ListKnowledgeBases`, `bedrock:GetKnowledgeBase`, `bedrock:ListDataSources`, `bedrock:GetDataSource`
- `bedrock:ListPrompts`, `bedrock:GetPrompt`
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`
- `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas`
- `ec2:DescribeInstances`

The skill operates entirely in **read-only** mode: it never calls `Create*`, `Update*`, `Delete*`, or any `InvokeModel*` (data-plane) APIs.

### 3. Model invocation activity (recommended)

Most CloudWatch-based checks (latency, throttling, prompt caching, guardrail signals, cross-region inference, model versions) rely on `AWS/Bedrock` metrics, which only exist for models that have been invoked in the analysis window. Reviewing an account with no recent Bedrock traffic still produces a configuration report, but metric-driven findings will be empty.

### 4. (Conditional) CloudWatch Agent for EC2 GPU utilization

The EC2 GPU utilization check (self-managed P4/P5/P5en/P6 instances) requires the **CloudWatch Agent** installed with the **NVIDIA DCGM plugin** enabled, publishing `nvidia_smi_utilization_gpu` and `nvidia_smi_memory_util` to the `CWAgent` namespace. Without it, GPU signals cannot be evaluated. This check is optional and only applies to accounts running self-managed GPU training/inference.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

### 1. Package the skill

From the `skills/` directory in this repo:

```bash
cd skills
zip -r bedrock-operation-review.zip bedrock-operation-review/ -x 'bedrock-operation-review/evals/*'
```

The resulting `bedrock-operation-review.zip` contains:

```
bedrock-operation-review/
├── SKILL.md          # frontmatter + skill instructions (required)
├── README.md
└── references/
    ├── best-practices-checklist.md
    └── metrics-thresholds.md
```

`evals/` is excluded from the upload to keep the zip small (it's only used for offline evaluation).

Constraints (enforced at upload time):

- Total zip size ≤ **6 MB**.
- `SKILL.md` is required and must include `name` and `description` frontmatter.
- A `scripts/` directory is **not** allowed — uploads containing scripts are rejected.

### 2. Upload via the Operator Web App

1. Navigate to the **Skills** page in your Agent Space Operator Web App.
2. Click **Add skill** → **Upload skill**.
3. Drag and drop `bedrock-operation-review.zip` (or browse to it).
4. Select agent types: **On-demand** and **Evaluation** (or leave **Generic** to make it available to all agent types).
5. Review the validation results.
6. Click **Upload**.

## Usage

In the DevOps Agent Chat, use natural language:

- *"Run a Bedrock operational review for all regions."*
- *"Review my Bedrock account `123456789012` in `us-east-1` for best practices."*
- *"Audit Bedrock security and cost optimization."*
- *"Check my Bedrock service quota utilization and throttling."*
- *"ORR for our Bedrock workloads."*

The agent will:

- Collect all data automatically (no prompts for confirmation).
- Use only AWS APIs — no model invocations, no prompt/response content read.
- Generate a report artifact named `bedrock-review-<account-id>-<region>-<YYYY-MM-DD>.md`.

## Skill Contents

```
bedrock-operation-review/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── references/
│   ├── best-practices-checklist.md    # checklist mapped to Bedrock best practices
│   └── metrics-thresholds.md          # CloudWatch metric thresholds & severity rules
└── evals/                             # evaluation data (not included in upload zip)
```

## Best-Practices Pillars Covered

| # | Pillar | Checks | Reference |
|---|--------|--------|-----------|
| 1 | Security | Guardrails, Guardrail Signals, Model Invocation Logging, Knowledge Base config & encryption, VPC config for customization jobs, IAM fine-grained access, KB logging, Prompt injection, Model access | [Bedrock security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html) |
| 2 | Performance | Latency & Throttling, Agent Performance, Invoked Model Versions, Data Automation, Service Tier | [Monitoring Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring.html) |
| 3 | Service Quotas | Model Quotas, Guardrail Service Quotas | [Bedrock quotas](https://docs.aws.amazon.com/bedrock/latest/userguide/quotas.html) |
| 4 | Cost Optimization | Application Inference Profiles, Custom Model Distillation, Prompt Caching, Prompt Management, Intelligent Prompt Routing, Provisioned Throughput, Batch Inference, EC2 GPU Utilization | [Bedrock pricing](https://aws.amazon.com/bedrock/pricing/) |
| 5 | Resilience | Cross-Region Inference (CRIS) | [Cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) |

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to availability, security, or data integrity | 24–48 hours |
| HIGH | Significant gap that could lead to incidents | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |
