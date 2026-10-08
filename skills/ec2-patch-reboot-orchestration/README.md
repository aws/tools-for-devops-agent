# ec2-patch-reboot-orchestration

A cross-platform (Linux + Windows) skill for AWS DevOps Agent that handles the **reboot lifecycle and reboot-timing races** in patching: an instance stuck NON_COMPLIANT only because patches are installed pending a reboot (`RebootOption=NoReboot`), and the "a system shutdown is in progress" race where a patch run starts while the OS is already rebooting.

The non-obvious value is knowing these are reboot-**timing** states, not patch failures: a pending-reboot instance needs a controlled reboot in an approved change window (and only if the run used `RebootIfNeeded` — never re-patch, never override a deliberate `NoReboot` policy), and a shutdown-in-progress race needs a **bounded wait** for boot then a single retry — never an indefinite retry loop and never a retry into a still-rebooting host.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. The pending-reboot path triggers a reboot — never execute it outside an approved maintenance/change window, confirm the application owner allows a restart, reboot cluster members one at a time, and review the steps and IAM against your organization's policies.

## When it applies
The situation is about the reboot around a patch, not a patch-content failure. Supported: all AMS-supported Linux distros and Windows Server 2012 R2–2025. If patches are genuinely Missing or Failed, use the matching root-cause skill.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ssm:DescribeInstancePatchStates`, `ssm:DescribeInstancePatches`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`, `ec2:RebootInstances`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"Instance is NON_COMPLIANT with InstalledPendingRebootCount=3 but Failed=0/Missing=0 and SSM.2 is open — is this a patch failure?"*
- *"Patch failed immediately with 'A system shutdown is in progress' and 0xffffffff — should I just retry?"*
- *"Can I reboot this instance to clear pending-reboot compliance?"*

Routes to: `reference/pending-reboot.md`, `reference/reboot-race.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
