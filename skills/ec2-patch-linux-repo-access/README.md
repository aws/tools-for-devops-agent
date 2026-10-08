# ec2-patch-linux-repo-access

A skill for AWS DevOps Agent that recovers a Linux EC2 instance whose patching is blocked by a **repository access or authentication failure** — where the package database is fine but the instance cannot reach, authenticate to, or validate its repositories: RHUI client-certificate expiry, lapsed subscription-manager/SUSE registration, Oracle Linux yum/ULN access, expired repo TLS certificates, rotated/missing GPG keys, proxy misconfiguration, stale metadata, or NTP/time-skew.

The non-obvious value: the correct fix depends on the auth mechanism. RHUI certs are **region-specific** and reinstalled from a regional S3 bucket; a "GPG check FAILED" on RHUI repos is often really an expired client cert; and an "SSL certificate has expired" error is frequently a wrong system clock, not an actual expired cert.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Validate in a non-production environment first and review the steps and IAM against your organization's policies.

## When it applies
A yum/dnf/apt/zypper patch operation fails on repository metadata, TLS cert, GPG, or subscription/RHUI access. Supported: Amazon Linux 2/2023, RHEL 8/9, Oracle Linux 8/9, CentOS 7, SLES 12/15, Ubuntu 20.04/22.04/24.04. Instance must be Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"RHEL 9 PAYG in us-west-2 (AMI copied from us-east-1) fails RHUI patching with SSL peer certificate not OK — how do I fix it?"*
- *"GPG check FAILED on rhel-8-baseos-rhui-rpms even after importing keys — what else?"*
- *"AL2 instance stopped for months now shows 'certificate has expired' on every repo — why?"*

Routes to: `reference/rhui-certs.md`, `reference/subscription-repo-config.md`, `reference/gpg-and-tls.md`, `reference/connectivity-and-cache.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence; no live broken instances required).
