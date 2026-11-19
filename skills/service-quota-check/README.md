# Service Quota Check

This skill enables the AWS DevOps Agent to check AWS service quota utilization during incident investigations, capacity planning, and before provisioning new resources.

## Purpose

When operational issues arise from hitting AWS service limits, or when recommendations involve provisioning additional resources, this skill checks current quota values and utilization. It proactively identifies quotas at risk (85%+ utilization), requests increases via the Service Quotas API when possible, and guides users to open support cases when programmatic increases are not available.

## Key Capabilities

- Retrieve current quota values and applied limits for any AWS service
- Calculate real-time utilization using CloudWatch metrics or resource counts
- Flag quotas at 85%+ utilization with risk-level assessment
- Submit quota increase requests via the Service Quotas API
- Check for existing pending increase requests to avoid duplicates
- Recommend support case creation for non-adjustable quotas
- Perform bulk quota assessments across all quotas for a service

## Prerequisites

- Agent permissions for Service Quotas APIs: `servicequotas:ListServices`, `servicequotas:ListServiceQuotas`, `servicequotas:GetServiceQuota`, `servicequotas:RequestServiceQuotaIncrease`, `servicequotas:ListRequestedServiceQuotaChangeHistory`, `servicequotas:CreateSupportCase`
- Agent permissions for CloudWatch: `cloudwatch:GetMetricData`, `cloudwatch:GetMetricStatistics`
- For resource counting fallback: read-only permissions on target services (e.g., `ec2:DescribeInstances`, `rds:DescribeDBInstances`)

## Limitations

- Service Quotas is a regional service; quotas must be checked in the correct region
- Not all quotas have a `UsageMetric` in CloudWatch; some require manual resource counting
- Some quotas are not adjustable via the API and require support cases
- Quota increase requests may take minutes (auto-approved) to days (manual review)
- Rate-based quotas (requests per second) require different monitoring than resource-count quotas

## Agent Types

This skill is used by the following agent types:

- **On-demand** — conversational quota lookup, capacity planning, and proactive checks
- **Incident RCA** — quota exhaustion as root cause during active incidents

## Uploading to AWS DevOps Agent

Grant the [Service Quotas and CloudWatch permissions](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

Quota checks help in chat, for capacity planning before you provision, and in root cause analysis, when quota exhaustion causes an incident, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, incident triage included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `service-quota-check`, or filter by AWS service **AWS Service Quotas**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to add quota codes your team checks often to `references/common-quota-codes.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/service-quota-check/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f service-quota-check.zip
   zip -r service-quota-check.zip service-quota-check/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l service-quota-check.zip | tail -1   # expect 2 files
   ```

2. Check that the zip has this structure:

   ```text
   service-quota-check.zip
   └── service-quota-check/
       ├── SKILL.md                    # required: frontmatter with name and description
       └── references/
           └── common-quota-codes.md   # quota codes for common services
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `service-quota-check.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

This skill is most suitable for chat and investigation. Below are sample prompts for each use-case.

### Chat

- "Check the EC2 vCPU quota utilization in us-east-1."
- "What's my current VPC quota and how many VPCs am I using?"
- "Show me all quotas for Lambda that are above 70% utilization."
- "Can I launch 50 more t3.large instances without hitting the quota?"
- "List all service quotas that are near their limits across EC2, VPC, and RDS."
- "Request an increase for my NAT Gateway quota in eu-west-1."

### Investigation

- "I'm getting LimitExceededException when creating a new VPC. Check quotas."
- "Lambda function invocations are being throttled. Check if we're hitting concurrent execution limits."
- "EC2 instance launch failed with InsufficientInstanceCapacity. Is this a quota issue?"
- "We need to scale our ECS cluster but tasks are failing to start. Check Fargate quotas."
- "The recommendation is to add more read replicas for RDS. Check if the quota allows it."
- "CloudFormation stack creation failed — investigate if we hit the stack count limit."
