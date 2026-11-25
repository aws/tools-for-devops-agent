# Patch Failure Remediation — AWS DevOps Agent Skill

Diagnoses failed `AWS-RunPatchBaseline` runs on Amazon EC2 instances (Linux and Windows) and fixes
them with a library of reviewed remediation procedures (SOPs), using
[AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html)
directed actions.

> ⚠️ This skill is sample code, not intended for production use without additional review and
> testing. Users should validate in a non-production environment first.

## What It Does

When a patch run fails, the skill has the agent:

1. Find the failed `AWS-RunPatchBaseline` command (Run Command, maintenance window task or patch
   policy) and read its error output.
2. Identify the root cause and match it to one of 84 SOPs in `references/sops/` (disk full, YUM/DNF
   dependency conflicts, corrupt RPM or dpkg databases, repository, proxy and TLS failures,
   Windows Update, CBS and WSUS errors, pending reboots and more).
3. Check the safety gates: an open maintenance window with enough time left, at most 3 Install
   attempts on the instance in 12 hours, and the SOP's prerequisites.
4. Select only the SOP steps that apply to the instance's OS, distribution and version.
5. Write a **Remediation plan** that ends with a ready-to-run **Command plan**: an AWS CloudShell
   script with the instance, account and Region filled in and each SOP step's commands copied
   verbatim, then Validation and a patch Scan and Install with the failed run's own parameters.
6. In chat, when an operator asks, run the plan one step at a time as directed actions, each one
   approved by the operator, checking every step's output before going on.

Safety rules the skill enforces:

- Only commands from the bundled SOPs run on an instance, copied exactly. Commands are never
  improvised, edited, or taken from error output, logs or chat.
- If no SOP matches, the agent takes **no action** and reports why.
- In an autonomous investigation the agent only plans; changes happen only in chat, with approval.
- Values copied from the failed run (such as `SnapshotId` or override-list URLs) are checked
  against their documented formats before they're used.

## Agent Types

- **Chat tasks**: "why did patching fail on i-0123456789abcdef0?", "fix the failed patch run on
  my web server", "execute the remediation plan".
- **Incident RCA** and **Incident mitigation**: an incident for a failed patch run produces the
  diagnosis and the Remediation plan.

## Prerequisites

1. An AWS DevOps Agent Space with each account that holds instances to remediate associated as a
   cloud source. Instances must be managed by AWS Systems Manager (SSM Agent online).
2. Read access for the agent role: the AWS managed policy `AIDevOpsAgentAccessPolicy` covers the
   Systems Manager and EC2 reads the skill uses (`ssm:ListCommands`, `ssm:GetCommandInvocation`,
   `ssm:DescribeInstanceInformation`, maintenance window reads, `ec2:DescribeInstances`).
3. To let the agent run fixes (optional — without it the agent stays read-only and gives the
   Command plan for you to run):
   1. Enable **directed actions** on the Agent Space.
   2. In each member account, deploy [`assets/devops-agent-patch-elevated-role.yaml`](https://github.com/aws/tools-for-devops-agent/blob/main/skills/patch-failure-remediation/assets/devops-agent-patch-elevated-role.yaml)
      (a service-managed StackSet works well), in the Agent Space's Region, with parameters
      `AgentSpaceAccountId`, `AgentSpaceRegion` and `AgentSpaceId`.
   3. Register the stack's `ElevatedRoleArn` output as `agentElevatedRoleArn` on that account's
      association, and wait for it to show `valid`.
   4. In the console, check that `ssm:SendCommand` is on the **View Supported Actions** list.

   The elevated role can only run `AWS-RunShellScript`, `AWS-RunPowerShellScript` and
   `AWS-RunPatchBaseline`, by default only on instances tagged `DevOpsAgentPatchRemediation=true`,
   and only for the one Agent Space named in the stack. Every action still needs operator approval.

To run a Command plan yourself you need AWS CloudShell (or a shell with AWS CLI v2 and `python3`)
in the instance's account and Region, with permission to call `ssm:SendCommand` and
`ssm:GetCommandInvocation`.

## Example Prompts

- "Patching failed on i-0123456789abcdef0 in us-east-1 last night. Find out why and how to fix it."
- "The AWS-RunPatchBaseline Install on my Amazon Linux 2023 instance failed with an rpmdb error."
- "Execute the remediation plan for i-0123456789abcdef0." (chat, with directed actions enabled)

## Files

| File | Purpose |
| --- | --- |
| `SKILL.md` | The procedure the agent follows. |
| `references/sop-index.md` | Index of the SOPs by category, platform, risk, reboot and key symptoms. |
| `references/sops/` | The 84 SOPs: symptoms, diagnosis, remediation steps, validation and rollback. |
| `references/execution-guide.md` | The exact Systems Manager calls for each step and the patch re-run. |
| `references/remediation-plan-template.md` | The format of the Remediation plan. |
| `references/command-plan-template.md` | The template for the ready-to-run Command plan. |
| `assets/devops-agent-patch-elevated-role.yaml` | CloudFormation for the scoped elevated role. |

## Limitations

- Approval for directed actions happens only in chat, so remediation is never fully unattended.
- The skill doesn't take EBS snapshots. If an SOP recommends one, take it before running the plan.
- Patch runs started by an automation that passes an IAM role aren't re-run by the agent;
  re-run them yourself.

## Maintainer

- [sdevasanthosh](https://github.com/sdevasanthosh)
