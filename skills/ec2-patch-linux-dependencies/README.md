# ec2-patch-linux-dependencies

A skill for AWS DevOps Agent that resolves a Linux EC2 **patch failure caused by package dependency conflicts** — where the package DB is intact and repos are reachable, but the transaction cannot solve: yum/dnf depsolve conflicts, DNF module-stream (modular filtering) problems on RHEL 8/9, multilib (i686 vs x86_64) protected-version conflicts, APT broken/unmet dependencies and held-back packages, versionlock/pinning blocking security updates, and third-party-repo version clashes.

The non-obvious value: the correct lever depends on the conflict type. Modular filtering is a **deliberate** exclusion needing `dnf module reset`/`switch-to` (not a forceable dependency); multilib needs a matched-version `distro-sync`; an APT "kept back" package is usually a hold/pin, not a real conflict — so a blind `install`/`--nodeps` makes it worse.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Validate in a non-production environment first and review the steps and IAM against your organization's policies. Some escalation paths (`--allowerasing`, `dist-upgrade`) can remove packages — review the removal list before running in production.

## When it applies
A yum/dnf/apt patch transaction fails to *solve* (dependency, module-stream, multilib, or pinning). Supported: Amazon Linux 2/2023, RHEL 8/9, Oracle Linux 8/9, CentOS 7, Ubuntu 20.04/22.04/24.04, Debian 11/12. Instance must be Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"RHEL 8: nodejs security update is 'filtered out by modular filtering' with nodejs:14 enabled — how to apply it?"*
- *"AL2: 'Protected multilib versions: glibc ... x86_64 != i686' — how to resolve?"*
- *"Ubuntu 22.04: security packages 'kept back' with no dependency error — why?"*

Routes to: `reference/module-streams.md`, `reference/multilib-conflicts.md`, `reference/apt-dependencies.md`, `reference/rpm-depsolve.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
