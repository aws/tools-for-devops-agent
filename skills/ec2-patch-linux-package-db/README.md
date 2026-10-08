# ec2-patch-linux-package-db

A skill for AWS DevOps Agent that recovers a Linux EC2 instance whose patching is blocked by a **corrupt package database or interrupted package transaction** — the family of failures rooted in the RPM database (BerkeleyDB or SQLite), the dpkg status/journal, incomplete yum/dnf/apt transactions, or RPM/DEB file conflicts.

The non-obvious value: the correct recovery depends on the **packager AND the RPM backend**. The naive `rpm --rebuilddb` is wrong on a totally corrupt AL2023 sqlite database (it leaves an empty DB); clearing dpkg journal files is different from restoring a corrupt dpkg status. This skill diagnoses which fault and packager is present and applies the correct, ordered, backup-first recovery.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Validate in a non-production environment first, review the remediation steps and IAM permissions against your organization's policies, and confirm behavior meets your operational requirements.

## When it applies
A yum/dnf/apt/zypper patch operation fails with a package-database or interrupted-transaction signature (rpmdb BDB0113, database disk image is malformed, dpkg parse error, dpkg was interrupted, file conflicts, incomplete transactions).

Supported: Amazon Linux 2, Amazon Linux 2023, RHEL 7/8/9, CentOS 7, Oracle Linux 7/8/9, SLES 12/15, Ubuntu 20.04/22.04/24.04, Debian 11/12. Instance must be Online in SSM.

## Prerequisites (IAM)
Most permissions are covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). The specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json) for the least-privilege policy.

## Usage
Upload to your Agent Space, then ask via chat or reference the scenario:
- *"Amazon Linux 2023: rpm -qa returns 0 packages after I ran rpm --rebuilddb — how do I recover?"*
- *"Ubuntu 22.04: dpkg status parse error at line 14477 — how to fix?"*
- *"rpmdb: BDB0113 on some RHEL hosts and 'database disk image is malformed' on others — how do I recover the fleet?"*

The skill routes to one of four references: `reference/rpm-db-recovery.md`, `reference/dpkg-recovery.md`, `reference/incomplete-transactions.md`, `reference/file-conflicts.md`.

## Evaluation
See `evals/` for eval definitions and results. Evals use inline evidence in chat-shaped prompts (no live broken instances required).
