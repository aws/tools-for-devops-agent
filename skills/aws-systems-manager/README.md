# AWS Systems Manager

> **Note:** This skill is sample code. It isn't intended for production use without additional review and testing. Validate it in a non-production environment first.

## Purpose

One skill for AWS Systems Manager tasks in DevOps Agent. A short description selects the skill; `SKILL.md` routes each request to one task chapter and sets the safety rules every chapter follows; the agent loads only the chapter it needs. New Systems Manager capabilities are added as chapters under `references/<capability>/`, so they share one entry point and one safety contract instead of competing as separate skills.

The skill currently covers **Automation**:

| Chapter | What it does |
|---|---|
| [Runbook discovery](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-systems-manager/references/automation/runbook-discovery.md) | Finds an AWS-owned runbook for a symptom, resource type or finding from a catalog of the 485 AWS-owned Automation runbooks (description, required parameters and risk tier for each), confirms it in the target Region, and falls back to the account's own runbooks |
| [Execution](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-systems-manager/references/automation/execution.md) | Prepares start commands with rate control (`MaxConcurrency`, `MaxErrors`) and an alarm that stops the run, including multi-account runs, and diagnoses executions that failed, timed out, were cancelled or are waiting for approval |
| [Hardening](https://github.com/aws/tools-for-devops-agent/blob/main/skills/aws-systems-manager/references/automation/hardening.md) | Reviews a runbook's content for command injection, secret handling, parameter validation and structure problems, with each check backed by public documentation, and returns a hardened version |

## Key Capabilities

- Routes Systems Manager requests to one task chapter, with explicit handoffs between chapters
- Applies one safety contract: read-only investigation first, facts separated from hypotheses, a plan with rollback and verification before any change, explicit approval, and verification of the result
- Finds Automation runbooks by symptom or resource type, and reports each one's risk tier and the approval it needs
- Builds rate-controlled, alarm-protected start commands for a person to run, and explains execution results from their step details
- Reviews runbook content and returns a hardened document

## Prerequisites

- The skill reads with `ssm:DescribeDocument`, `ssm:GetDocument`, `ssm:ListDocuments`, `ssm:DescribeAutomationExecutions`, `ssm:DescribeAutomationStepExecutions`, `tag:GetResources`, `cloudwatch:DescribeAlarms` and `iam:GetRole`, which the [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html) managed policy grants. No additional permissions are needed.
- The person who runs the prepared commands needs `ssm:StartAutomationExecution`, `ssm:StopAutomationExecution` and `ssm:SendAutomationSignal`, and `iam:PassRole` for the runbook's assume role.
- Multi-account runs need the `AWS-SystemsManager-AutomationAdministrationRole` and `AWS-SystemsManager-AutomationExecutionRole` roles; see [Running automations in multiple AWS Regions and accounts](https://docs.aws.amazon.com/systems-manager/latest/userguide/running-automations-multiple-accounts-regions.html).

## Limitations

- Only Automation is covered today. For other Systems Manager capabilities, the skill says so and falls back to the public documentation.
- The agent doesn't start, stop or signal executions; it prepares the commands for a person to run.
- The runbook catalog reflects the AWS-owned runbooks published on 2026-11-04. Availability and versions differ by Region, so the skill confirms every runbook with a live call.
- Risk tiers come from static analysis of each runbook's steps. Runbooks that run shell or PowerShell scripts on an instance are rated `mutating-reversible` without inspecting the script.
- The hardening review is static: it doesn't run the runbook or review the assume role's IAM policy.
- The multi-account guidance follows the Systems Manager documentation; single-account behaviour was verified in a test account.

## Agent Types

This skill is used by the following agent types:

- **Chat tasks** (`CHAT`) — find runbooks, prepare commands, explain executions, review runbooks
- **Incident triage** (`INCIDENT_TRIAGE`) and **Incident RCA** (`INCIDENT_RCA`) — find diagnostic runbooks and diagnose failed executions
- **Incident mitigation** (`INCIDENT_MITIGATION`) — prepare a safe run of a remediation runbook
- **Prevention** (`PREVENTION`) — recommend remediation runbooks and review account-owned runbooks
- **Release readiness review** (`RELEASE_READINESS_REVIEW`) — review runbooks that ship with a release

## Uploading to AWS DevOps Agent

To deploy this skill to your Agent Space, you can use any of three ways:

**Option A: Import from GitHub (recommended)**

If you have a [GitHub connection configured](https://docs.aws.amazon.com/devopsagent/latest/userguide/connecting-to-cicd-pipelines-connecting-github.html) in your Agent Space, you can import this skill directly from the repository. In the DevOps Agent web app, go to Settings → Add Skill → Import from repository, then point to the `skills/aws-systems-manager` directory. See [Importing a skill from a repository](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-devops-agent-skills.html#creating-skills) for full instructions.

**Option B: Upload as a zip file**

1. Zip the skill directory (only including allowed extensions):

   ```bash
   cd skills
   zip -r aws-systems-manager.zip aws-systems-manager/ -i '*.md' '*.txt' '*.json' '*.yaml' '*.yml' '*.xml' '*.csv' '*.tsv' '*.html' '*.htm' '*.png' '*.jpg' '*.jpeg' '*.gif' '*.svg' '*.webp' '*.pdf' -x '*/.claude/*' '*/scripts/*' '*/README.md' '*/.skilleval.yaml' '*/.skilleval.yml' '*/CHANGELOG.md' '*/evals/*'
   ```

2. In the AWS DevOps Agent web app, navigate to the **Skills** page.
3. Click **Add skill** → **Upload skill**.
4. Drag and drop the zip file.
5. Select the agent types: **Chat tasks**, **Incident triage**, **Incident RCA**, **Incident mitigation**, **Prevention** and **Release readiness review**.
6. Click **Upload**.

**Option C: Upload via the Asset API**

Use the AWS DevOps Agent Asset API to manage the skill programmatically. Assign it to the `CHAT`, `INCIDENT_TRIAGE`, `INCIDENT_RCA`, `INCIDENT_MITIGATION`, `PREVENTION` and `RELEASE_READINESS_REVIEW` agent types. See [Managing a skill end-to-end](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-managing-assets.html#managing-a-skill-end-to-end).

## How to Use This Skill

### Find a runbook

- "Is there an AWS runbook that can fix SSH access to my EC2 instance?"
- "Which Automation runbook should I use to block public access on an S3 bucket in us-west-2?"
- "Do we have any runbooks of our own for rotating database credentials?"

### Run and diagnose

- "Give me the command to run AWS-RestartEC2Instance on every instance tagged app=web, one at a time, stopping if the web-5xx alarm fires"
- "Why did automation execution 00000001-0000-4000-8000-000000000000 fail?"
- "My execution is stuck in Waiting. What does it need?"

### Review a runbook

- "Review our runbook MyOrg-RestartAppService for security issues before we share it"
- "Harden this runbook: (paste YAML)"

## Adding a chapter

To add another Systems Manager capability:

1. Add its chapters under `references/<capability>/`, each with its own checklist, self-check and report format, following the safety contract in `SKILL.md`.
2. Add one row per chapter to the routing table in `SKILL.md`, so each intent has one primary route.
3. If the description must change to select the new capability, keep it short and rerun the trigger evals, including the negative cases.
4. Add eval cases for the new chapters to `evals/evals.json`, bump the version, and add a CHANGELOG entry.

## Related

- [aws-systems-manager custom agent](https://github.com/aws/tools-for-devops-agent/tree/main/custom-agents/aws-systems-manager) — scheduled read-only review that uses this skill
- [AWS Systems Manager Automation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-automation.html)
- [Systems Manager Automation runbook reference](https://docs.aws.amazon.com/systems-manager-automation-runbooks/latest/userguide/automation-runbook-reference.html)
- [Security best practices for Systems Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/security-best-practices.html)
