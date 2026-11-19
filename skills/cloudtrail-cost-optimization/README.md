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

- **On-demand** — "why is my CloudTrail bill so high", "find duplicate trails".

Select **Generic** if you want the skill available to all agent types — required if you use it with the `unified-security-cost-optimizer` custom agent.

## Uploading to AWS DevOps Agent

Configure the target account as a cloud source (see [Prerequisites](#prerequisites)) first, or add the skill as **Inactive** until it's done. The skill needs no additional IAM permissions. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill answers on-demand cost questions and isn't meant for incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need. The exception is the `unified-security-cost-optimizer` custom agent, which needs **Generic**: upload a zip (Option B) and leave **Generic** selected if you use it.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `cloudtrail-cost-optimization`, or filter by AWS service **AWS CloudTrail**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the opportunity checks in `references/opportunities.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/cloudtrail-cost-optimization/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f cloudtrail-cost-optimization.zip
   zip -r cloudtrail-cost-optimization.zip cloudtrail-cost-optimization/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l cloudtrail-cost-optimization.zip | tail -1   # expect 5 files
   ```

2. Check that the zip has this structure:

   ```text
   cloudtrail-cost-optimization.zip
   └── cloudtrail-cost-optimization/
       ├── SKILL.md                # required: frontmatter with name and description
       ├── assets/
       │   └── report-template.md
       └── references/
           ├── opportunities.md
           ├── billing-model.md
           └── api-inventory.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `cloudtrail-cost-optimization.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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
