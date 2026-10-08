# ec2-patch-linux-kernel-boot

A skill for AWS DevOps Agent that recovers a Linux EC2 instance whose **kernel patching fails or leaves it unbootable** — a full `/boot` partition blocking the new kernel, GRUB2/BLS regeneration failures, kernel headers / DKMS rebuild failures for third-party modules (ENA, EFA, NVIDIA, CrowdStrike), and Oracle Linux UEK-vs-RHCK dual-kernel conflicts.

The non-obvious value: `/boot` is a separate small partition that fills after a few kernels (so overall disk looks fine); old-kernel pruning must **preserve the running kernel**; DKMS needs the headers matching the *running* kernel; and both UEK and RHCK repos enabled produces an unsolvable kernel transaction.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. **This is a high-risk domain** — a wrong GRUB config or removing the running kernel can render an instance unbootable. Always take an AMI/EBS snapshot before kernel work, validate the bootloader config before rebooting, and validate in a non-production environment first.

## When it applies
A kernel patch fails to install, fails to update the bootloader, or leaves the instance unable to boot the new kernel. Supported: Amazon Linux 2/2023, RHEL 7/8/9, Oracle Linux 8/9, CentOS 7, SLES 12/15, Ubuntu 20.04/22.04/24.04. Instance Online in SSM (or reachable via serial console/rescue if unbootable).

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"RHEL 8: kernel RPM fails with 'No space left on device' but only /boot is 100% — how to fix?"*
- *"Oracle Linux 8: 'kernel-uek conflicts with kernel' on patching — how to resolve?"*
- *"Ubuntu 22.04: NVIDIA DKMS build fails after kernel update, headers missing — how to fix?"*

Routes to: `reference/boot-space.md`, `reference/grub-and-bls.md`, `reference/kernel-headers-dkms.md`, `reference/uek-rhck-conflict.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
