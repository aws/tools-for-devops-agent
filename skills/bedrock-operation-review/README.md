# Bedrock Operational Review — AWS DevOps Agent Skill

A comprehensive Amazon Bedrock operational review skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments aligned with the [Amazon Bedrock User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html) and the [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html). Generates a shareable report artifact for the review.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover Bedrock resources in the configured account/regions — foundation models, guardrails, inference profiles, prompt routers, provisioned throughput, custom models, model customization jobs, agents, knowledge bases, data sources, and prompts.
2. Collect CloudWatch metrics from the `AWS/Bedrock` namespace (also `CWAgent` namespaces) for invocations, latency, throttling, errors, token usage, guardrail interventions, and prompt-cache activity.
3. Pull service quota values from Service Quotas and compare against observed usage.
4. Analyze against five pillars — **Security, Performance, Service Quotas, Cost Optimization, Resilience** — plus check-specific guidance.
5. Generate a shareable report artifact, named `bedrock-review-<account-id>-<region>-<YYYY-MM-DD>.md`.

All data is gathered through native AWS APIs (`bedrock`, `bedrockagent`, `cloudwatch`, `servicequotas`, `ec2`). The skill performs **no data-plane model invocations** and reads no prompt or response content. It does not depend on Kubernetes, EKS, or any internal tooling.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("review my Bedrock account", "Bedrock health check").

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
- `bedrock:ListPrompts` (metadata only; the skill does not call `GetPrompt`, so prompt template content is never read)
- `cloudwatch:ListMetrics`, `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`
- `servicequotas:GetServiceQuota`, `servicequotas:ListServiceQuotas`
- `ec2:DescribeInstances`

The skill operates entirely in **read-only** mode: it never calls `Create*`, `Update*`, `Delete*`, or any `InvokeModel*` (data-plane) APIs.

### 3. Model invocation activity (recommended)

Most CloudWatch-based checks (latency, throttling, prompt caching, guardrail signals, cross-region inference, model versions) rely on `AWS/Bedrock` metrics, which only exist for models that have been invoked in the analysis window. Reviewing an account with no recent Bedrock traffic still produces a configuration report, but metric-driven findings will be empty.

### 4. (Conditional) CloudWatch Agent for EC2 GPU utilization

The EC2 GPU utilization check (self-managed P4/P5/P5en/P6 instances) requires the **CloudWatch Agent** installed with the **NVIDIA DCGM plugin** enabled, publishing `nvidia_smi_utilization_gpu` and `nvidia_smi_memory_util` to the `CWAgent` namespace. Without it, GPU signals cannot be evaluated. This check is optional and only applies to accounts running self-managed GPU training/inference.

## Uploading to AWS DevOps Agent

Add the IAM permissions in [Prerequisites](#prerequisites) to the Agent Space's role first, or add the skill as **Inactive** until they're in place. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand operational reviews and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `bedrock-operation-review`, or filter by AWS service **Amazon Bedrock**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust thresholds in `references/metrics-thresholds.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/bedrock-operation-review/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f bedrock-operation-review.zip
   zip -r bedrock-operation-review.zip bedrock-operation-review/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l bedrock-operation-review.zip | tail -1   # expect 3 files
   ```

2. Check that the zip has this structure:

   ```text
   bedrock-operation-review.zip
   └── bedrock-operation-review/
       ├── SKILL.md                      # required: frontmatter with name and description
       └── references/
           ├── best-practices-checklist.md
           └── metrics-thresholds.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `bedrock-operation-review.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review
> and testing. Validate in a non-production environment first. Proposed IAM policies are
> suggestions derived from observed evidence — review and narrow them before applying, and
> never apply an IAM change you have not read.
