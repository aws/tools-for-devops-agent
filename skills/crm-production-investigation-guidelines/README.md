# CRM Production Investigation Guidelines Skill (Sample)

This is a **sample skill** demonstrating how to write production investigation guidelines for the AWS DevOps Agent **Incident triage** agent type. It shows how to encode application-specific troubleshooting knowledge — architecture details, incident isolation rules, and investigation procedures — into a skill that guides the agent during production incidents.

> **Note:** This skill is specific to a fictional CRM application and cannot be reused as-is. Use it as a template for writing similar investigation guideline skills for your own applications.

## Purpose

When a production incident occurs, investigation agents might need application-specific context that goes beyond generic AWS troubleshooting: what services make up the application, what the common failure modes are, how to isolate unrelated incidents, and what observability tools to use. This sample skill demonstrates how to encode that knowledge so the Incident triage agent can conduct thorough, structured investigations without repeated human guidance.

## Key Capabilities (Demonstrated)

- Defining investigation isolation rules to prevent conflating unrelated incidents
- Specifying known incident titles and their corresponding failure domains
- Providing a structured investigation approach (symptoms → logs → audit trail → correlation → root cause → remediation)
- Documenting application architecture so the agent understands service relationships
- Listing common root cause patterns with specific AWS API calls to check

## Prerequisites

- AWS DevOps Agent space
- The target application's observability stack (CloudWatch Logs, CloudWatch Metrics, CloudTrail)
- IAM permissions for the agent to access CloudWatch, CloudTrail, and application-specific resources

## Limitations

- This skill is a sample for a fictional CRM application — it must be adapted to your own architecture before use
- Investigation guidance is only as effective as the observability data available to the agent
- The incident title matching logic assumes a fixed set of known alert titles

## Agent Types

This skill is designed for:

- **Incident Triage** — initial incident assessment and investigation

## Uploading to AWS DevOps Agent

Make sure the agent can read the application's observability data (see [Prerequisites](#prerequisites)) first, or add the skill as **Inactive** until it's done. This skill is a sample for a fictional application, so for real use adapt it first and upload your version as a zip (Option B). You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **Incident Triage** (`INCIDENT_TRIAGE`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **Incident Triage** recommended | Yes: files and agent types | Re-upload a new zip |

This skill guides the initial investigation of production incidents, so target **Incident Triage** only. **Generic** would load it for every agent type, on-demand and evaluation agents included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `crm-production-investigation-guidelines`, or filter by AWS service **AWS Lambda**, **Amazon SQS**, or **Amazon Aurora DSQL**.
4. Choose **Details** and check that the agent type is **Incident Triage**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to replace the CRM architecture and incident titles in `SKILL.md` with your own application's, or to choose different agent types.

1. Clone the repository, make your changes under `skills/crm-production-investigation-guidelines/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f crm-production-investigation-guidelines.zip
   zip -r crm-production-investigation-guidelines.zip crm-production-investigation-guidelines/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l crm-production-investigation-guidelines.zip | tail -1   # expect 1 file
   ```

2. Check that the zip has this structure:

   ```text
   crm-production-investigation-guidelines.zip
   └── crm-production-investigation-guidelines/
       └── SKILL.md                # required: frontmatter with name and description
   ```

   The zip leaves out `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `crm-production-investigation-guidelines.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **Incident Triage**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### As a Template

1. Copy the `SKILL.md` file as a starting point for your own application
2. Replace the CRM architecture section with your application's architecture
3. Replace the incident titles with your actual alert titles
4. Update the investigation approach with your organization's runbook procedures
5. Add common root cause patterns specific to your application

### Sample Chat Prompts (to test the `Incident triage` agent for this demo application)

- "Investigate the SQS Message Backlog Spike alert"
- "We received an alert for High Lambda Error Rate, all invocations failing"
- "Triage the RDS Read Latency/CPU Utilization High incident"
- "What changed in the CRM Lambda function in the last hour?"
- "Check CloudTrail for IAM permission changes affecting the CRM application"
