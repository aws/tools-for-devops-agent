# SOP-018: Triage and Auto-Close Transient Post-Patch Scan Failures

| Field | Value |
|-------|-------|
| ID | SOP-018 |
| Category | transient_postscan_failure |
| Severity | Low |
| Risk Level | Low |
| Platforms | Windows, Linux |
| Distributions | All supported |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-10 |

## Symptoms

- A patch-failure alert or OpsItem is raised, but the instance is **already compliant** (`MissingCount=0, FailedCount=0`)
- `AWS-RunPatchBaseline` `PatchWindows`/`PatchLinux` plugin returns a bare **`failed to run commands: exit status 1`** with no descriptive error
- PatchDiag shows **patches were installed** (KBs/packages present with a recent InstalledOn date) yet the operation is marked Failed
- The failure is at the **post-install patch-baseline scan / verification** step, not the install step
- Pre-patch validation passed (endpoints reachable, disk space OK, credentials OK)
- The same instance is healthy on the next daily scan with no operator action

## Root Cause

The patch **installed successfully**, but the post-install verification scan returned a non-zero exit code, causing SSM to flag the whole operation as Failed and the patch automation to raise a PatchInstallFailure OpsItem. Causes of the transient post-scan failure include:

- The scan ran while the OS was finalizing updates or in a momentary reboot-pending state
- A brief WUA/CIM/scan-engine timeout immediately after a large install batch
- SSM agent command-completion verification race (scan command returned Failed envelope while results were still flushing)
- Transient resource pressure (CPU/disk) during the post-install scan

The defining characteristic: **the failure is cosmetic** — current compliance is clean. These OpsItems accumulate as `InProgress` noise and obscure genuine failures if not closed.

## Related Failure Patterns

- SOP-017 (Windows Lock Conflict) — a *fast* exit-code failure that is real; this SOP must distinguish transient-but-succeeded from genuinely-failed
- SOP-012 (RPB Race Condition) — a race can also produce spurious post-scan results

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Operator/automation has permission to query patch compliance and `ssm update-ops-item`
- The OpsItem ID and target instance ID are known

## Diagnosis

Determine whether this is a transient (succeeded) failure or a genuine one. **This gate is mandatory before any auto-close.**

```bash
# 1. Current compliance state
aws ssm describe-instance-patch-states --instance-ids <instance-id> --region <region> \
  --query "InstancePatchStates[0].{Op:Operation,Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount,InstalledOther:InstalledOtherCount}" --output table

# 2. Are there any patches actually in Failed state?
aws ssm describe-instance-patches --instance-id <instance-id> --region <region> \
  --filters Key=State,Values=Failed --query "Patches[].{KB:KBId,Title:Title,State:State}" --output table
```

**Decision rule:**
- `FailedCount=0` **AND** `MissingCount=0` **AND** the Failed-state query returns empty → **transient, succeeded** → proceed to auto-close (Step 2).
- `InstalledPendingRebootCount>0` (otherwise clean) → not a failure; route to reboot scheduling (SOP-019) and close as pending-reboot.
- `FailedCount>0` **OR** `MissingCount>0` → **genuine** failure → STOP, do not auto-close; route to the matching SOP (Linux: SOP-001/003/004/...; Windows lock: SOP-017) and escalate.

## Remediation Steps

### Step 1: Verify current patch compliance state

Confirm the instance is currently compliant (the transient failure was cosmetic):

```bash
aws ssm describe-instance-patch-states --instance-ids <instance-id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount}" --output table
```

Expected output: `Failed=0` and `Missing=0`.
On failure (any non-zero): abort auto-close, route to the matching root-cause SOP.

### Step 2: Confirm no patches in Failed state

```bash
aws ssm describe-instance-patches --instance-id <instance-id> --region <region> \
  --filters Key=State,Values=Failed --query "Patches[].{KB:KBId,Title:Title,State:State}" --output table
```

Expected output: empty result (no failed patches)
On failure: abort auto-close, route to the matching root-cause SOP.

### Step 3: Auto-close the OpsItem with evidence

Only if Steps 1 and 2 confirmed clean:

```bash
aws ssm update-ops-item --ops-item-id <ops-item-id> --status Resolved \
  --operational-data '{"resolutionNote":{"Value":"Transient post-patch scan failure (SOP-018). Fresh scan confirms FailedCount=0, MissingCount=0; patches installed successfully. Auto-resolved.","Type":"String"}}' \
  --region <region>
```

Expected output: command succeeds; OpsItem moves to `Resolved`.
On failure: continue to manual close and flag the permissions gap.

## Validation

```bash
aws ssm get-ops-item --ops-item-id <ops-item-id> --region <region> \
  --query "OpsItem.{Id:OpsItemId,Status:Status,Title:Title}" --output table
```

Expected: `Status=Resolved`.

## Rollback

Re-open the OpsItem if later evidence shows a genuine failure:

```bash
aws ssm update-ops-item --ops-item-id <ops-item-id> --status Open --region <region>
```

## Prevention

- Add a built-in post-install **re-scan + grace period** before the patch automation declares failure, so reboot-pending/finalizing states are not misreported.
- Implement a scheduled sweep that applies the Diagnosis gate to all open `PatchInstallFailure` OpsItems daily and auto-resolves the transient ones.
- Treat repeated transient failures on the *same* instance across cycles as a real signal (route to SOP for repeat offenders) rather than auto-closing indefinitely.

## Escalation

If an instance repeatedly raises transient post-scan failures (3+ consecutive cycles) despite clean compliance:
- Capture the scan CommandId, exit code, and `describe-instance-patch-states` history
- Check for resource pressure during the patch window (CPU/disk metrics)
- Escalate to your patching team — the post-scan verification logic may be timing out on this instance class
