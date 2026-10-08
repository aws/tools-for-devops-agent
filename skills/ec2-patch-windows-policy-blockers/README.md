# ec2-patch-windows-policy-blockers

A skill for AWS DevOps Agent that recovers a Windows Server EC2 instance whose patching is blocked by a **policy or security control** rather than the update mechanism — Group Policy disabling Windows Update, antivirus/EDR locking system files or a missing AV-compat key, BitLocker triggering recovery on a boot-critical update, the Server 2012 R2 SHA-2 signing prerequisite, or narrower blockers (execution policy, registry ACLs, DCOM, Credential Guard, scheduled task, language pack).

The non-obvious value: a GPO registry edit is **temporary** (reverts on ~90-min refresh, so the GPO is the durable fix); BitLocker must be **suspended before** a boot-critical update or the reboot demands the 48-digit recovery key; Microsoft won't offer updates without the **QualityCompat** AV-compat key on 2012 R2/2016; and 2012 R2 needs the **SHA-2 KBs** before any post-2019 update will validate.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Several paths change security controls (suspend BitLocker, disable AV real-time protection, clear GPO values) — validate in a non-production environment first, confirm recovery keys before touching BitLocker, get approval for policy changes, and re-enable protections after the window.

## When it applies
A Windows patch fails because a policy/security control is blocking it (GPO, AV/EDR, BitLocker, SHA-2 prereq, exec policy, ACLs, DCOM, Credential Guard). Supported: Windows Server 2012 R2, 2016, 2019, 2022, 2025. Instance Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"Server 2019: 0x8024002E, 'managed by your organization', NoAutoUpdate=1 — can I just set it to 0?"*
- *"Server 2016 with third-party AV returns 0 updates and 0x80070005 on WinSxS — why?"*
- *"BitLocker + pending firmware update; last patch rebooted into recovery — how to patch safely?"*

Routes to: `reference/gpo-blocks.md`, `reference/av-interference.md`, `reference/bitlocker.md`, `reference/sha2-and-misc-blockers.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
