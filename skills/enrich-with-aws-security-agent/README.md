# Enrich with AWS Security Agent

This skill enables the AWS DevOps Agent to query AWS Security Agent CloudWatch logs during incident investigations, surfacing code-level security findings that may be the root cause of application outages.

## ⚠️ Important Notice

This skill is provided as sample code. If you intend to deploy it in production, start with a non-production environment first. Review IAM permissions and security configurations against your organization's policies, and validate that skill behavior meets your operational requirements before production use.

## Purpose

When an application outage or degradation occurs without a clear infrastructure cause, the root cause may be a security vulnerability — such as SSRF, injection attacks, or compromised dependencies. This skill queries AWS Security Agent findings stored in CloudWatch Logs to retrieve actionable details (file path, line number, vulnerability type, severity) that customers can directly fix.

## Key Capabilities

- Query AWS Security Agent CloudWatch log groups for security findings
- Extract actionable vulnerability details: file path, line number, vulnerability type, severity
- Correlate security findings with current incident symptoms and timeframes
- Present remediation guidance with exact code locations
- Automatically activate when application errors have no obvious infrastructure cause

## Prerequisites

- AWS Security Agent configured and writing findings to CloudWatch Logs
- Agent permissions for `logs:DescribeLogGroups`, `logs:StartQuery`, `logs:GetQueryResults` on Security Agent log groups (e.g., `/aws/securityagent/*`)

## Limitations

- Requires AWS Security Agent to be configured and actively scanning — no findings will exist if the service is not enabled
- Log retention depends on CloudWatch Logs retention settings for the Security Agent log groups
- Findings are only as current as the last Security Agent scan

## Agent Types

This skill is used by the following agent types:

- **On-demand** — conversational security finding lookup and analysis
- **Incident RCA** — automated root cause analysis when security issues may cause outages

## Uploading to AWS DevOps Agent

Complete the [prerequisites](#prerequisites) first (AWS Security Agent writing findings to CloudWatch Logs, and the CloudWatch Logs query permissions), or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`) and **Incident RCA** (`INCIDENT_RCA`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** and **Incident RCA** recommended | Yes: files and agent types | Re-upload a new zip |

Target **On-demand** for security finding lookups and **Incident RCA** so investigations can check for a security root cause when an outage has no clear infrastructure cause. **Generic** would also load it for incident triage, mitigation, and the other agent types, which don't need it.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent types.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `enrich-with-aws-security-agent`, or filter by AWS service **AWS Security Agent**.
4. Choose **Details** and check that the agent types are **On-demand** and **Incident RCA**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to add your own Security Agent log group names to the log group step in `SKILL.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/enrich-with-aws-security-agent/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f enrich-with-aws-security-agent.zip
   zip -r enrich-with-aws-security-agent.zip enrich-with-aws-security-agent/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l enrich-with-aws-security-agent.zip | tail -1   # expect 1 file
   ```

2. Check that the zip has this structure:

   ```text
   enrich-with-aws-security-agent.zip
   └── enrich-with-aws-security-agent/
       └── SKILL.md                          # required: frontmatter with name and description
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `enrich-with-aws-security-agent.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand** and **Incident RCA**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use This Skill

### Chat

- "Check AWS Security Agent findings for my application — are there any critical vulnerabilities?"
- "Show me security findings related to SSRF or injection attacks in the last 7 days."
- "What security vulnerabilities has AWS Security Agent found in the orders service?"
- "Are there any hardcoded secrets or credential exposure findings?"

### Investigation

- "My application is returning 500 errors but there were no recent deployments. Investigate."
- "We're seeing unexplained outages on the checkout service — could it be a security issue?"
- "The API started failing with authentication errors. Check if there are security findings related to this."
- "Our web application is behaving unexpectedly and we suspect injection attacks. Investigate."
