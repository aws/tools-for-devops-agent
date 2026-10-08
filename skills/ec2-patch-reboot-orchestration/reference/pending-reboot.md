# Pending-reboot non-compliance (RebootOption=NoReboot)

**Signatures:** instance is `NON_COMPLIANT` with `InstalledPendingRebootCount>0` while `FailedCount=0`
and `MissingCount=0`; patches in `InstalledPendingReboot` state; Security Hub control **SSM.2** open
("should be COMPLIANT after a patch installation"); the run used `RebootOption=NoReboot`.

**This is NOT a patch failure** — it's a deferred-reboot policy side effect. The remediation is a
controlled reboot in an approved window, not a re-patch.

## Diagnose — confirm it's purely reboot-pending
```bash
aws ssm describe-instance-patch-states --instance-ids <id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount,LastOp:Operation}" --output table
aws ssm describe-instance-patches --instance-id <id> --region <region> \
  --filters Key=State,Values=InstalledPendingReboot --query "Patches[].{KB:KBId,Title:Title}" --output table
```
Decision: `Failed=0, Missing=0, PendingReboot>0` → this applies. `Missing>0`/`Failed>0` → different
problem; route to the root-cause skill first, then return.

## In-guest reboot-readiness pre-check
```powershell
# Windows:
"RebootPending=$(Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')"
(Get-CimInstance Win32_OperatingSystem).LastBootUpTime
```
```bash
# Linux:
needs-restarting -r 2>/dev/null; echo "rc=$?"; [ -f /var/run/reboot-required ] && echo "reboot-required present"; uptime
```
If no reboot is actually pending → re-scan; the state may already be clearing.

## Controlled reboot — GATED
**Only reboot if the failed execution's `RebootOption` was `RebootIfNeeded`.** If it was `NoReboot`,
that's the customer's deferred-reboot policy — do NOT make a disruptive change. Requirements before rebooting:
- an **approved change/maintenance window** exists (these are often GxP/production instances),
- the application owner confirms the instance tolerates a restart,
- cluster/quorum members are rebooted **one at a time**.

## Verify
```bash
aws ssm describe-instance-patch-states --instance-ids <id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount}" --output table
```
Expected `PendingReboot=0, Failed=0, Missing=0`; Security Hub SSM.2 auto-resolves on its next evaluation.

## Escalation
If pending-reboot persists after a successful reboot: the update may be failing to finalize on boot —
check `CBS.log` (Windows) / `dnf history` (Linux); capture boot event logs and the
`InstalledPendingReboot` list; escalate with instance ID, region, and reboot CommandId.
