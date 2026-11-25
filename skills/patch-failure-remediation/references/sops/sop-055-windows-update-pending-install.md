# SOP-055: Resolve Windows Update Stuck in "Pending Install" State

| Field | Value |
|-------|-------|
| ID | SOP-055 |
| Category | windows_update_pending_install |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 240 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Updates permanently in "Pending Install" state, never completing
- SSM Patch Compliance shows patches as "InstalledPendingReboot" indefinitely
- `PendingFileRenameOperations` registry key contains stale entries
- `RebootPending` flag persists even after reboot
- Component-Based Servicing reports packages in "Install Pending" stage
- New patches cannot install because previous updates are "in progress"

## Root Cause

Updates get stuck pending when:

- Pending reboot flag left behind by a cancelled or failed installation
- `SessionsPending` registry contains orphaned update session IDs
- TrustedInstaller failed to complete post-reboot servicing
- Group Policy prevents automatic reboot but pending state persists
- CBS package state stuck between "Staged" and "Installed"
- Third-party software set RebootRequired registry keys
- Server 2012 R2 specific: multiple cumulative updates queued but never rebooted

## Related Failure Patterns

- SOP-019 (Pending Reboot Scheduling) — reboot scheduling vs stuck pending state
- SOP-022 (Reboot Race) — reboot interruption can leave pending state

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Confirm no legitimate reboot is actually needed before clearing flags

## Diagnosis

```powershell
$rebootKeys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending',
    'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
)
foreach ($k in $rebootKeys) {
    if (Test-Path $k) { Write-Output "FOUND: $k" }
}
$pfr = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
if ($pfr) { Write-Output "PendingFileRename entries: $($pfr.Count)" }
```

## Remediation Steps

### Step 1: Check pending reboot indicators

```powershell
$pending = @()
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') { $pending += 'WU-RebootRequired' }
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending') { $pending += 'CBS-RebootPending' }
if (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\SessionsPending') { $pending += 'CBS-SessionsPending' }
$pfr = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
if ($pfr) { $pending += "PFR($($pfr.Count) entries)" }
Write-Output "Pending indicators: $($pending -join ', ')"
```

Expected output: Pending indicators listed
On failure: abort

### Step 2: Clear Windows Update RebootRequired flag

```powershell
$path = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired'
if (Test-Path $path) {
    Remove-Item $path -Force
    Write-Output "Removed WU RebootRequired key"
} else { Write-Output "No WU RebootRequired key" }
```

Expected output: Key removal confirmed
On failure: continue

### Step 3: Clear CBS pending sessions

```powershell
# reg.exe uses the HKLM\ (no colon) form; PowerShell uses HKLM:\
$cbsKeys = @{
    'CBS-RebootPending'   = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
    'CBS-SessionsPending' = 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\SessionsPending'
}
# Safety guard: never clear CBS pending state while servicing is actively in progress —
# a reboot/cleanup is then genuinely required and wiping these keys would corrupt servicing.
$servicingActive = (Get-Process TiWorker,TrustedInstaller -ErrorAction SilentlyContinue) -or ((Get-Service TrustedInstaller -ErrorAction SilentlyContinue).Status -eq 'Running')
# Recreate the backup dir fresh per run, BEFORE the servicingActive check, so Rollback never restores stale .reg files left by a previous run that took the skip branch
$backupDir = "$env:SystemRoot\Temp\PatchRemediation-Backup"
if (Test-Path $backupDir) { Remove-Item $backupDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction SilentlyContinue | Out-Null
if ($servicingActive) {
    Write-Output "SKIPPING CBS pending removal - TiWorker/TrustedInstaller servicing is in progress; a reboot is genuinely needed"
} else {
    foreach ($name in $cbsKeys.Keys) {
        $regPath = $cbsKeys[$name]
        $psPath = 'HKLM:\' + ($regPath -replace '^HKLM\\','')
        if (Test-Path $psPath) {
            $backupFile = Join-Path $backupDir "$name.reg"
            & reg.exe export "$regPath" "$backupFile" /y 2>&1 | Out-Null
            # Only remove the key if the backup actually succeeded, so Rollback can always restore it
            if ((Test-Path $backupFile) -and ($LASTEXITCODE -eq 0)) {
                Remove-Item $psPath -Recurse -Force
                Write-Output "Backed up to $backupFile and removed: $regPath"
            } else {
                Write-Output "Backup of $regPath failed - NOT removing"
            }
        }
    }
    Write-Output "CBS pending state cleared (backups in $backupDir)"
}
```

Expected output: "CBS pending state cleared (backups in ...)" — or "SKIPPING CBS pending removal - ..." if TiWorker/TrustedInstaller servicing is in progress
On failure: continue

### Step 4: Clear stale PendingFileRenameOperations

```powershell
$sm = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
$pfr = (Get-ItemProperty $sm -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations
if ($pfr -and $pfr.Count -gt 0) {
    $backupPath = 'HKLM:\SOFTWARE\Amazon\PatchRemediation\Backup'
    if (-not (Test-Path $backupPath)) { New-Item -Path $backupPath -Force | Out-Null }
    Set-ItemProperty -Path $backupPath -Name 'PendingFileRenameOperations_Backup' -Value $pfr
    Remove-ItemProperty $sm -Name PendingFileRenameOperations -Force -ErrorAction SilentlyContinue
    Write-Output "Backed up and cleared $($pfr.Count) PendingFileRename entries"
} else { Write-Output "No stale PFR entries" }
```

Expected output: PFR entries backed up and cleared, or none found
On failure: continue

### Step 5: Restart Windows Update agent

```powershell
Restart-Service wuauserv -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
$s = Get-Service wuauserv
Write-Output "PENDING STATE CLEARED - WUA status: $($s.Status)"
```

Expected output: "PENDING STATE CLEARED"
On failure: abort

## Validation

```powershell
$reboot = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or
          (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')
if (-not $reboot) { "PENDING STATE REMEDIATION OK" } else { "STILL PENDING" }
```

Expected: "PENDING STATE REMEDIATION OK"

## Rollback

Reboot indicators are informational flags. If patches truly need a reboot to complete, the next patch scan cycle will re-set the flags appropriately.

To restore the CBS pending keys removed in Step 3, re-import the backups exported to `$env:SystemRoot\Temp\PatchRemediation-Backup`:

```powershell
$backupDir = "$env:SystemRoot\Temp\PatchRemediation-Backup"
foreach ($f in @('CBS-RebootPending.reg','CBS-SessionsPending.reg')) {
    $path = Join-Path $backupDir $f
    if (Test-Path $path) { & reg.exe import "$path" 2>&1 | Out-Null; Write-Output "Restored $f" }
}
```

To restore PendingFileRenameOperations if other applications are affected:

```powershell
$backupPath = 'HKLM:\SOFTWARE\Amazon\PatchRemediation\Backup'
$backup = (Get-ItemProperty $backupPath -Name 'PendingFileRenameOperations_Backup' -ErrorAction SilentlyContinue).PendingFileRenameOperations_Backup
if ($backup) {
    Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager' -Name PendingFileRenameOperations -Value $backup
    Write-Output "Restored $($backup.Count) PendingFileRename entries from backup"
} else { Write-Output "No backup found" }
```

## Escalation

If pending state returns immediately:
- Check CBS.log for packages stuck in staging: `Select-String "Staged|Install Pending" $env:SystemRoot\Logs\CBS\CBS.log`
- Run `DISM /Online /Cleanup-Image /RevertPendingActions` (Server 2012 R2)
- For persistent SessionsPending: a reboot may genuinely be required — schedule maintenance reboot
- Check if Group Policy `NoAutoRebootWithLoggedOnUsers` is blocking needed reboots
