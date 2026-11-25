# SOP-019: Resolve NoReboot Pending-Reboot Non-Compliance

| Field | Value |
|-------|-------|
| ID | SOP-019 |
| Category | pending_reboot_noncompliance |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows, Linux |
| Distributions | All supported |
| Requires Reboot | **Yes** (controlled) |
| Estimated Duration | 300 seconds (excludes reboot wait) |
| Last Validated | 2026-06-10 |

## Symptoms

- Instance is `NON_COMPLIANT` with `InstalledPendingRebootCount > 0`
- Patches installed successfully but the patch operation used `RebootOption=NoReboot`
- Security Hub control **SSM.2** is in `Open`/`FAILED` state for the instance ("should have patch compliance status COMPLIANT after a patch installation")
- `FailedCount=0` and `MissingCount=0`, yet the instance still reports non-compliant
- Patches show state `InstalledPendingReboot` in `describe-instance-patches`

## Root Cause

The maintenance window applies patches with `RebootOption=NoReboot` (common in environments that control reboots separately to avoid unplanned downtime). Patches that require a restart are installed but remain in `InstalledPendingReboot` state until the OS is rebooted. Until that reboot occurs the instance is reported NON_COMPLIANT and the associated Security Hub SSM.2 finding stays open.

This is **not a patch failure** — it is a deferred-reboot policy side effect. The remediation is a controlled reboot in an approved window, not a re-patch.

## Related Failure Patterns

- SOP-018 (Transient Post-Scan Auto-Close) — the Diagnosis gate routes pending-reboot instances here rather than auto-closing them as transient
- SOP-008 (grub2 Update) — Linux kernel/bootloader updates are a frequent source of reboot-required state

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- **A change/approval window exists** for the reboot (these are GxP/production instances — reboots must be scheduled and approved)
- Application owner has confirmed the instance can tolerate a restart
- Operator has permission to trigger a controlled reboot within an approved change window

> **Safety note:** This SOP causes a reboot. Do NOT execute outside an approved maintenance/change window. Confirm cluster/quorum members are rebooted one at a time.

## Diagnosis

Confirm the non-compliance is purely reboot-pending and quantify it:

```bash
# Confirm pending-reboot is the only issue
aws ssm describe-instance-patch-states --instance-ids <instance-id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount,LastOp:Operation}" --output table

# List the specific patches awaiting reboot
aws ssm describe-instance-patches --instance-id <instance-id> --region <region> \
  --filters Key=State,Values=InstalledPendingReboot \
  --query "Patches[].{KB:KBId,Title:Title}" --output table
```

**Decision rule:**
- `Failed=0`, `Missing=0`, `PendingReboot>0` → proceed (this SOP applies).
- `Missing>0` or `Failed>0` → different problem; route to SOP-001/003/017/etc. first, then return here.

## Remediation Steps

### Step 1: Verify reboot readiness (in-guest pre-checks)

Windows:

```powershell
# Confirm a reboot is actually pending and capture uptime
$pending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
"RebootPending=$pending"
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime
```

Linux:

```bash
needs-restarting -r 2>/dev/null; echo "needs-restarting rc=$?"; [ -f /var/run/reboot-required ] && echo "reboot-required flag present"; uptime
```

Expected output: confirmation a reboot is pending.
On failure (no reboot actually pending): re-scan (SOP-018 Step 1) — state may already be clearing.

### Step 2: Perform a controlled reboot within the approved window

**Decision gate (agent MUST confirm before running any command below):**

`RebootOption` is an SSM patch-operation *input*, not something readable on the host. The agent MUST inspect the failed execution's input parameters and only proceed when **`RebootOption=RebootIfNeeded`**. If `RebootOption=NoReboot` (or the value cannot be confirmed), make **no disruptive change** — the reboot must instead be scheduled through an approved change window, and this SOP stops here.

Only when a reboot is genuinely pending (confirmed in Step 1) **AND** `RebootOption=RebootIfNeeded` is confirmed from the execution input, issue the controlled reboot:

```bash
# Guarded reboot: only reboots if a pending-reboot marker is present on the host.
# REBOOT_OPTION MUST be injected by the orchestrator from the failed SSM execution
# input; it is NOT discoverable on the host. Fail CLOSED when it is missing or is
# anything other than RebootIfNeeded, so an automated agent never reboots a NoReboot run.
if [ "${REBOOT_OPTION:-}" != "RebootIfNeeded" ]; then
  echo "RebootOption not confirmed as RebootIfNeeded (REBOOT_OPTION='${REBOOT_OPTION:-unset}') - making no disruptive change" >&2
  exit 0
fi
NEEDS_REBOOT=0
[ -f /var/run/reboot-required ] && NEEDS_REBOOT=1
needs-restarting -r >/dev/null 2>&1; [ $? -eq 1 ] && NEEDS_REBOOT=1   # needs-restarting -r exits 1 when a reboot is required
if [ "$NEEDS_REBOOT" -eq 1 ]; then
  shutdown -r +1 "Patch remediation reboot"; echo "Controlled reboot scheduled (+1 min)"
else
  echo "No pending-reboot marker on host - making no disruptive change"
fi
```

Expected output: "Controlled reboot scheduled (+1 min)" when a reboot is pending and permitted; otherwise "No pending-reboot marker on host - making no disruptive change".
On failure (no reboot pending): re-scan (SOP-018 Step 1) — state may already be clearing.


## Validation

```bash
aws ssm describe-instance-patch-states --instance-ids <instance-id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount}" --output table
```

Expected: `PendingReboot=0`, `Failed=0`, `Missing=0`. The Security Hub SSM.2 finding should auto-resolve on its next evaluation.



## Escalation

If pending-reboot persists after a successful reboot:
- The update may be failing to finalize on boot (check `CBS.log` on Windows, `dnf history` on Linux)
- Capture the boot event logs and the list of `InstalledPendingReboot` patches
- Escalate to your patching team with instance ID, region, and reboot CommandId
