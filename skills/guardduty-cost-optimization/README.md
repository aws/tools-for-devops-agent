# GuardDuty Cost Optimization — AWS DevOps Agent Skill

A read-only Amazon GuardDuty cost optimization skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). It identifies, quantifies, and prioritizes GuardDuty cost-reduction opportunities aligned with [Monitoring GuardDuty usage and estimating costs](https://docs.aws.amazon.com/guardduty/latest/ug/monitoring_costs.html) and [GuardDuty pricing](https://aws.amazon.com/guardduty/pricing/), and generates a shareable report artifact.

## Purpose

GuardDuty is pay-as-you-go per protection plan, priced on the volume of data each plan analyzes — so spend is driven by which plans are enabled and how much they process, not by any per-detector fee. This skill teaches the agent the GuardDuty billing model (including the Runtime-Monitoring/VPC-Flow-Log offset and the fact that customer log configuration does *not* reduce GuardDuty cost), reads the per-data-source `AWS/GuardDuty` CloudWatch usage metrics to attribute spend by plan, weighs each plan's cost against its finding activity, and recommends compliance-aware reductions — always as a cost-vs-security tradeoff.

## Key Capabilities

- Inventories detectors, enabled protection plans, Runtime Monitoring coverage, and organization member coverage via read-only APIs
- Attributes spend per protection plan using the `AWS/GuardDuty` (and `AWS/GuardDuty/MalwareProtection`) CloudWatch usage metrics, reconciled against Cost Explorer when available
- Flags high-cost/low-signal plans by weighing per-plan cost against `GetFindingsStatistics` finding activity
- Sizes the Runtime Monitoring ↔ VPC Flow Log charge offset (enabling the runtime agent stops VPC Flow Log processing charges on monitored instances)
- Reviews S3 Protection and Malware Protection for S3 scan volume as cost-vs-risk tradeoffs
- Projects post-free-trial monthly cost from observed trial usage — before the bill lands
- Flags duplicate/inconsistent multi-account or unused-Region coverage
- Produces a severity-ranked report artifact with a per-plan spend table, free-trial projection, priority matrix, and next steps

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account configured as a cloud source

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

**No additional IAM permissions are required.** Every call this skill makes is read-only and covered by the AWS managed [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html):

- `guardduty:ListDetectors`, `guardduty:GetDetector`, `guardduty:ListMembers`, `guardduty:GetMemberDetectors`
- `guardduty:GetMasterAccount`, `guardduty:ListOrganizationAdminAccounts`, `guardduty:GetFindingsStatistics`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`
- `organizations:DescribeOrganization`, `organizations:ListAccounts` (organization scope)
- `ce:GetCostAndUsage` (dollar signal for sizing opportunities), granted via `ce:Get*`

There is no CloudFormation template to deploy for this skill.

The skill operates entirely in **read-only** mode — it never calls `CreateDetector`, `UpdateDetector`, `DeleteDetector`, or any protection-plan mutation.

## Limitations

- GuardDuty usage metrics are published hourly and can lag up to ~24 hours; the skill uses a multi-day window for sizing.
- Without Cost Explorer access, findings are still reported but dollar impact is labeled "not quantified".
- The skill reads usage metrics and finding *statistics* only — it does not read finding detail content.
- GuardDuty is a security control: the skill frames every reduction as a cost-vs-risk tradeoff and never recommends disabling coverage on cost grounds alone. The security decision remains the user's.
- Customer-side log configuration (VPC Flow Logs, CloudTrail, S3 data events) does not affect GuardDuty cost, so the skill does not recommend changing it to save GuardDuty spend.

## Agent Types

- **On-demand (Chat tasks)** — "why is my GuardDuty bill so high", "which protection plan costs the most".
- **Evaluation** — proactive cost-optimization recommendations, including pre-trial-end projections.

Select **Generic** (All agents) if you want the skill available to all agent types — required if you use it with the `unified-security-cost-optimizer` custom agent.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

Build the zip from **inside** the skill directory so `SKILL.md` sits at the archive root, excluding development-only files:

```bash
cd skills/guardduty-cost-optimization
zip -r ../guardduty-cost-optimization.zip . \
  -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' '.skilleval.yml' 'evals/*'
```

Then in the Operator Web App: **Skills → Add skill → Upload skill**, drag in the zip, select agent types (**On-demand** and **Evaluation**, or **Generic** for the custom agent), review validation, and **Upload**.

## How to Use This Skill

In DevOps Agent Chat:

- *"Review my GuardDuty costs for account 123456789012 across all regions."*
- *"Which GuardDuty protection plan is costing me the most?"*
- *"Is GuardDuty S3 Protection worth it for my workload?"*
- *"Project my GuardDuty spend after the free trial ends."*
- *"Would enabling Runtime Monitoring reduce my VPC Flow Log charges?"*

The agent will inventory protection plans, attribute per-plan spend from usage metrics, weigh cost against finding activity, and generate `guardduty-cost-optimization-<account-id>-<YYYY-MM-DD>.md`.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate in a non-production environment first. Recommendations are derived from observed usage and finding statistics — GuardDuty is a security control, so review the security impact of any coverage reduction before applying, and never disable a protection plan you have not assessed for risk.
