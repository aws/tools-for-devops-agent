# AWS Backup Coverage Review — Custom Agent

## Purpose

This custom agent determines which backup-eligible resources in an AWS account are actually recoverable and which only appear to be, across all enabled Regions. It resolves every eligible resource to a coverage state, evaluates 23 checks across service enablement, coverage, plan quality, vault posture, and coverage integrity, and produces a rated report artifact with prioritized remediation.

## Key Capabilities

- Builds an independent inventory of backup-eligible resources and diffs it against what AWS Backup is actually protecting, so gaps surface without requiring AWS Config or AWS Backup Audit Manager to be set up first
- Distinguishes backup plan *membership* from actual *protection*, and separates resources that are unprotected, stale, blocked by a Region-level opt-in, selected but never backed up, or orphaned recovery points for deleted resources
- Flags backup selections that name resources by literal ARN, including selections pointing at resources that no longer exist
- Evaluates plan frequency and retention, cross-Region and cross-account copies, vault encryption, Vault Lock, access policies, air-gapped vaults, and failure notifications
- Checks restore testing coverage and whether AWS Backup Audit Manager report plans and frameworks are configured per Region, so a decline in coverage would be noticed
- Never lets a permissions gap masquerade as a coverage gap: unverifiable checks are excluded from the denominator and cap the rating rather than lowering it
- Produces a persisted Markdown artifact for sharing with stakeholders

## Prerequisites

- An AWS DevOps Agent space
- IAM permissions for AWS Backup read APIs (`backup:List*`, `backup:Describe*`, `backup:GetBackupPlan`, `backup:GetBackupSelection`, `backup:GetSupportedResourceTypes`) and resource inventory read APIs across EC2, RDS, DynamoDB, EFS, FSx, S3, Redshift, Timestream, Storage Gateway, CloudFormation and EKS. Most are covered by `AIDevOpsAgentAccessPolicy`; the exact delta and a deployable CloudFormation policy are documented in the skill README
- The [aws-backup-coverage-review skill](../../skills/aws-backup-coverage-review/) uploaded to your Agent Space. Important note: for the skill to be used by the custom agent, choose "All agents" in the "Agent Type" field when importing the skill, even though the skill's README instructs to choose specific agent types

## Limitations

- Single account. Organization-wide review via a delegated administrator account is not supported.
- The coverage percentage is indicative rather than audited. Per-resource states are authoritative — a named ARN reported as unprotected is a verified fact — but account-wide totals can drift on bulk resource types such as S3 buckets and CloudFormation stacks. Treat the Coverage Matrix as the record of record.
- Read-only. The agent reports the exact change needed for each gap but never applies it, including when asked directly.

## Creating the Agent

1. In the DevOps Agent web app, go to the "Agents" menu (on the bottom left pane)
2. Click "Create agent" (on the right side), then in the menu that appears, click "Form" (the left-most option)
3. In the "Name" field, use "aws-backup-coverage-review"
4. Copy the content of the "SYSTEM_PROMPT.md" file from this directory, and paste it into the "System prompt" field
5. In the "Skills" drop-down list, select the "aws-backup-coverage-review" skill, and click "Create agent"
6. Now add the `use_aws` tool — in the new custom agent's window, click "Edit"
7. In the window that appears, select "Chat". A new chat will start on the left side. Wait for DevOps Agent to finish thinking, and it will ask what you would like to change
8. Type "Add the `use_aws` tool to this custom agent". Once the chat finishes, verify that `use_aws` is shown under "Tools" on the custom agent's page

## Executing the Agent

You can execute the custom agent on-demand from the custom agent page, on a schedule, or using chat. Follow the [Executing custom agents guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/custom-agents-executing-custom-agents.html) for more information. You can also run it with a custom prompt — for example asking it to review only specific Regions, or to focus on vault posture.

Once finished, the artifact is persisted on the **Artifacts** page in the DevOps Agent web app.

Running it on a schedule is the intended use for coverage tracking: coverage is a point-in-time state, and a scheduled review turns "what isn't backed up?" into a question that gets answered continuously rather than only when someone remembers to ask.

## Related

- [aws-backup-coverage-review skill](../../skills/aws-backup-coverage-review/) — domain knowledge, check definitions, thresholds, and report format
- [AWS DevOps Agent custom agents documentation](https://docs.aws.amazon.com/devopsagent/latest/userguide/working-with-devops-agent-custom-agents-index.html)

## Non-production disclaimer

> ⚠️ This custom agent is sample code, not intended for production use without additional
> review and testing. Users should validate in a non-production environment first.
