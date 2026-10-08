# CloudTrail Cost Optimization — AWS DevOps Agent Skill

A read-only AWS CloudTrail cost optimization skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). It identifies, quantifies, and prioritizes CloudTrail cost-reduction opportunities aligned with [Managing CloudTrail trail costs](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-trail-manage-costs.html) and [CloudTrail pricing](https://aws.amazon.com/cloudtrail/pricing/), and generates a shareable report artifact.

## Purpose

CloudTrail spend grows quietly: duplicate trails re-deliver the same management events, data events are billed on every copy with no free tier, high-volume KMS and RDS Data API events inflate volume, and CloudTrail Lake ingestion/retention accumulates. This skill teaches the agent how CloudTrail billing works and how to trace spend back to specific trails, event selectors, and event data stores — then recommends concrete, compliance-aware reductions.

## Key Capabilities

- Inventories all trails (including multi-Region shadow and Organizations trails) and CloudTrail Lake event data stores via read-only APIs
- Detects duplicate management-event trails within a Region (multi-Region + single-Region overlap, Org trail + member trail) — the most common and highest-impact CloudTrail cost driver
- Flags paid trails logging unnecessary Read management events
- Identifies high-volume noise events (AWS KMS, RDS Data API) that can be excluded via event selectors
- Flags overly broad data event logging and duplicate data event deliveries (every data event copy is billed)
- Reviews CloudTrail Lake pricing option, retention, and duplicate ingestion
- Attributes spend using Cost Explorer usage types when available, and sizes each opportunity with an estimated monthly saving
- Produces a severity-ranked report artifact with a priority matrix and next steps

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account configured as a cloud source

### 2. IAM permissions for the DevOps Agent's primary cloud-source role

**No additional IAM permissions are required.** Every call this skill makes is read-only and covered by the AWS managed [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html):

- `cloudtrail:DescribeTrails`, `cloudtrail:GetTrail`, `cloudtrail:GetTrailStatus`, `cloudtrail:ListTrails`, `cloudtrail:GetEventSelectors`
- `cloudtrail:ListEventDataStores`, `cloudtrail:GetEventDataStore`
- `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`, `cloudwatch:ListMetrics`
- `s3:ListBucket`, `s3:GetLifecycleConfiguration` (destination bucket hygiene)
- `organizations:DescribeOrganization`, `organizations:ListAccounts` (organization scope)
- `ce:GetCostAndUsage` (dollar signal for sizing opportunities), granted via `ce:Get*`

There is no CloudFormation template to deploy for this skill.

The skill operates entirely in **read-only** mode — it never calls `CreateTrail`, `UpdateTrail`, `DeleteTrail`, `PutEventSelectors`, `StopLogging`, or any Lake mutation.

## Limitations

- CloudTrail does not expose reliable per-trail event counts; the skill uses Cost Explorer usage types and S3 bucket size as volume proxies and labels estimates as approximate.
- Without Cost Explorer access, findings are still reported but dollar impact is labeled "not quantified".
- The skill reasons about configuration and volume — it does not read the content of logged events.
- Compliance requirements (which events must be retained, and for how long) are the user's to confirm; the skill surfaces the tradeoff but does not decide it.

## Agent Types

- **On-demand (Chat tasks)** — "why is my CloudTrail bill so high", "find duplicate trails".
- **Evaluation** — proactive cost-optimization recommendations.

Select **Generic** (All agents) if you want the skill available to all agent types — required if you use it with the `unified-security-cost-optimizer` custom agent.

## Uploading to AWS DevOps Agent

> Reference: [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill)

Build the zip from **inside** the skill directory so `SKILL.md` sits at the archive root, excluding development-only files:

```bash
cd skills/cloudtrail-cost-optimization
zip -r ../cloudtrail-cost-optimization.zip . \
  -x 'README.md' 'CHANGELOG.md' '.skilleval.yaml' '.skilleval.yml' 'evals/*'
```

Then in the Operator Web App: **Skills → Add skill → Upload skill**, drag in the zip, select agent types (**On-demand** and **Evaluation**, or **Generic** for the custom agent), review validation, and **Upload**.

## How to Use This Skill

In DevOps Agent Chat:

- *"Review my CloudTrail costs for account 123456789012 across all regions."*
- *"Why did my CloudTrail bill go up this month?"*
- *"Find duplicate CloudTrail trails in my organization."*
- *"Are my CloudTrail data events costing too much?"*
- *"Optimize my CloudTrail Lake retention and ingestion."*

The agent will inventory trails and event data stores, size opportunities with any available cost signal, and generate `cloudtrail-cost-optimization-<account-id>-<YYYY-MM-DD>.md`.

## Non-production disclaimer

> ⚠️ This skill is sample code, not intended for production use without additional review and testing. Validate in a non-production environment first. Recommendations are derived from observed configuration and usage — review the compliance impact and narrow them before applying, and never apply a CloudTrail change you have not read.
