# SOP-017: Resolve Windows Patch Baseline Lock Conflicts

| Field | Value |
|-------|-------|
| ID | SOP-017 |
| Category | windows_patch_lock_conflict |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-10 |

## Symptoms

- `AWS-RunPatchBaseline` `PatchWindows` plugin fails with **exit status 4**
- Error: `Cannot acquire lock on C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock. Another patching operation is in progress`
- SSM Patch Manager reports the instance Failed while a prior patch command is still running or recently exited
- Two overlapping `AWS-RunPatchBaseline` invocations target the same instance in the same window
- Patch operation exits almost immediately (1-3 seconds) without scanning or installing

## Root Cause

Windows patch lock conflicts occur when more than one patch operation attempts to run concurrently on the same instance. SSM serializes patching via the lock file `C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock`; a second operation that cannot acquire it fails fast with exit code 4. Common triggers:

- Both a custom baseline and the default baseline target the instance in the same maintenance window
- The SSM agent retried the patch command (timeout/network blip) while the previous invocation was still holding the lock
- A manual/operator-initiated `AWS-RunPatchBaseline` overlapped with the scheduled maintenance-window run
- A previous patch operation crashed or was killed and left a **stale** lock file behind
- Multiple State Manager associations invoking patch baseline on an overlapping schedule

This is the Windows equivalent of the Linux RPM/yum lock contention handled in SOP-012.

## Related Failure Patterns

- SOP-012 (RPB Race Condition) — Linux equivalent of this problem
- SOP-018 (Transient Post-Scan Auto-Close) — a fast exit-code failure where patches actually succeeded should be auto-triaged, not retried blindly
- SOP-014 (Ubuntu Lock) — Debian/Ubuntu lock contention

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No interactive RDP session is actively running Windows Update / `wuauclt`
- Operator has permission to run `AWS-RunPowerShellScript` and read/cancel SSM commands

## Diagnosis

Identify whether a real patch process is running vs. a stale lock. Run via `AWS-RunPowerShellScript`:

```powershell
# Is a live patch/Windows Update process running?
Get-Process -Name TiWorker,TrustedInstaller,wuauclt,ssm-document-worker -ErrorAction SilentlyContinue | Select-Object Name,Id,StartTime
# Does the lock file exist, and how old is it?
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
if (Test-Path $lock) { Get-Item $lock | Select-Object FullName,LastWriteTime,@{n='AgeMinutes';e={[math]::Round(((Get-Date)-$_.LastWriteTime).TotalMinutes,1)}} } else { 'No lock file present' }
```

Check for overlapping patch processes from the control plane:

```powershell
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
$procs = Get-Process -Name TiWorker,TrustedInstaller,wuauclt,ssm-document-worker -ErrorAction SilentlyContinue
if ($procs) { $procs | Select-Object Name,Id,StartTime } else { "No active patch processes" }
if (Test-Path $lock) { Get-Item $lock | Select-Object FullName,LastWriteTime,@{n='AgeMinutes';e={[math]::Round(((Get-Date)-$_.LastWriteTime).TotalMinutes,1)}} } else { "No lock file present" }
```

**Decision rule:**
- A live `TiWorker`/`TrustedInstaller` process **OR** a lock file younger than ~30 min **AND** an InProgress command = a **real** concurrent operation → do NOT clear the lock; wait (Step 1).
- No patch process **AND** lock older than ~30 min with no InProgress command = **stale** lock → safe to clear (Step 2).

## Remediation Steps

### Step 1: Wait for the genuinely-running operation to complete

If a real concurrent patch operation is in progress, let it finish. Poll the lock file with a hard cap (max 10 polls, ~60s each — no infinite loop):

```powershell
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
$cleared = $false
for ($i = 1; $i -le 10; $i++) {
    $proc = Get-Process -Name TiWorker,TrustedInstaller,wuauclt,ssm-document-worker -ErrorAction SilentlyContinue
    if (-not $proc -and -not (Test-Path $lock)) { $cleared = $true; break }
    Start-Sleep -Seconds 60
}
"LOCK_CLEARED=$cleared after $i poll(s)"
```

Expected output: "LOCK_CLEARED=True"
- If `True` → proceed to Step 2 (if a stale lock file remains) or Step 4 (verify readiness).
- If `False` after 10 polls → STOP; do not loop. A patch operation is genuinely stuck → go to Escalation.

### Step 2: Remove the stale lock (only if Diagnosis confirmed stale)

```powershell
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
$proc = Get-Process -Name TiWorker,TrustedInstaller,wuauclt -ErrorAction SilentlyContinue
if (-not $proc -and (Test-Path $lock)) {
    Remove-Item $lock -Force
    "Stale lock removed"
} else {
    "Lock NOT removed - live patch process detected or no lock present"
}
```

Expected output: `Stale lock removed`
On failure (a live patch process is still present): **do not loop back** — let that operation finish on its own; if it never completes, go to Escalation. Do not delete the lock while a patch process is running.

### Step 3: Confirm the Windows Update service is healthy

```powershell
Get-Service wuauserv | Select-Object Status,StartType
(New-Object -ComObject Microsoft.Update.AutoUpdate).Results | Select-Object LastSearchSuccessDate,LastInstallationSuccessDate
"WUA check done"
```

Expected output: service present (StartType Manual is normal), `WUA check done`
On failure: continue

### Step 4: Confirm readiness for next patch cycle

The underlying lock conflict has been resolved. The patch will be retried automatically by the next scheduled maintenance window run.

```powershell
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
$proc = Get-Process -Name TiWorker,TrustedInstaller,wuauclt -ErrorAction SilentlyContinue
if (-not $proc -and -not (Test-Path $lock)) { "READY for next patch cycle" } else { "NOT READY - processes or lock still present" }
```

Expected output: "READY for next patch cycle"
On failure: abort and escalate

## Validation

```powershell
$lock = 'C:\ProgramData\Amazon\SSM\patch-baseline-concurrent.lock'
$proc = Get-Process -Name TiWorker,TrustedInstaller,wuauclt -ErrorAction SilentlyContinue
$svc = Get-Service wuauserv -ErrorAction SilentlyContinue
if (-not $proc -and -not (Test-Path $lock) -and $svc) { "LOCK CONFLICT RESOLVED" } else { "LOCK CONFLICT NOT RESOLVED" }
```

Expected: "LOCK CONFLICT RESOLVED"

## Rollback

No destructive change is made (only a stale lock file is removed). Nothing to roll back.

## Prevention

- Ensure only **one** baseline (custom OR default) targets each instance — audit with `aws ssm describe-patch-groups`.
- Avoid manual `AWS-RunPatchBaseline` during the scheduled maintenance window.
- Stagger State Manager associations so patch invocations do not overlap.
- Increase maintenance-window task `MaxConcurrency`/timeout tuning so the agent does not retry mid-operation.

## Escalation

If the lock reappears immediately after removal or exit-4 persists with no concurrent command:
- Capture `Get-Process`, the lock file `LastWriteTime`, and `aws ssm list-commands` output
- Check for a hung `ssm-document-worker` (restart `AmazonSSMAgent` service if confirmed hung)
- Escalate to your patching team with the CommandId and instance ID
