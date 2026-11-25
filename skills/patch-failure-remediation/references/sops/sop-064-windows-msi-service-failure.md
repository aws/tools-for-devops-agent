# SOP-064: Resolve Windows Patch Failure Due to Corrupt Windows Installer (MSI) Service

| Field | Value |
|-------|-------|
| ID | SOP-064 |
| Category | windows_msi_service_failure |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80070643` ("Fatal error during installation") for MSI-based patches
- `0x80070652` ("ERROR_INSTALL_ALREADY_RUNNING") — MSI service stuck
- `0x800F0902` ("CBS_E_INSTALLERS_FAILED") for installer-dependent updates
- Windows Installer service (msiserver) fails to start
- .NET, Visual C++, or Office updates fail while OS updates succeed
- Event 1033/1040 in Application log from MsiInstaller with failure codes

## Root Cause

Windows Installer service failures during patching when:

- MSI service (msiserver) hung from a previous failed installation
- Installer temp folder corrupt or permissions wrong
- Another MSI installation is in progress (single-instance limitation)
- Windows Installer registration broken after system restore
- MSI database (Installer folder) has corrupt cached packages
- Group Policy software installation conflicting with patch MSI
- Server 2012 R2: WMF/PowerShell upgrade left MSI in bad state

## Related Failure Patterns

- SOP-054 (.NET Update) — .NET uses MSI for some components
- SOP-061 (AV Interference) — AV can lock MSI temp files

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No software installations actively in progress

## Diagnosis

```powershell
$msi = Get-Service msiserver
Write-Output "MSI Service: $($msi.Status) ($($msi.StartType))"
Get-Process msiexec -ErrorAction SilentlyContinue | Select-Object Id,CPU,StartTime
Get-WinEvent -LogName Application -MaxEvents 10 | Where-Object { $_.ProviderName -eq 'MsiInstaller' -and $_.Level -le 3 } | Select-Object TimeCreated,Message
```

## Remediation Steps

### Step 1: Check MSI service state and any stuck processes

```powershell
$msi = Get-Service msiserver -ErrorAction SilentlyContinue
$procs = Get-Process msiexec -ErrorAction SilentlyContinue
Write-Output "MSI Service: $($msi.Status)"
if ($procs) { $procs | ForEach-Object { Write-Output "msiexec PID $($_.Id) running since $($_.StartTime)" } }
else { Write-Output "No msiexec processes running" }
```

Expected output: MSI status reported
On failure: continue

### Step 2: Kill stuck MSI processes

```powershell
$stuck = Get-Process msiexec -ErrorAction SilentlyContinue | Where-Object { ((Get-Date) - $_.StartTime).TotalMinutes -gt 15 }
if ($stuck) {
    $stuck | Stop-Process -Force
    Write-Output "Killed $($stuck.Count) stuck msiexec process(es)"
} else { Write-Output "No stuck msiexec processes" }
Start-Sleep -Seconds 3
```

Expected output: Process cleanup status
On failure: continue

### Step 3: Re-register Windows Installer service

```powershell
& msiexec /unregister 2>&1 | Out-Null
Start-Sleep -Seconds 2
& msiexec /regserver 2>&1 | Out-Null
Start-Sleep -Seconds 2
Write-Output "Windows Installer re-registered"
```

Expected output: "Windows Installer re-registered"
On failure: continue

### Step 4: Clear MSI installer temp files

```powershell
# Escape the literal $ characters so this resolves to the real "$PatchCache$" folder,
# not "C:\Windows\Installer\$" (bare $PatchCache is an undefined variable = empty).
$msiTemp = "$env:SystemRoot\Installer\`$PatchCache`$"
# Collect stray MSI*.tmp temp files from the user temp dir and the installer cache folder.
# Note: only *.tmp scratch files are removed here — cached installer packages are left intact.
$tempMsi = @(Get-ChildItem "$env:TEMP\MSI*.tmp" -ErrorAction SilentlyContinue)
if (Test-Path $msiTemp) {
    $tempMsi += @(Get-ChildItem "$msiTemp\MSI*.tmp" -ErrorAction SilentlyContinue)
}
if ($tempMsi.Count -gt 0) {
    $tempMsi | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Output "Cleared $($tempMsi.Count) MSI temp files"
} else { Write-Output "No MSI temp files to clean" }
# Clear pending install state
Remove-Item 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress' -Force -ErrorAction SilentlyContinue
Write-Output "MSI in-progress state cleared"
```

Expected output: Cleanup completed
On failure: continue

### Step 5: Verify MSI service is operational

```powershell
Start-Service msiserver -ErrorAction SilentlyContinue
$msi = Get-Service msiserver
if ($msi.Status -eq 'Running' -or $msi.StartType -eq 'Manual') {
    Write-Output "MSI SERVICE OK: $($msi.Status) ($($msi.StartType))"
} else { Write-Output "MSI SERVICE ISSUE: $($msi.Status)" }
```

Expected output: "MSI SERVICE OK"
On failure: abort

## Validation

```powershell
$msi = Get-Service msiserver
$inProgress = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress'
if (-not $inProgress -and ($msi.Status -ne 'Stopped' -or $msi.StartType -eq 'Manual')) { "MSI REMEDIATION OK" }
else { "MSI ISSUE: InProgress=$inProgress Status=$($msi.Status)" }
```

Expected: "MSI REMEDIATION OK"

## Rollback

MSI re-registration is non-destructive. Service will function normally after remediation.

## Escalation

If MSI service remains broken:
- Run `sfc /scannow` to repair Windows Installer binaries
- Check if `%SystemRoot%\System32\msi.dll` exists and is not corrupted
- For persistent ERROR_INSTALL_ALREADY_RUNNING: check for orphaned _MSIxxxxxx mutex
- If Installer folder is >10GB: use MSIZAP or PatchCleaner to remove orphaned cached packages
- For Server 2012 R2: PowerShell/WMF upgrade may need repair — reinstall WMF 5.1
- Verify Windows Installer version: `msiexec /version` should show 5.0+
