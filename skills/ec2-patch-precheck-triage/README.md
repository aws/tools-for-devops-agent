# ec2-patch-precheck-triage

A cross-platform (Linux + Windows) skill for AWS DevOps Agent that triages the patch **operation and workflow** around a maintenance window: pre-patch prerequisite-check failures, deciding whether a bare failure is a transient cosmetic scan error or a genuine one, handling SSM-unreachable instances that can't be patched at all, and patch runs that time out or exceed the window.

The non-obvious value is triage **order and gates**: fix connectivity and repo health before other prechecks (dependent checks are skipped or auto-resolve); only auto-close a failure once a fresh scan proves `FailedCount=0` and `MissingCount=0`; an SSM-unreachable instance has **no remote path** (control-plane checks + customer escalation only — don't deregister hybrid ghosts); and a timeout is window-sizing/bandwidth, not a code bug.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Some paths change instance state or resolve OpsItems — validate in a non-production environment first, never auto-close a failure without the compliance gate, and review the steps and IAM against your organization's policies.

## When it applies
The question is about the patch operation/workflow rather than a specific in-OS root cause. Supported: all AMS-supported Linux distros and Windows Server 2012 R2–2025. If a specific package-manager / store / connectivity / policy error is named, use the matching platform skill instead.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ssm:DescribeInstancePatchStates`, `ssm:DescribeInstancePatches`, `ssm:GetOpsItem`, `ssm:UpdateOpsItem`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`, `iam:ListAttachedRolePolicies`, `iam:GetInstanceProfile`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"Prechecks failed with repo, dry-run, and S3 endpoint all unhealthy — which do I fix first?"*
- *"PatchInstallFailure OpsItem but the instance is already compliant — can I auto-close it?"*
- *"Instance is ConnectionLost in SSM — can you restart the agent and patch it?"*

Routes to: `reference/precheck-failures.md`, `reference/transient-vs-genuine.md`, `reference/ssm-unreachable.md`, `reference/timeout-and-window.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
