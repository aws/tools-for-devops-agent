# ec2-patch-windows-servicing-store

A skill for AWS DevOps Agent that recovers a Windows Server EC2 instance whose patching is blocked by a **component-servicing fault** — the family of failures rooted in the CBS/WinSxS component store, the servicing stack (SSU), pending servicing transactions, the Windows Update datastore, or a stalled feature update.

The non-obvious value: these sub-faults **masquerade as each other**. A stale servicing stack and a halted pending transaction both surface as `0x800F0831` (CBS_E_STORE_CORRUPTION), so the naive "just run `DISM /RestoreHealth`" loops for hours without converging. This skill diagnoses *which* servicing fault is present and applies the correct, ordered recovery.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Validate it in a non-production environment first, review the remediation steps and IAM permissions against your organization's policies, and confirm the behavior meets your operational requirements before using it against production instances. Several steps mutate system state (SSU install, `RestoreHealth`, `RevertPendingActions`, clearing `pending.xml`/`SessionsPending`) and require a reboot.

## When it applies
A Windows patch / Windows Update install fails with a servicing-subsystem signature, e.g.:
- `0x80073712`, `0x800F0831` (CBS_E_STORE_CORRUPTION), `0x800F081F`, `0x800F0922`, `0x80073701`
- `0x80070BC9` (SSU prerequisite), `0x8024400A` / `0x80244010` (WU datastore), `0xC1900101` (feature update)
- `DISM /ScanHealth` reports corruption or "packages are pending servicing"; updates stuck in "InstalledPendingReboot"/"Pending Install"; `DataStore.edb` oversized; `Windows.old` lingering after a failed in-place upgrade.

Supported: Windows Server 2012 R2, 2016, 2019, 2022, 2025. Instance must be Online in SSM.

## Prerequisites (IAM)
The DevOps Agent role associated with your Agent Space needs permission to inspect and remediate the target instance via SSM. Most of this is already covered by the AWS managed policy [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). The specific actions this skill drives:

- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation` — run the diagnostic/remediation PowerShell on the instance
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus` — target/verify the instance

The exact least-privilege policy is in [`automation/iam-policy.json`](automation/iam-policy.json). The instance itself must have an SSM-enabled instance profile (`AmazonSSMManagedInstanceCore`) and the SSM agent running.

## Usage
Upload the skill to your Agent Space, then use DevOps Agent chat or an investigation:

- **Chat:** *"Windows Server 2016 cumulative update keeps failing at Installing with 0x80073712; I ran DISM /RestoreHealth twice and it loops — how do I fix it?"*
- **Investigation:** start an investigation on the failing instance (or, as the eval does, provide the collected `CBS.log` / servicing-state evidence) and the skill drives the diagnosis to the correct root cause.

The skill routes to one of five references based on the detected sub-fault: `reference/pending-transactions.md`, `reference/ssu-ordering.md`, `reference/cbs-store-repair.md`, `reference/wu-datastore.md`, `reference/feature-update.md`.

## Evaluation
See `evals/` for the eval definitions and results. Functional evaluation uses bundled evidence fixtures under `evals/files/` (a `CBS.log` excerpt and a servicing-state snapshot) so the investigation scenario is self-contained and reproducible without a live broken instance.
