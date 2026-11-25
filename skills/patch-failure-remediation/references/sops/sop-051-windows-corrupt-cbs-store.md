# SOP-051: Resolve Corrupt Windows Update Component Store (CBS)

| Field | Value |
|-------|-------|
| ID | SOP-051 |
| Category | corrupt_windows_update_store |
| Severity | High |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 600 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with HRESULT `0x80073712` ("The component store has been corrupted")
- `0x800F0831` ("CBS_E_STORE_CORRUPTION")
- `0x800736B3` ("The referenced assembly is not installed on your system")
- DISM /Online /Cleanup-Image /ScanHealth reports corruption
- CBS.log shows "store corruption" or "manifest missing" errors
- Windows Update repeatedly downloads the same update but fails to install
- "Error 14098: The component store has been corrupted"

## Root Cause

Windows Component Store (WinSxS) corruption occurs when:

- Previous update was interrupted during servicing (power loss, forced shutdown)
- Disk I/O error during component store write operations
- Manual deletion of files from C:\Windows\WinSxS or C:\Windows\SoftwareDistribution
- Anti-virus quarantined system files during update installation
- Third-party cleanup tools removed required component manifests
- Failed in-place upgrade left orphaned component references

## Related Failure Patterns

- SOP-023 (WMI/CIM) — WMI corruption can co-occur with CBS corruption
- SOP-024 (TLS Failure) — different root cause but similar "update won't install" symptom

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Sufficient disk space for DISM repair (at least 5GB free on C:)
- Instance has access to Windows Update or a repair source

## Diagnosis

```powershell
# Check CBS health
$scan = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
$scan | Select-String "repairable|corrupted|healthy"
# Check recent CBS errors
Get-Content "$env:SystemRoot\Logs\CBS\CBS.log" -Tail 50 | Select-String "ERROR|corrupt|missing"
```

## Remediation Steps

### Step 1: Run DISM ScanHealth to assess corruption

```powershell
$result = & DISM /Online /Cleanup-Image /ScanHealth 2>&1
$result | Select-String "component store|repairable|no component"
Write-Output "DISM ScanHealth complete"
```

Expected output: "DISM ScanHealth complete"
On failure: continue

### Step 2: Run DISM RestoreHealth to repair component store

```powershell
# Run DISM under a bounded timeout so it cannot hang the maintenance window unattended.
# Launch it directly with -PassThru so on timeout we terminate ONLY this DISM child by PID, never every dism.exe on the host (a concurrent DISM must not be killed mid-transaction).
$out = [System.IO.Path]::GetTempFileName(); $err = [System.IO.Path]::GetTempFileName()
$proc = Start-Process -FilePath DISM -ArgumentList '/Online','/Cleanup-Image','/RestoreHealth' -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
if ($proc.WaitForExit(1800000)) {
    (Get-Content $out, $err) | Select-String "operation completed|error"
    Write-Output "DISM RestoreHealth exit: $($proc.ExitCode)"
} else {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    # dism.exe is only a thin client; the actual servicing runs in TrustedInstaller/TiWorker out-of-process and is NOT stopped by killing the client
    Write-Output "DISM RestoreHealth: TIMEOUT - exceeded 1800s. The dism client was stopped, but TrustedInstaller/TiWorker servicing may still be running in the background - do NOT force a reboot; let servicing finish or escalate."
}
Remove-Item $out, $err -ErrorAction SilentlyContinue
```

Expected output: "DISM RestoreHealth exit: 0"
On failure: if DISM returned a non-zero exit code, continue to Step 3. **If the output was a TIMEOUT, do NOT run Step 3** — TrustedInstaller/TiWorker servicing is still active in the background and `sfc /scannow` would contend with it and can corrupt the CBS store. Wait for servicing to finish (or reboot per change policy) or escalate; this step is terminal on timeout.

### Step 3: Run SFC if DISM alone did not resolve

```powershell
& sfc /scannow 2>&1 | Select-String "found|repair|unable"
Write-Output "SFC exit: $LASTEXITCODE"
```

Expected output: "SFC exit: 0" with "found corrupt files and successfully repaired them" or "did not find any integrity violations"
On failure: continue

### Step 4: Reset Windows Update components

```powershell
Stop-Service wuauserv,cryptSvc,bits,msiserver -Force -ErrorAction SilentlyContinue
Rename-Item "$env:SystemRoot\SoftwareDistribution" "$env:SystemRoot\SoftwareDistribution.old" -Force -ErrorAction SilentlyContinue
Rename-Item "$env:SystemRoot\System32\catroot2" "$env:SystemRoot\System32\catroot2.old" -Force -ErrorAction SilentlyContinue
Start-Service wuauserv,cryptSvc,bits,msiserver -ErrorAction SilentlyContinue
Write-Output "Windows Update components reset"
```

Expected output: "Windows Update components reset"
On failure: continue

### Step 5: Verify component store is healthy

```powershell
$result = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
if ($result -match "healthy") { "CBS STORE HEALTHY" } else { "CBS STORE STILL CORRUPT" }
```

Expected output: "CBS STORE HEALTHY"
On failure: abort

## Validation

```powershell
$health = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
$wuService = Get-Service wuauserv
if ($health -match "healthy" -and $wuService.Status -eq "Running") { "CBS REMEDIATION OK" } else { $health; "CBS STATUS: Check output above" }
```

Expected: "CBS REMEDIATION OK"

## Rollback

```powershell
if (Test-Path "$env:SystemRoot\SoftwareDistribution.old") {
    Stop-Service wuauserv -Force
    Remove-Item "$env:SystemRoot\SoftwareDistribution" -Recurse -Force -ErrorAction SilentlyContinue
    Rename-Item "$env:SystemRoot\SoftwareDistribution.old" "$env:SystemRoot\SoftwareDistribution"
    Start-Service wuauserv
    "SoftwareDistribution restored"
}
if (Test-Path "$env:SystemRoot\System32\catroot2.old") {
    Rename-Item "$env:SystemRoot\System32\catroot2.old" "$env:SystemRoot\System32\catroot2" -Force
    "catroot2 restored"
}
```

## Escalation

If DISM RestoreHealth fails:
- Try specifying a repair source: `DISM /Online /Cleanup-Image /RestoreHealth /Source:WIM:D:\sources\install.wim:1`
- Check if instance can reach Windows Update (RestoreHealth downloads repair files from WU by default)
- For severe corruption: consider in-place upgrade repair or rebuilding from AMI
- Check CBS.log for the specific missing component manifest
