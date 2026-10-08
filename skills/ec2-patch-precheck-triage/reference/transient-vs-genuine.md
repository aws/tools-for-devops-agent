# Transient (cosmetic) vs genuine patch failure — the auto-close gate

**Signatures:** an `AWSManagedServices:PatchInstallFailure` OpsItem is raised, but the instance is
**already compliant**; `AWS-RunPatchBaseline` returned a bare `failed to run commands: exit status 1`
with no descriptive error; PatchDiag shows patches installed with a recent date yet the op is Failed;
the failure was at the **post-install scan/verify** step, and the next daily scan is clean with no action.

**Root cause:** the patch installed fine but the post-install verification scan returned non-zero
(reboot-pending/finalizing state, a brief WUA/CIM/scan timeout, or an SSM command-completion race),
so SSM flagged the whole op Failed. The failure is **cosmetic** — but you must PROVE it.

## The mandatory gate (run BEFORE any auto-close)
```bash
aws ssm describe-instance-patch-states --instance-ids <id> --region <region> \
  --query "InstancePatchStates[0].{Failed:FailedCount,Missing:MissingCount,PendingReboot:InstalledPendingRebootCount}" --output table
aws ssm describe-instance-patches --instance-id <id> --region <region> \
  --filters Key=State,Values=Failed --query "Patches[].{KB:KBId,State:State}" --output table
```

**Decision rule:**
- `FailedCount=0` AND `MissingCount=0` AND the Failed-state query is **empty** → transient/succeeded → auto-close with evidence.
- `InstalledPendingRebootCount>0` (otherwise clean) → not a failure → route to reboot scheduling; close as pending-reboot.
- `FailedCount>0` OR `MissingCount>0` OR any patch in Failed state → **GENUINE** → STOP, do NOT close → route to the matching root-cause skill and escalate.

## Auto-close with evidence (only if the gate passed)
```bash
aws ssm update-ops-item --ops-item-id <id> --status Resolved \
  --operational-data '{"resolutionNote":{"Value":"Transient post-patch scan failure. Fresh scan: FailedCount=0, MissingCount=0, no Failed-state patches; patches installed. Auto-resolved.","Type":"String"}}' \
  --region <region>
```
Rollback: re-open with `--status Open` if later evidence shows a genuine failure.

## Escalation
Treat 3+ consecutive transient failures on the **same** instance as a real signal (scan verification
timing out on that instance class) — capture the scan CommandId/exit code and patch-state history,
escalate to patch engineering. Do not auto-close indefinitely.
