# ec2-patch-windows-update-service

A skill for AWS DevOps Agent that recovers a Windows Server EC2 instance whose patching is blocked by an **update service or runtime fault** (distinct from CBS component-store corruption): a hung/crashed Windows Update / BITS / TrustedInstaller service, a corrupt Windows Installer (MSI) service, the Windows Update service set to **Disabled**, and the AWS-specific **AWSSDK.Core assembly missing from the GAC** (which breaks `AWS-RunPatchBaseline` itself).

The non-obvious value: a Disabled service can't be started by SSM until re-enabled (unlike Stopped/Manual); a hung WUA needs a service reset + SoftwareDistribution/DataStore.edb rebuild; and a GAC-missing AWSSDK.Core throws a .NET type-load error that isn't obviously a "patch" problem.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Validate in a non-production environment first and review the steps and IAM against your organization's policies. Take an EBS snapshot before the GAC re-registration path.

## When it applies
A Windows patch scan/install fails because a required service (wuauserv, BITS, TrustedInstaller, msiserver) is hung/crashed/disabled, or the .NET runtime `AWS-RunPatchBaseline` needs is broken. Supported: Windows Server 2012 R2, 2016, 2019, 2022, 2025. Instance Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"Server 2019: AWS-RunPatchBaseline fails with 0x80070422 and wuauserv StartType is Disabled — why can't SSM start it?"*
- *"Server 2016: patch scan never returns, TiWorker pegged, DataStore.edb over 1GB — how to fix?"*
- *"AWS-RunPatchBaseline throws 'Could not load type ... AWSSDK.Core' — what's wrong?"*

Routes to: `reference/service-startup-state.md`, `reference/wua-bits-hang.md`, `reference/msi-service.md`, `reference/awssdk-gac.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
