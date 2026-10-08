# ec2-patch-linux-host-preconditions

A skill for AWS DevOps Agent that recovers a Linux EC2 instance whose patching is blocked by a **host-level precondition** rather than the package manager itself — a read-only-remounted filesystem, inode exhaustion (disk "full" with free space showing), OOM kills during patching, SELinux/AppArmor denials in package scriptlets, corrupt NSS crypto library (`libfreeblpriv3.so`) that segfaults yum itself, locale/encoding and corrupt-Python-stdlib errors, PAM/PBIS misconfig, and systemd service-restart failures.

The non-obvious value: inode exhaustion needs `df -i` (not `df -h`); a read-only FS from I/O errors must **not** just be remounted (it's a volume problem); and NSS corruption must be repaired with `rpm -ivh --force` because yum can't self-heal (it depends on the corrupt library).

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Some paths involve EBS volume operations and filesystem repair — validate in a non-production environment first and review the steps and IAM against your organization's policies.

## When it applies
A patch operation fails because of a host/filesystem/runtime condition beneath the package manager. Supported: Amazon Linux 2/2023, RHEL 7/8/9, Oracle Linux 7/8/9, CentOS 7, SLES 15, Ubuntu 20.04/22.04/24.04. Instance Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`, `ec2:DescribeVolumeStatus`, `ec2:DescribeVolumes` (for the read-only-FS / EBS-impairment path)

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"AL2: 'No space left on device' but df -h shows 55% used — what's wrong?"*
- *"RHEL 8: /var read-only with EXT4-fs errors and I/O errors in dmesg — just remount rw?"*
- *"AL2: every yum command segfaults on libfreeblpriv3.so — how to recover?"*

Routes to: `reference/filesystem-integrity.md`, `reference/space-and-memory.md`, `reference/runtime-library-corruption.md`, `reference/security-and-services.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
