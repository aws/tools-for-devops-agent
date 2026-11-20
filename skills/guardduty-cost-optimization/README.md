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

- **On-demand** — "why is my GuardDuty bill so high", "which protection plan costs the most".

Select **Generic** if you want the skill available to all agent types — required if you use it with the `unified-security-cost-optimizer` custom agent.

## Uploading to AWS DevOps Agent

The skill needs no extra IAM permissions (see [Prerequisites](#prerequisites)), only an Agent Space with the target account as a cloud source. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended, or **Generic** for the custom agent | Yes: files and agent types | Re-upload a new zip |

This skill answers on-demand cost questions and isn't meant for incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need. The exception is the [unified-security-cost-optimizer custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/unified-security-cost-optimizer): to use the skill through it, upload the zip (Option B) and leave **Generic** selected so the custom agent can load it.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `guardduty-cost-optimization`, or filter by AWS service **Amazon GuardDuty**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the report layout in `assets/report-template.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/guardduty-cost-optimization/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f guardduty-cost-optimization.zip
   zip -r guardduty-cost-optimization.zip guardduty-cost-optimization/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l guardduty-cost-optimization.zip | tail -1   # expect 5 files
   ```

2. Check that the zip has this structure:

   ```text
   guardduty-cost-optimization.zip
   └── guardduty-cost-optimization/
       ├── SKILL.md                          # required: frontmatter with name and description
       ├── references/
       │   ├── billing-model.md
       │   ├── data-collection.md
       │   └── opportunities.md
       └── assets/
           └── report-template.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `guardduty-cost-optimization.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**. To use the skill through the unified-security-cost-optimizer custom agent, leave **Generic** selected instead.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

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
