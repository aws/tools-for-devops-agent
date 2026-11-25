# SOP-072: Resolve Windows Update Failure Due to Scheduled Task / Maintenance Window Conflict

| Field | Value |
|-------|-------|
| ID | SOP-072 |
| Category | windows_scheduled_task_conflict |
| Severity | Low |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- SSM patch operation times out waiting for Windows Update
- Another scheduled task already running `wuauclt.exe` or Windows Update scan
- Automatic Maintenance window conflicts with SSM patch maintenance window
- `0x80240022` ("WU_E_ALL_UPDATES_FAILED") due to concurrent access
- Patch operation starts but never completes — no error, just timeout
- TiWorker.exe already running from scheduled maintenance

## Root Cause

Scheduled task conflicts during SSM patching when:

- Windows Automatic Maintenance is running a scan at the same time
- Third-party patch management tool (SCCM, Ivanti) running concurrent scan
- Scheduled Task `Microsoft\Windows\WindowsUpdate\Scheduled Start` triggered
- GPO-configured automatic update time overlaps with SSM window
- Multiple SSM associations targeting same instance at same time
- Background intelligent transfer (BITS) jobs consuming bandwidth
- Server 2012 R2: Automatic Update scheduler runs outside configured hours

## Related Failure Patterns

- SOP-017 (Lock Conflict) — concurrent WU access creates locks
- SOP-052 (WUA Hang) — concurrent access can deadlock WUA

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

```powershell
Get-ScheduledTask | Where-Object { $_.TaskPath -match 'WindowsUpdate|UpdateOrchestrator|Maintenance' -and $_.State -eq 'Running' } | Select-Object TaskName,State,TaskPath
Get-Process TiWorker,wuauclt,UsoClient -ErrorAction SilentlyContinue | Select-Object Name,Id,StartTime
Get-BitsTransfer -AllUsers -ErrorAction SilentlyContinue | Where-Object { $_.JobState -eq 'Transferring' } | Select-Object DisplayName,BytesTransferred
```

## Remediation Steps

### Step 1: Identify running update-related tasks

```powershell
$runningTasks = Get-ScheduledTask | Where-Object { $_.TaskPath -match 'WindowsUpdate|UpdateOrchestrator|Maintenance|SoftwareDistribution' -and $_.State -eq 'Running' }
$updateProcs = Get-Process TiWorker,wuauclt,UsoClient,musNotification -ErrorAction SilentlyContinue
Write-Output "Running WU tasks: $($runningTasks.Count)"
$runningTasks | ForEach-Object { Write-Output "  $($_.TaskName) ($($_.State))" }
Write-Output "Update processes: $($updateProcs.Count)"
$updateProcs | ForEach-Object { Write-Output "  $($_.Name) PID=$($_.Id) since $($_.StartTime)" }
```

Expected output: Tasks and processes listed
On failure: continue

### Step 2: Stop conflicting scheduled tasks

```powershell
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -match 'WindowsUpdate|UpdateOrchestrator' -and $_.State -eq 'Running' }
foreach ($t in $tasks) {
    Stop-ScheduledTask -TaskName $t.TaskName -TaskPath $t.TaskPath -ErrorAction SilentlyContinue
    Write-Output "Stopped: $($t.TaskName)"
}
if ($tasks.Count -eq 0) { Write-Output "No conflicting tasks running" }
```

Expected output: Tasks stopped or none found
On failure: continue

### Step 3: Disable Automatic Maintenance during patch window

```powershell
$maintPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance'
if (-not (Test-Path $maintPath)) { New-Item $maintPath -Force | Out-Null }
Set-ItemProperty $maintPath -Name 'MaintenanceDisabled' -Value 1 -Type DWord
Write-Output "Automatic Maintenance disabled"
```

Expected output: "Automatic Maintenance disabled"
On failure: continue

### Step 4: Restart stuck scheduler services and clean up orphaned scanner processes

```powershell
# NEVER force-kill TiWorker.exe: it is the Windows Modules Installer worker and killing it
# mid-servicing corrupts the component store (the failure SOP-065 repairs). A legitimate
# cumulative update can run TiWorker well past 60 min, so it is deliberately excluded here.
# Prefer restarting the servicing scheduler services over killing processes.
Restart-Service usosvc -Force -ErrorAction SilentlyContinue
Restart-Service wuauserv -Force -ErrorAction SilentlyContinue
Write-Output "Restarted usosvc and wuauserv"
# Only the stuck scheduler/scan clients (never TiWorker) may be terminated, and only if very old.
$orphaned = Get-Process wuauclt,UsoClient -ErrorAction SilentlyContinue | Where-Object { ((Get-Date) - $_.StartTime).TotalMinutes -gt 120 }
if ($orphaned) {
    $orphaned | Stop-Process -Force
    Write-Output "Killed $($orphaned.Count) orphaned scanner process(es)"
} else { Write-Output "No orphaned scanner processes" }
```

Expected output: Process cleanup status
On failure: continue

### Step 5: Verify no conflicting operations remain

```powershell
# Exclude TiWorker: Step 4 deliberately never kills it (a legitimate cumulative update runs it long), so counting it here would falsely report an unresolved conflict
$conflicts = Get-Process wuauclt,UsoClient -ErrorAction SilentlyContinue
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -match 'WindowsUpdate|UpdateOrchestrator' -and $_.State -eq 'Running' }
if ($conflicts.Count -eq 0 -and $tasks.Count -eq 0) { Write-Output "SCHEDULE CONFLICT CLEARED" }
else { Write-Output "STILL CONFLICTING: Processes=$($conflicts.Count) Tasks=$($tasks.Count)" }
```

Expected output: "SCHEDULE CONFLICT CLEARED"
On failure: abort

### Step 6: Re-enable Automatic Maintenance

```powershell
# Step 3 disabled Automatic Maintenance for the patch window; re-enable it on the success path
# so it is not left disabled after remediation completes (Rollback also re-enables it).
$maintPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance'
Remove-ItemProperty $maintPath -Name 'MaintenanceDisabled' -Force -ErrorAction SilentlyContinue
Write-Output "Automatic Maintenance re-enabled"
```

Expected output: "Automatic Maintenance re-enabled"
On failure: continue

## Validation

```powershell
$procs = Get-Process wuauclt,UsoClient -ErrorAction SilentlyContinue
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -match 'WindowsUpdate|UpdateOrchestrator' -and $_.State -eq 'Running' }
if ($procs.Count -eq 0 -and $tasks.Count -eq 0) { "SCHEDULE REMEDIATION OK" } else { "CONFLICTS REMAIN" }
```

Expected: "SCHEDULE REMEDIATION OK"

## Rollback

```powershell
# Re-enable Automatic Maintenance
$maintPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Schedule\Maintenance'
Remove-ItemProperty $maintPath -Name 'MaintenanceDisabled' -Force -ErrorAction SilentlyContinue
Write-Output "Automatic Maintenance re-enabled"
```

## Escalation

If scheduling conflicts persist:
- Check if SCCM/MECM agent is running independent patch cycles
- Verify SSM maintenance windows don't overlap for same target
- For persistent TiWorker issues: check if CBS has a stuck transaction (SOP-065)
- Disable Windows Update scheduled tasks permanently if patching is SSM-managed only
- For Server 2012 R2: disable `wuauserv` automatic start if only using SSM for patching
- Review if multiple patch associations target same instance
