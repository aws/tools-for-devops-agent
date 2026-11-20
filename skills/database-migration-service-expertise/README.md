# DMS Operational Review — AWS DevOps Agent Skill

A comprehensive AWS Database Migration Service (DMS) operational review and troubleshooting skill for [AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html). Conducts best-practices assessments, health checks, performance diagnostics, cost optimization reviews, and migration cutover guidance.

## What It Does

When activated via Chat, this skill instructs the DevOps Agent to:

1. Discover DMS replication instances, tasks, and endpoints in the configured account/regions.
2. Collect instance configuration, task settings, endpoint connectivity, table statistics, and version data.
3. Collect 7-day historical CloudWatch metrics and task logs.
4. Analyze against 5 assessment categories (Instance Health, Task Health, Endpoint Security, Performance, Cost Efficiency) using a weighted 100-point scoring model.
5. For troubleshooting: classify errors, run targeted diagnostics, and provide root cause analysis.
6. For cutover planning: validate pre-cutover checklist, guide execution, and document rollback procedures.
7. Generate a shareable report artifact per environment, named `dms-review-<instance-name>-<YYYY-MM-DD>.md`.

## Agent Types

This skill is intended for the following agent types (selected in the Operator Web App at upload time):

- **On-demand** — conversational invocation in Chat ("review my DMS environment", "troubleshoot DMS task failure").

Select **Generic** instead if you want the skill available to all agent types.

## Prerequisites

### 1. An AWS DevOps Agent Space with the target AWS account

You need an existing [Agent Space](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-creating-an-agent-space.html) with the target AWS account configured as a cloud source.

### 2. IAM permissions for DMS read access

The Agent Space IAM role needs read-only permissions for DMS resources. Nearly all required actions are already covered by the `AIDevOpsAgentAccessPolicy` managed policy attached to the DevOps Agent role. The one exception is `dms:TestConnection`, which must be granted separately — use the [CloudFormation template](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml).

For reference, the complete action set used by this skill:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dms:Describe*",
        "dms:List*",
        "dms:TestConnection",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "logs:FilterLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "ec2:DescribeSecurityGroups",
        "ec2:DescribeVpcs",
        "ec2:DescribeSubnets",
        "health:DescribeEvents",
        "health:DescribeEventDetails"
      ],
      "Resource": "*"
    }
  ]
}
```

### 3. DMS task logging enabled

For troubleshooting and log analysis, DMS tasks must have CloudWatch Logs enabled. Tasks with `EnableLogging: false` will have limited diagnostic capability.

## Uploading to AWS DevOps Agent

Grant `dms:TestConnection` and enable DMS task logging (see [Prerequisites](#prerequisites)) first, or add the skill as **Inactive** until it's done. You can add this skill in two ways:

| Option | Agent type | Can you edit it? | Updates |
|---|---|---|---|
| A. Skills Catalog (recommended) | **On-demand** (`CHAT`), set by the skill | No | **Sync** on the skill's row |
| B. Zip upload | You choose at upload; **On-demand** recommended | Yes: files and agent types | Re-upload a new zip |

This skill runs on-demand DMS reviews, troubleshooting, and cutover planning that an operator asks for in chat, so target **On-demand** only. **Generic** would load it for every agent type, incident triage and RCA included, and add context those agents don't need.

### Option A: Add from the Skills Catalog (recommended)

You don't need a GitHub account or a zip file. The catalog copy keeps the published name, description, files, and agent type.

1. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
2. Next to **Add skill**, choose **Browse catalog**.
3. In **Find skills**, enter `database-migration-service-expertise`, or filter by AWS service **AWS Database Migration Service**.
4. Choose **Details** and check that the agent type is **On-demand**.
5. Optional: to add the skill without activating it, choose the dropdown arrow next to **Add to agent space** and set **Status** to **Inactive**.
6. Choose **Add to agent space**. When the button shows **Installed**, choose **View in Skills**.

Catalog skills don't update automatically. To get a newer version, choose **Sync** on the skill's row. Your operator role needs the `AIDevOpsOperatorAppAccessPolicy` AWS managed policy, or the catalog and asset actions listed in [Skills Catalog](https://docs.aws.amazon.com/devopsagent/latest/userguide/devops-agent-skills-skills-catalog.html).

### Option B: Upload as a zip file (customizable)

Use this option to change the skill, for example to change the validation criteria in `references/dms-validation-checklist.md`, or to choose different agent types.

1. Clone the repository, make your changes under `skills/database-migration-service-expertise/`, and build the zip from `skills/`. Delete any old archive first so removed files don't linger in it:

   ```bash
   git clone https://github.com/aws/tools-for-devops-agent.git
   cd tools-for-devops-agent/skills
   rm -f database-migration-service-expertise.zip
   zip -r database-migration-service-expertise.zip database-migration-service-expertise/ \
     -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' \
        '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' \
     -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' \
        '*/CHANGELOG.md' '*/evals/*'
   unzip -l database-migration-service-expertise.zip | tail -1   # expect 4 files
   ```

2. Check that the zip has this structure:

   ```text
   database-migration-service-expertise.zip
   └── database-migration-service-expertise/
       ├── SKILL.md                # required: frontmatter with name and description
       └── references/
           ├── dms-best-practices.md
           ├── dms-validation-checklist.md
           └── dms-version-reference.md
   ```

   The zip leaves out `evals/`, `.skilleval.yaml`, `CHANGELOG.md`, and `README.md`.

3. In the DevOps Agent web app, open the **Knowledge** page and choose the **Skills** tab.
4. Choose **Add skill**, and then choose **Upload skill**.
5. Drag and drop `database-migration-service-expertise.zip`, or browse to it.
6. For **Agent Type**, clear **Generic** and select **On-demand**.
7. Review the validation results, and then choose **Upload**.

If you also added the catalog copy, delete one of them. Agents might use only one of two skills that share a name. For more information, see [Uploading a skill](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#uploading-a-skill).

## Connecting additional observability sources (optional)

For richer analysis, connect your observability tools to the Agent Space:

| Tool | Setup Guide |
|------|-------------|
| CloudWatch | Built-in (no setup needed) |
| Datadog | [Connecting Datadog](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-datadog.html) |
| Dynatrace | [Connecting Dynatrace](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-dynatrace.html) |
| New Relic | [Connecting New Relic](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-new-relic.html) |
| Splunk | [Connecting Splunk](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-splunk.html) |
| Grafana | [Connecting Grafana](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-telemetry-sources-connecting-grafana.html) |
| Custom MCP | [Connecting MCP Servers](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-capabilities-for-aws-devops-agent-connecting-mcp-servers.html) |

## Usage

In the DevOps Agent Chat, use natural language:

- *"Run a DMS operational review for all instances in us-east-1."*
- *"Review my DMS replication instance `prod-migrator` for best practices."*
- *"Troubleshoot CDC latency on task `oracle-to-aurora-cdc`."*
- *"Assess cost optimization opportunities for my DMS environment."*
- *"Help me plan a migration cutover for task `full-load-cdc-orders`."*
- *"Check DMS version deprecations and recommend upgrades."*

The agent will:

- Collect all data automatically (no prompts for confirmation).
- Cross-reference versions against known issues and deprecation timelines.
- Generate a report artifact per environment, named `dms-review-<instance-name>-<YYYY-MM-DD>.md`.

## Skill Contents

```
database-migration-service-expertise/
├── SKILL.md                           # main skill instructions (with frontmatter)
├── README.md                          # this file
├── CHANGELOG.md                       # version history
├── .skilleval.yaml                    # evaluation config
├── references/
│   ├── dms-best-practices.md          # comprehensive DMS best practices
│   ├── dms-validation-checklist.md    # operations review validation criteria
│   └── dms-version-reference.md       # version lifecycle and known bugs
└── evals/                             # evaluation data (not included in upload zip)
    ├── evals.json                     # functional evaluation test cases
    ├── eval_queries.json              # trigger/routing test queries
    ├── benchmark.json                 # functional eval benchmark results
    ├── report.json                    # unified eval report
    ├── trigger_report.json            # trigger eval results
    └── files/
        └── dms-context.json           # mock DMS environment for evals
```

`evals/` is for skill evaluation tracking and is **not** included in the upload zip.

## Assessment Categories

| # | Category | Weight | Scope |
|---|----------|--------|-------|
| 1 | Instance Health | 25 pts | Status, version, Multi-AZ, public access, storage, encryption |
| 2 | Task Health | 25 pts | Task status, table errors, CDC latency, logging |
| 3 | Endpoint Security | 20 pts | SSL mode, Secrets Manager, connectivity, SG rules |
| 4 | Performance | 15 pts | CPU, memory, swap, disk queue, CDC throughput |
| 5 | Cost Efficiency | 15 pts | Right-sizing, idle resources, Multi-AZ justification |

## Additional Capabilities

| Capability | Description |
|------------|-------------|
| Troubleshooting | Error classification, targeted diagnostics, log analysis |
| Migration Cutover | Pre-cutover checklist, execution steps, rollback procedures |
| Version Management | Deprecation tracking, upgrade guidance, known bug cross-reference |
| DMS Serverless | Suitability assessment, provisioned vs serverless evaluation |
| Homogeneous Migration | Native tool alternatives for same-engine migrations |
| Pre-Migration Assessment | Fleet Advisor, SCT integration, task assessment guidance |
| Data Validation | Validation failure investigation and remediation |

## Severity Definitions

| Severity | Definition | SLA |
|----------|------------|-----|
| CRITICAL | Immediate risk to migration integrity, data loss, or security | 24–48 hours |
| HIGH | Significant gap that could lead to task failures | 1 week |
| MEDIUM | Notable improvement opportunity | 30 days |
| LOW | Minor optimization or hardening | When convenient |
| INFO | Observation, no action required | N/A |

## License

⚠️ **This skill is sample code, not intended for production use without additional review and testing.** Users should validate all recommendations in a non-production environment first. Always test DMS configuration changes (version upgrades, task setting modifications, instance resizing) in a staging environment before applying to production migrations.
