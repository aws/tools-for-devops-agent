# Windows Installer (MSI) service failure

**Signatures:** `0x80070643` "Fatal error during installation", `0x80070652`
ERROR_INSTALL_ALREADY_RUNNING, `0x800F0902` CBS_E_INSTALLERS_FAILED, msiserver won't start, .NET /
VC++ / Office updates fail while OS updates succeed, Event 1033/1040 from MsiInstaller.

## Diagnose
```powershell
Get-Service msiserver | Select Status,StartType
Get-Process msiexec -EA SilentlyContinue | Select Id,CPU,StartTime
Get-WinEvent -LogName Application -MaxEvents 10 | ? {$_.ProviderName -eq 'MsiInstaller' -and $_.Level -le 3} | Select TimeCreated,Message
```

## Fix — kill stuck msiexec, re-register the installer, clear InProgress
```powershell
# kill msiexec stuck >15 min
Get-Process msiexec -EA SilentlyContinue | ? {((Get-Date)-$_.StartTime).TotalMinutes -gt 15} | Stop-Process -Force; Start-Sleep 3
msiexec /unregister 2>&1 | Out-Null; Start-Sleep 2; msiexec /regserver 2>&1 | Out-Null; Start-Sleep 2
Get-ChildItem "$env:TEMP\MSI*.tmp" -EA SilentlyContinue | Remove-Item -Force -EA SilentlyContinue
Remove-Item 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress' -Force -EA SilentlyContinue
Start-Service msiserver -EA SilentlyContinue
```

## Verify
```powershell
$m=Get-Service msiserver
$inprog = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress'
if(-not $inprog -and ($m.Status -ne 'Stopped' -or $m.StartType -eq 'Manual')){"MSI OK"}else{"MSI ISSUE"}
```

## Escalation
- Persistent breakage → `sfc /scannow` to repair installer binaries; verify `System32\msi.dll` present, `msiexec /version` shows 5.0+.
- ALREADY_RUNNING that won't clear → orphaned `_MSI...` mutex; reboot to clear.
- Installer folder >10GB of orphaned cached packages → MSIZAP / PatchCleaner.
- Server 2012 R2 after WMF/PowerShell upgrade → reinstall WMF 5.1.
