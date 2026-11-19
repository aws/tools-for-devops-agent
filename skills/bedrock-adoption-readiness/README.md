# Bedrock Adoption Readiness Assessor

Assess an AWS account's readiness to run Amazon Bedrock at production scale. Evaluates four dimensions: IAM governance, data retention (ZDR), quota and capacity headroom, and operational observability. Operates across both Standard Bedrock and Mantle (OpenAI models) surfaces.

## What This Skill Does

Runs a readiness assessment against your Bedrock configuration across both control planes and returns prioritized findings with specific remediation steps. Designed for teams preparing to scale Bedrock usage from experimentation to production. Covers four dimensions: IAM governance, data retention (ZDR), quota and capacity headroom, and operational observability - all API/metrics-driven with no dependency on customer configuration state.

**Example prompts:**
- "Review my Bedrock readiness for production"
- "Check if my Bedrock quotas can handle our projected growth"
- "Assess my Bedrock IAM permissions and ZDR configuration"
- "Am I ready to scale Bedrock to production?"
- "Bedrock operational review"
- "Audit my Bedrock security posture"

## Prerequisites

### IAM Permissions Required

The DevOps Agent role needs read-only access. Most required actions are covered by the [AIDevOpsAgentAccessPolicy](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html) managed policy.

Additional permissions that may be needed beyond the managed policy:
- `bedrock:GetAccountDataRetention` (for full D2 ZDR assessment - fallback available if not present)
- `iam:ListRolePolicies`, `iam:GetRolePolicy`, `iam:GetPolicyVersion` (for deep IAM policy inspection)
- `servicequotas:ListServiceQuotas` (for D3 quota headroom - Step 3.3 lists all quotas under `serviceCode: bedrock`)

**Note:** All operations are read-only. This skill does not modify any resources.

### AWS Resources

- At least one Bedrock model must have been invoked in the last 7 days for metrics-based analysis
- Organization-level SCP assessment requires the account to have Organizations API access (management account or delegated admin)

## Uploading to AWS DevOps Agent

Add the IAM permissions in [Prerequisites](#prerequisites) to the DevOps Agent role first, or add the skill as **Inactive** until they're in place. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand readiness assessments and isn't meant for active incident investigation, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `bedrock-adoption-readiness`, or filter by AWS service **Amazon Bedrock**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the alarm and metric thresholds the observability dimension checks in `SKILL.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/bedrock-adoption-readiness/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f bedrock-adoption-readiness.zip
   zip -r bedrock-adoption-readiness.zip bedrock-adoption-readiness/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l bedrock-adoption-readiness.zip | tail -1   # expect 1 file
   ```

2. Check that the zip has this structure:

   ```text
   bedrock-adoption-readiness.zip
   └── bedrock-adoption-readiness/
       └── SKILL.md                      # required: frontmatter with name and description
   ```

   The zip leaves out `evals/`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `bedrock-adoption-readiness.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## How to Use with DevOps Agent

1. Upload this skill to your DevOps Agent Space
2. Select the **On-demand** agent type
3. Ensure the DevOps Agent role has the IAM permissions listed above
4. Ask natural language questions about Bedrock readiness

**Agent types:** On-demand

## Output

The skill generates a structured assessment report with:
- Overall readiness verdict (READY / READY WITH ACTIONS / NOT READY)
- Per-dimension status (ASSESSED / NOT_ASSESSED / INSUFFICIENT_DATA)
- Findings by severity with specific remediation steps
- Model inventory with per-model utilization metrics
- Priority actions sorted by urgency

## Key Features

- **Dual-surface assessment**: Checks both Standard Bedrock (AWS/Bedrock) and Mantle (AWS/BedrockMantle) namespaces
- **Per-model quota comparison**: Compares each model's peak against its specific quota (not account aggregate)
- **Cache-aware arithmetic**: Accounts for prompt caching in quota calculations (cache reads don't consume quota)
- **Covered Model detection**: Identifies compliance-relevant retention implications from metrics alone
- **Graceful degradation**: Never silently skips a dimension - reports NOT_ASSESSED with reason when data is unreachable
- **Multi-region**: Discovers and assesses all regions with Bedrock activity

## Limitations

- Does not currently assess model selection fitness or cost optimization (requires model invocation logging to be enabled)
- Account-level data retention mode may require `bedrock:GetAccountDataRetention` permission not yet in standard DA policy (fallback available)
- Organization SCP assessment may be limited from member accounts without delegated admin access
- Mantle retention endpoint (`/v1/data_retention`) is a REST endpoint without SDK client - not directly assessable, uses indirect evidence

## Disclaimer

> This skill is sample code, not intended for production use without additional review and testing. Users should validate findings in a non-production environment first. Recommendations are based on AWS best practices as of the skill version date and may not reflect the latest service changes.
