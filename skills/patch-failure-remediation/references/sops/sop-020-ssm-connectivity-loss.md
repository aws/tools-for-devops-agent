# SOP-020: Triage SSM Connectivity Loss / Unreachable Instances Before Patching

| Field | Value |
|-------|-------|
| ID | SOP-020 |
| Category | ssm_connectivity_loss |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows, Linux, Hybrid (mi-) |
| Distributions | All supported |
| Requires Reboot | No |
| Estimated Duration | 120 seconds (control-plane only) |
| Last Validated | 2026-06-15 |

## Symptoms

- SSM reports `PingStatus: ConnectionLost` or `Inactive` for an instance
- Patch command never starts / times out with no plugin output ("instance not reachable")
- An endpoint-reachability check or automation fails on the instance
- Maintenance-window patch run skips or fails targets that are offline
- Hybrid-activation (`mi-`) managed instances with a stale `LastPingDateTime` (days/weeks/months old)
- Security Hub / patch compliance shows the instance perpetually non-compliant because it is never scanned

## Root Cause

The instance cannot maintain its connection to the SSM service, so Patch Manager can neither scan nor patch it. Distinguish two classes:

**Class A — EC2 instance lost connectivity:**
- SSM Agent stopped/crashed or is an old version
- Instance is stopped/terminated/impaired
- IAM instance profile missing/changed (lost `ssm:UpdateInstanceInformation` permission)
- VPC endpoint / NAT / security-group change blocked outbound 443 to `ssm`, `ssmmessages`, `ec2messages`
- Network/route change isolated the subnet

**Class B — Hybrid (`mi-`) activation is dead/abandoned:**
- On-prem/other-cloud host decommissioned but the managed-instance registration was never deregistered
- Activation expired or the host's agent stopped permanently
- These linger as `ConnectionLost` forever and **inflate the non-compliant count with un-patchable ghosts**

**Important constraint:** SSM is the **only** channel through which Patch Manager operates and through which this triage runs. If SSM is unreachable, there is **no remote path into the instance** (no Run Command, no Session Manager). Triage is therefore limited to **control-plane checks** (IAM, EC2 state, network config) plus **documentation and escalation to the customer** — the in-guest agent must be restored by the customer/instance owner.

## Related Failure Patterns

- SOP-003 (Network Unreachable) — that SOP assumes SSM **is** reachable and fixes repo connectivity; this SOP handles the case where SSM itself is unreachable (prerequisite layer)
- SOP-018 (Transient Post-Scan Auto-Close) — do NOT auto-close compliance for an unreachable instance; route here instead

## Prerequisites

- Operator has read access to SSM, EC2, and IAM describe APIs (control-plane)
- No assumption of any in-guest access — if SSM is down, the instance cannot be reached remotely

## Diagnosis

Enumerate all unreachable instances and classify EC2 vs hybrid:

```bash
# All non-Online managed instances with last-ping age
aws ssm describe-instance-information --region <region> \
  --query "InstanceInformationList[?PingStatus!='Online'].{Id:InstanceId,Type:ResourceType,Ping:PingStatus,LastPing:LastPingDateTime,Agent:AgentVersion,Platform:PlatformName}" \
  --output table
```

For an EC2 instance (Class A), confirm its state and instance profile from the control plane:

```bash
aws ec2 describe-instances --instance-ids <instance-id> --region <region> \
  --query "Reservations[].Instances[].{State:State.Name,Profile:IamInstanceProfile.Arn,Subnet:SubnetId}" --output table
```

**Decision rule:**
- `PingStatus != Online` → the instance is unreachable and **cannot be patched or troubleshot via SSM** → **Step 1** (document + escalate) and **Step 3** (exclude from the current run).
- Run **Step 2** in parallel — a missing/incorrect IAM instance profile is the one cause fixable from the control plane without in-guest access.
- `ResourceType=ManagedInstance` (`mi-`) with a stale `LastPingDateTime` (weeks/months) → likely a dead/abandoned activation → still **Step 1 + Step 3** (flag to the customer; do not deregister).

## Remediation Steps

### Step 1: Document instance details and escalate to the customer

SSM is the only path to the instance; if it is not Online, the agent cannot be restarted remotely. Capture the facts and escalate to the customer/instance owner to investigate and restore the SSM agent on their side.

Record from Diagnosis: `InstanceId`, region, `PingStatus`, `LastPingDateTime`, `AgentVersion`, platform, EC2 `State`, subnet, and instance-profile ARN.

```bash
aws ssm describe-instance-information --region <region> \
  --filters Key=InstanceIds,Values=<instance-id> \
  --query "InstanceInformationList[].{Id:InstanceId,Ping:PingStatus,LastPing:LastPingDateTime,Agent:AgentVersion,Platform:PlatformName}" --output table
```

Escalate to the customer with this evidence (the agent must be brought back online by them since it is unreachable from AWS).

### Step 2: Verify the IAM instance profile / role (control-plane; flag missing permission)

This is the one cause addressable without in-guest access. Confirm the instance has an instance profile and that its role carries SSM managed-instance permissions; **call out any missing permission**.

```bash
# Instance profile attached?
aws ec2 describe-instances --instance-ids <instance-id> --region <region> \
  --query "Reservations[].Instances[].IamInstanceProfile.Arn" --output text
# Inspect the role's attached policies (extract <role> from the instance-profile)
aws iam list-attached-role-policies --role-name <role> \
  --query "AttachedPolicies[].PolicyName" --output text
```

Expected: an instance profile is present and the role includes `AmazonSSMManagedInstanceCore` (or an equivalent policy granting `ssm:UpdateInstanceInformation`, `ssmmessages:*`, `ec2messages:*`).
If a required policy is **missing** → report it to the customer to attach (this can restore connectivity without in-guest access). If the profile is present and correct, the cause is in-guest/network → Step 1 escalation stands.

### Step 3: Exclude the unreachable instance from the current patch run (do not let it fail the window)

Remove the instance from the current patch list / maintenance-window target set so it is tracked as **excluded**, not counted as a hard patch failure. Record the list from Diagnosis and notify the owner; re-include once connectivity is restored. Do **not** deregister the managed instance.

## Validation

```bash
# Once the customer restores the agent, confirm the instance returns Online
aws ssm describe-instance-information --region <region> \
  --filters Key=InstanceIds,Values=<instance-id> \
  --query "InstanceInformationList[].{Id:InstanceId,Ping:PingStatus,LastPing:LastPingDateTime}" --output table
```

Expected: `PingStatus=Online`, after which the instance can be re-included in the patch run.

## Prevention

- Add a **pre-patch connectivity pre-flight**: list `PingStatus!=Online` targets and exclude+alert before the install task runs, so the window does not report false failures.
- Implement a **stale hybrid-activation sweep**: flag `mi-` instances with `LastPingDateTime` older than N days for **customer review** (the customer decides on cleanup).
- Alarm on EC2 instances transitioning to `ConnectionLost` so the agent/IAM/network cause is fixed before the next patch cycle.
- Ensure the SSM Agent auto-updates (State Manager association) to avoid version-drift disconnects.

## Escalation

If the instance cannot be brought Online:
- Confirm the instance profile, SG egress (443), VPC endpoints (`ssm`/`ssmmessages`/`ec2messages`), NAT/route table.
- If a **CloudWatch Logs group** is configured for the SSM agent, search it by instance id for the agent log (the instance cannot be accessed directly while SSM is down) to find the disconnect cause.
