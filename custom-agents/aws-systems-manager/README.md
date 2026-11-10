# AWS Systems Manager — Custom Agent

> **Note:** This custom agent is sample code. It isn't intended for production use without additional review and testing. Validate it in a non-production environment first.

## Purpose

This custom agent reviews how an account uses AWS Systems Manager. On a schedule or on demand, it runs one read-only review per Systems Manager capability and produces one report with a section per capability. It uses the [aws-systems-manager](../../skills/aws-systems-manager/) skill, so each review follows that skill's chapters and safety contract.

The agent currently reviews **Automation**: it finds executions that failed, timed out or were cancelled and explains why, flags runs against many resources that had no alarm or loose rate control, scans the account's own runbooks for security and reliability problems, and suggests AWS-owned runbooks to replace account-owned ones that keep failing. New capability reviews are added as sections under "Capability reviews" in `SYSTEM_PROMPT.md`.

## Key Capabilities

- Runs one review per Systems Manager capability, in one report
- Automation: finds failed, timed-out and cancelled executions, groups child executions under their parent, and names the failing step and error
- Automation: detects recurring failures by runbook and cause
- Automation: flags multi-target and multi-account runs without `AlarmConfiguration`, or with high `MaxConcurrency` or `MaxErrors`
- Automation: reviews account-owned runbooks and reports findings by severity, and suggests AWS-owned runbooks for recurring failures
- Creates Recommendations for critical findings
- Read-only: calls no API that changes anything

## Prerequisites

- An AWS DevOps Agent space
- The [aws-systems-manager](../../skills/aws-systems-manager/) skill uploaded to the Agent Space
- The agent calls `ssm:DescribeAutomationExecutions`, `ssm:DescribeAutomationStepExecutions`, `ssm:ListDocuments`, `ssm:GetDocument` and `ssm:DescribeDocument`, which the [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html) managed policy grants. No additional permissions are needed.

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" menu (on the bottom left pane)
2. Click "Create agent" (on the right side), then on the new menu that popped up, click "Form" (the left-most option)
3. In the "Name" field, use "aws-systems-manager"
4. Copy the content of the "SYSTEM_PROMPT.md" file from this directory, and paste it into the "System prompt" field in the custom agent creation form
5. In the "Skills" drop-down list, select the "aws-systems-manager" skill, and click "Create agent"
6. Now add the `use_aws` tool — in the new custom agent's window, click "Edit"
7. In the new popped up window, select "Chat". A new chat will start on the left side. Wait for DevOps Agent to finish thinking, and it'll ask you what would you like to change
8. Type "Add the use_aws tool to this custom agent". Once the chat is finished, verify in the custom agent's page that `use_aws` is shown under "Tools" for this custom agent

## Executing the Agent

### Scheduled Execution (Recommended)

Run it weekly, so each run covers the previous 7 days. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) to set up a schedule.

### On-Demand Execution

Run it from the custom agent page or via chat, for example:

- "Review Automation in us-east-1 and eu-west-1 for the last 30 days"
- "Only run the Automation review"
- "Only review executions of our own runbooks"
- "Why did our patching automations fail this week?"

## Output

- **Task journal entry** — the report: a summary, one section per capability review (for Automation: problem executions, rate-control and alarm findings, runbook findings, suggested AWS-owned runbooks), and anything that couldn't be checked
- **Recommendations** — for critical runbook findings, recurring failures and multi-target runs without an alarm

## Adding a capability review

Add a subsection under "Capability reviews" in `SYSTEM_PROMPT.md` that names the skill chapters it uses, its read-only steps and its Recommendations, and add its section to the Output list. The common approach, constraints and report structure apply unchanged.

## Related

- [AWS Systems Manager Automation](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-automation.html)
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
