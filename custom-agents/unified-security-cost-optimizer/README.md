# Unified Security Cost Optimizer - Custom Agent

## Purpose

This custom agent helps customers reduce spend on AWS security and governance services — Amazon CloudTrail, AWS Config, and Amazon GuardDuty — without weakening their security posture. It routes each service to its dedicated cost-optimization skill, runs entirely read-only, and produces a consolidated, severity-ranked cost-optimization report with estimated savings and explicit cost-vs-risk tradeoffs. It is designed for FinOps and security teams who want to find and prioritize security-service savings across an account or organization in one pass.

## Key Capabilities

- Reviews Amazon CloudTrail, AWS Config, and Amazon GuardDuty cost in a single run (or any subset the user selects)
- Detects the highest-impact drivers per service: duplicate CloudTrail management-event trails and broad data events; over-broad AWS Config recording, continuous-vs-daily frequency mismatches, and duplicate global-resource recording; and high-cost GuardDuty protection plans including the Runtime Monitoring / VPC Flow Log charge offset and free-trial cost projection
- Attributes spend using Cost Explorer usage types and each service's CloudWatch usage metrics, and sizes each opportunity with an estimated monthly saving
- Frames every recommendation as a cost-vs-risk tradeoff — never reducing coverage below compliance or security requirements
- Highlights cross-service themes (e.g. shared high-volume S3 activity touching CloudTrail data events, Config delivery buckets, and GuardDuty S3 Protection)
- Produces a consolidated Markdown report artifact for sharing with stakeholders

## Prerequisites

- An AWS DevOps Agent space with the target AWS account configured as a cloud source
- **No additional IAM permissions are required.** Every read-only API the three skills use (CloudTrail, Config, GuardDuty, CloudWatch, S3, Organizations) plus `ce:GetCostAndUsage` for dollar sizing is already covered by the AWS managed [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AIDevOpsAgentAccessPolicy.html). The only optional extra is the config-cost-optimization Athena CI-driver path (`EnableConfigAthenaCiAnalysis` in [`cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/cloudformation/devops-agent-skill-policies/devops-agent-skill-policies.yaml)), which is off by default; without it the Config skill falls back to a resource-count signal.
- The [cloudtrail-cost-optimization skill](../../skills/cloudtrail-cost-optimization/) uploaded to your Agent Space. Important: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even though the skill's README suggests specific agent types
- The [config-cost-optimization skill](../../skills/config-cost-optimization/) uploaded to your Agent Space. Important: choose "All agents" in the "Agent Type" field when importing the skill
- The [guardduty-cost-optimization skill](../../skills/guardduty-cost-optimization/) uploaded to your Agent Space. Important: choose "All agents" in the "Agent Type" field when importing the skill

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" menu (on the bottom left pane)
2. Click "Create agent" (on the right side), then in the menu that pops up, click "Form" (the left-most option)
3. In the "Name" field, use "unified-security-cost-optimizer"
4. Copy the content of the "SYSTEM_PROMPT.md" file from this directory, and paste it into the "System prompt" field in the custom agent creation form
5. In the "Skills" drop-down list, select the "cloudtrail-cost-optimization", "config-cost-optimization", and "guardduty-cost-optimization" skills, and click "Create agent"
6. Now add the `use_aws` tool — in the new custom agent's window, click "Edit"
7. In the window that pops up, select "Chat". A new chat starts on the left side. Wait for DevOps Agent to finish thinking; it will ask what you'd like to change
8. Type "Add the use_aws tool to this custom agent". Once the chat finishes, verify on the custom agent's page that `use_aws` is shown under "Tools"

## Executing the Agent

You can execute the custom agent on-demand from the custom agent page, on a schedule, or using chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also run it with a custom prompt — for example, ask it to review only GuardDuty, focus on a specific account/Region, or project GuardDuty free-trial cost.

Example prompts:

- *"Optimize the cost of my security services (CloudTrail, Config, GuardDuty) for account 123456789012."*
- *"Where am I overspending on CloudTrail and Config across my organization?"*
- *"Review only GuardDuty cost and project my spend after the free trial."*

Once finished, the artifact is persisted on the **Artifacts** page in the DevOps Agent web app. Single-service runs use that skill's artifact name (e.g. `guardduty-cost-optimization-<account-id>-<YYYY-MM-DD>.md`); multi-service runs produce a consolidated `security-cost-optimization-<account-id>-<YYYY-MM-DD>.md`.

## Related

- [cloudtrail-cost-optimization skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/cloudtrail-cost-optimization) - Domain knowledge for Amazon CloudTrail cost optimization

- [config-cost-optimization skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/config-cost-optimization) - Domain knowledge for AWS Config cost optimization

- [guardduty-cost-optimization skill](https://github.com/aws/tools-for-devops-agent/tree/main/skills/guardduty-cost-optimization) - Domain knowledge for Amazon GuardDuty cost optimization

- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)
