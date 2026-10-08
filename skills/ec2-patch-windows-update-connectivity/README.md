# ec2-patch-windows-update-connectivity

A skill for AWS DevOps Agent that recovers a Windows Server EC2 instance whose patching fails because it **cannot reach or authenticate to the update source** — WSUS/Microsoft Update endpoint unreachable, proxy authentication failures in the SYSTEM context, TLS 1.2 not enabled, outdated/missing root certificates, firewall/WPAD issues, or a wrong WUServer GPO.

The non-obvious value: a WSUS-configured instance (`UseWUServer=1`) that can't reach WSUS is an infrastructure problem to escalate (not an OS fix, don't loop-retry); SSM patches run as **SYSTEM** which has no cached proxy credentials (so a proxy needs a WinHTTP config + WU bypass); and a cert error is often a stale root store or a wrong clock, not an unreachable endpoint.

## ⚠️ Non-Production Disclaimer
This is **sample code**, not intended for production use without additional review and testing. Some paths change the update source (`UseWUServer`) or proxy config — validate in a non-production environment first, get approval for source changes, and review the steps and IAM against your organization's policies.

## When it applies
A Windows patch scan/install fails reaching or authenticating to WSUS or Microsoft Update (timeout, TLS/cert error, proxy 407). Supported: Windows Server 2012 R2, 2016, 2019, 2022, 2025. Instance Online in SSM.

## Prerequisites (IAM)
Most is covered by [`AIDevOpsAgentAccessPolicy`](https://docs.aws.amazon.com/devopsagent/latest/userguide/aws-devops-agent-security-devops-agent-iam-permissions.html). Specific actions:
- `ssm:SendCommand`, `ssm:GetCommandInvocation`, `ssm:ListCommandInvocations`, `ssm:DescribeInstanceInformation`
- `ec2:DescribeInstances`, `ec2:DescribeInstanceStatus`

See [`automation/iam-policy.json`](automation/iam-policy.json).

## Usage
Ask via chat, e.g.:
- *"Server 2019: 0x8024401C, 'Windows Update is not reachable', UseWUServer=1, WSUS host unreachable — how to handle?"*
- *"AWS-RunPatchBaseline gets HTTP 407 but interactive Windows Update works — why?"*
- *"Server 2016 stopped for 2 months now fails scan with 0x80072F8F — cert problem?"*

Routes to: `reference/wsus-routing.md`, `reference/proxy-system-context.md`, `reference/tls-settings.md`, `reference/root-certs-and-clock.md`.

## Evaluation
See `evals/` for eval definitions and results (chat-shaped prompts with inline evidence).
