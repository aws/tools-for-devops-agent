# Support Cases Skill

This skill enables the AWS DevOps Agent to retrieve and analyze AWS Support cases during incident investigation, root cause analysis, and operational troubleshooting.

## Purpose

When an operational incident occurs, historical support cases often contain valuable context — prior root causes, proven remediations, and recurring patterns. This skill searches past AWS Support cases by service, time window, severity, and error keywords to surface relevant history that informs the current investigation.

## Key Capabilities

- Retrieve open and resolved AWS Support cases via the Support API
- Search and filter cases by service, severity, time range, and keywords
- Review case communications for root cause statements and remediation steps
- Correlate historical findings with current incident symptoms
- Identify recurring patterns that may require permanent fixes

## Prerequisites

- AWS account with Business Support+, Enterprise Support, or Unified Operations plan
- Agent permissions for `support:DescribeCases` and `support:DescribeCommunications`

## Limitations

- Support case data is only available for up to 24 months after creation

## Agent Types

This skill is used by the following agent types:

- **On-demand** — conversational support case lookup and analysis
- **Incident RCA** — root cause analysis during active incidents

## Uploading to AWS DevOps Agent

Confirm the [Support plan and permissions](#prerequisites) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

Past support cases help in chat lookups and in root cause analysis, where prior root causes and remediations inform the current incident, so target **On-demand** and **Incident RCA**. **Generic** would load it for every agent type, incident triage included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `support-cases`, or filter by AWS service **AWS Support**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to adjust the matching heuristics in `references/case-review-patterns.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/support-cases/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f support-cases.zip
   zip -r support-cases.zip support-cases/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l support-cases.zip | tail -1   # expect 3 files
   ```

2. Check that the zip has this structure:

   ```text
   support-cases.zip
   └── support-cases/
       ├── SKILL.md                      # required: frontmatter with name and description
       └── references/
           ├── support-api-reference.md  # Support API operations the skill uses
           └── case-review-patterns.md   # heuristics for finding relevant past cases
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `support-cases.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

This skill is most suitable for chat and investigation. Below are sample prompts for each use-case

### Chat

- "Create a support cases report for all support cases in the last 12 months, including breakdowns by service and severity"
- "Show me all support cases opened in the last 30 days for RDS."
- "What was the resolution for case-123456789010-muen-2024?"
- "Are there any open critical-severity cases in this account?"
- "Summarize the communications on our most recent EC2 support case."
- "Have we filed any support cases related to Lambda throttling this quarter?"

### Investigation

- "Investigate the Lambda-Errors alarm"
- "We're seeing 5xx errors on our ALB — can you investigate?"
- "RDS connections are maxing out and queries are timing out. What's going on?"
- "There's a latency spike on our ECS service starting around 3am UTC."
- "Our last deployment triggered elevated error rates across multiple endpoints."
- "The same DynamoDB throttling alarm fired again. Help me figure out why this keeps happening."
