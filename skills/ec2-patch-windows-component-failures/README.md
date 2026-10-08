# ec2-patch-windows-component-failures

A skill for AWS DevOps Agent that recovers a Windows Server EC2 instance where the update mechanism works but a **specific component** (or the host's **role**) makes one patch fail — a .NET Framework update, a Windows Update driver conflicting with the AWS ENA/NVMe/PV drivers, a stalled feature update / in-place upgrade, a language-pack mismatch, a corrupt profile, or a failover-cluster node that can't reboot without losing quorum.

The non-obvious value: a WU driver over an AWS driver should be **excluded from WU** (not reinstalled generically, and recovered via Serial Console); .NET is an **OS component** repaired via DISM; a feature update stuck between builds blocks the LCU until flags/staging are cleared; and a cluster node must be **drained and suspended before any reboot** or quorum is lost.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Several paths are high-risk (driver changes, cluster drain/suspend, removing upgrade staging) — validate in a non-production environment first, confirm cluster health and recovery access, and coordinate with DBAs/cluster admins before draining a node.

## When it applies
Most patches install but one component fails, or the host's role blocks the reboot. Supported: Windows Server 2012 R2, 2016, 2019, 2022, 2025 (feature-update and driver paths are 2016+/EC2-specific). Instance Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"After a driver patch, Server 2019 lost network and ENA shows a yellow bang — how to fix and prevent it?"*
- *"Every cycle succeeds except the .NET update (0x80070643) — should I reinstall .NET?"*
- *"Failover cluster node (SQL AlwaysOn) blocks the patch reboot with 0x80070426 — how to patch safely?"*

Routes to: `reference/driver-conflicts.md`, `reference/dotnet-repair.md`, `reference/feature-update-limbo.md`, `reference/cluster-and-misc.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
