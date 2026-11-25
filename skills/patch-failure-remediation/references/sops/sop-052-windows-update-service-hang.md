# SOP-052: Resolve Windows Update Service Crash/Hang (BITS/WUA)

| Field | Value |
|-------|-------|
| ID | SOP-052 |
| Category | windows_update_service_hang |
| Severity | High |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch scan hangs indefinitely — never returns results
- Windows Update service (wuauserv) stuck in "Stopping" or "Starting" state
- BITS (Background Intelligent Transfer Service) not running
- `0x80070422` ("The service cannot be started")
- `0x80246008` ("Update download failed")
- svchost.exe consuming 100% CPU in WUA context
- TiWorker.exe (Trusted Installer) hung for extended period
- Patch operation times out without error — just no progress

## Root Cause

Windows Update service failures when:

- WUA service (wuauserv) in a corrupted state — DLL registration broken
- BITS service crashed and cannot transfer update packages
- SoftwareDistribution folder contains corrupt download state
- TrustedInstaller service hung processing a previous update
- WUA DLL version mismatch after partial servicing stack update
- Service dependencies (RPC, Cryptographic Services) not started
- Windows Update Agent needs self-update but cannot complete it

## Related Failure Patterns

- SOP-017 (Lock Conflict) — service hang can leave lock files
- SOP-051 (Corrupt CBS) — service hangs can indicate underlying store corruption
- SOP-021 (WSUS Unreachable) — network issues can cause WUA to appear hung

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No active RDP session running Windows Update manually

## Diagnosis

```powershell
Get-Service wuauserv,bits,cryptSvc,TrustedInstaller | Select-Object Name,Status,StartType
Get-Process -Name TiWorker,svchost,wuauclt -ErrorAction SilentlyContinue | Where-Object {$_.CPU -gt 60} | Select-Object Name,Id,CPU,StartTime
(New-Object -ComObject Microsoft.Update.AutoUpdate).Results | Select-Object LastSearchSuccessDate,LastInstallationSuccessDate
```

## Remediation Steps

### Step 1: Check Windows Update service state

```powershell
$services = @('wuauserv','bits','cryptSvc','msiserver','TrustedInstaller')
foreach ($svc in $services) {
    $s = Get-Service $svc -ErrorAction SilentlyContinue
    Write-Output "$($svc): $($s.Status) ($($s.StartType))"
}
Write-Output "Service check done"
```

Expected output: Service states listed
On failure: continue

### Step 2: Kill hung update processes

```powershell
$hung = Get-Process -Name TiWorker,wuauclt -ErrorAction SilentlyContinue | Where-Object { ((Get-Date) - $_.StartTime).TotalMinutes -gt 30 }
if ($hung) {
    $hung | Stop-Process -Force
    Write-Output "Killed $($hung.Count) hung process(es)"
} else {
    Write-Output "No hung update processes"
}
```

Expected output: "No hung update processes" or kill confirmation
On failure: continue

### Step 3: Stop and reset Windows Update services

```powershell
Stop-Service wuauserv,bits,cryptSvc,msiserver -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
# Verify stopped
$still = Get-Service wuauserv,bits | Where-Object {$_.Status -ne 'Stopped'}
if ($still) { $still | ForEach-Object { $svcName = $_.Name; $proc = (Get-WmiObject Win32_Service -Filter "Name='$svcName'").ProcessId; if ($proc) { Stop-Process -Id $proc -Force -ErrorAction SilentlyContinue } } }
Write-Output "Services stopped"
```

Expected output: "Services stopped"
On failure: continue

### Step 4: Clear SoftwareDistribution download cache

```powershell
$sd = "$env:SystemRoot\SoftwareDistribution\Download"
if (Test-Path $sd) {
    Remove-Item "$sd\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Output "Download cache cleared"
} else { Write-Output "No download cache found" }
```

Expected output: "Download cache cleared"
On failure: continue

### Step 5: Re-register Windows Update DLLs

```powershell
$dlls = @('wuaueng.dll','wuaueng1.dll','wucltui.dll','wups.dll','wups2.dll','wuweb.dll','atl.dll','msxml3.dll')
foreach ($dll in $dlls) {
    $path = Join-Path "$env:SystemRoot\System32" $dll
    if (Test-Path $path) { & regsvr32.exe /s $path }
}
Write-Output "WUA DLLs re-registered"
```

Expected output: "WUA DLLs re-registered"
On failure: continue

### Step 6: Start services and verify

```powershell
Start-Service bits,cryptSvc,msiserver,wuauserv -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
$wua = Get-Service wuauserv
$bits = Get-Service bits
if ($wua.Status -eq 'Running' -or $wua.Status -eq 'Stopped') {
    Write-Output "WUA SERVICE OK (Status: $($wua.Status), BITS: $($bits.Status))"
} else {
    Write-Output "WUA SERVICE PROBLEM: $($wua.Status)"
}
```

Expected output: "WUA SERVICE OK"
On failure: abort

## Validation

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
try {
    $result = $searcher.Search("IsInstalled=0 and Type='Software'")
    Write-Output "WUA SEARCH OK: $($result.Updates.Count) updates found"
} catch {
    Write-Output "WUA SEARCH FAILED: $($_.Exception.Message)"
}
```

Expected: "WUA SEARCH OK: N updates found"

## Rollback

```powershell
Start-Service wuauserv,bits,cryptSvc,msiserver -ErrorAction SilentlyContinue
Write-Output "Services started - no destructive changes to rollback"
```

## Escalation

If WUA service remains stuck:
- Check Event Log: `Get-WinEvent -LogName System -MaxEvents 20 | Where-Object {$_.ProviderName -match 'Update|BITS|Trust'}`
- Reset WUA completely: download and run Microsoft's Windows Update Troubleshooter
- If svchost consuming 100% CPU in WUA context: the update scan database may be corrupt — delete `%SystemRoot%\SoftwareDistribution\DataStore\DataStore.edb`
- For Server 2016: ensure SSU (Servicing Stack Update) is current — outdated SSU causes TrustedInstaller hangs
