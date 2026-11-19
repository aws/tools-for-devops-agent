# AWS Health Events Skill

This skill enables the AWS DevOps Agent to retrieve and analyze AWS Health events during incident investigation, root cause analysis, and operational troubleshooting.

## Purpose

When an operational incident occurs, AWS Health events provide critical visibility into service disruptions, scheduled maintenance, and account-specific notifications that may explain or correlate with observed issues. This skill searches AWS Health events by service, time window, severity, region, and event type to surface AWS-side events as potential root causes or contributing factors.

## Key Capabilities

- Retrieve open and resolved AWS Health events via the Health API
- Search and filter events by service, severity, time range, region, and event type
- Identify affected resources impacted by Health events
- Correlate Health events with current incidents to determine root cause or contributing factors
- Generate health posture reports summarizing account health over configurable time periods

## Prerequisites

- IAM permissions for `health:Describe*` actions (`health:DescribeEvents`, `health:DescribeEventDetails`, `health:DescribeAffectedEntities`, `health:DescribeEventTypes`)
- AWS Health API access (requires AWS Business Support+, Enterprise Support, or Unified Operations support plan)

## Limitations

- The AWS Health API is only available in the `us-east-1` region for commercial accounts
- Health event data retention is limited by the AWS Health service retention period
- API rate limits apply — the skill implements exponential backoff for throttled requests

## Agent Types

This skill is used by the following agent types:

- **On-demand** — conversational health event lookup, reporting, and analysis
- **Incident RCA** — root cause analysis during active incidents

## Uploading to AWS DevOps Agent

Add the IAM permissions and support plan in [Prerequisites](#prerequisites) first, or add the skill as **Inactive** until they're in place. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

This skill answers health-event questions on demand and checks for AWS-side causes during root cause analysis, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, mitigation and evaluation included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `aws-health-events`, or filter by AWS service **AWS Health**.
4. Choose **Details** and check that the agent types listed are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to add API notes or filter examples in `references/health-api-reference.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/aws-health-events/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f aws-health-events.zip
   zip -r aws-health-events.zip aws-health-events/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l aws-health-events.zip | tail -1   # expect 2 files
   ```

2. Check that the zip has this structure:

   ```text
   aws-health-events.zip
   └── aws-health-events/
       ├── SKILL.md                      # required: frontmatter with name and description
       └── references/
           └── health-api-reference.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `aws-health-events.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

This skill is most suitable for chat and investigation. Below are sample prompts for each use-case.

### Chat

- "Create a health events report for the last 30 days, including breakdowns by service and event type."
- "Show me all open AWS Health events affecting my account."
- "Are there any scheduled maintenance events for RDS in the next 7 days?"
- "Summarize all EC2 health events from the past quarter."
- "What health events have occurred in us-west-2 this month?"
- "Give me a health posture summary for my account over the last 90 days."

### Investigation

- "Investigate the RDS connectivity alarm — are there any related AWS Health events?"
- "We're seeing elevated error rates on our ECS service. Check if there's an AWS-side issue."
- "Our Lambda functions are timing out. Is there an active Health event for Lambda in us-east-1?"
- "There's a latency spike on our ALB starting around 2am UTC — correlate with any Health events."
- "Multiple services in us-west-2 are degraded. Check for regional Health events."
- "The same EBS performance issue keeps recurring. Are there related Health events or scheduled changes?"
