# SOP-061: Resolve Windows Patch Failure Due to Antivirus/Security Software Interference

| Field | Value |
|-------|-------|
| ID | SOP-061 |
| Category | windows_antivirus_patch_interference |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch installation fails with `0x80070005` ("Access Denied") on system files
- `0x80070020` ("The process cannot access the file because it is being used by another process")
- TrustedInstaller cannot replace files locked by AV real-time scanning
- CBS.log shows "access denied" errors on WinSxS file operations
- Patches install on reboot but AV blocks post-install configuration
- Windows Defender conflicts with third-party AV (dual-AV scenario)
- Update rollback triggered by AV driver compatibility check

## Root Cause

Security software interferes with patching when:

- Real-time file scanning locks files TrustedInstaller needs to replace
- AV kernel-mode filter driver blocks CBS write operations to WinSxS
- Application control (Carbon Black, CrowdStrike) blocks update binaries
- Third-party AV hasn't set `ALLOW REGKEY` for Windows Update compatibility
- DLP (Data Loss Prevention) agents scanning SoftwareDistribution folder
- EDR hooks on process creation block TiWorker.exe child processes
- Server 2012 R2/2016: Spectre/Meltdown patch requires AV compatibility registry key

## Related Failure Patterns

- SOP-017 (Lock Conflict) — AV file locks present as lock conflicts
- SOP-057 (Driver Update) — AV filter drivers can conflict with driver updates

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Knowledge of customer's AV/EDR product for proper exclusion configuration

## Diagnosis

```powershell
Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction SilentlyContinue | Select-Object displayName,productState
Get-Service | Where-Object { $_.DisplayName -match 'Symantec|McAfee|CrowdStrike|Trend|Sophos|Carbon|Cylance|SentinelOne|Defender' } | Select-Object Name,DisplayName,Status
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\QualityCompat' -ErrorAction SilentlyContinue
```

## Remediation Steps

### Step 1: Identify installed security products

```powershell
$avServices = Get-Service | Where-Object { $_.DisplayName -match 'Symantec|McAfee|CrowdStrike|Trend|Sophos|Carbon|Cylance|SentinelOne|Defender|ESET|Kaspersky|Bitdefender' -and $_.Status -eq 'Running' }
$avServices | ForEach-Object { Write-Output "RUNNING: $($_.DisplayName) ($($_.Name))" }
$drivers = Get-WindowsDriver -Online | Where-Object { $_.ProviderName -match 'Symantec|McAfee|CrowdStrike|Trend|Sophos|Carbon|Cylance|SentinelOne' }
Write-Output "AV filter drivers: $($drivers.Count)"
Write-Output "AV services found: $($avServices.Count)"
```

Expected output: AV products identified
On failure: continue

### Step 2: Check AV compatibility registry key (Spectre/Meltdown requirement)

```powershell
$qcPath = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\QualityCompat'
$val = (Get-ItemProperty $qcPath -Name 'cadca5fe-87d3-4b96-b7fb-a231484277cc' -ErrorAction SilentlyContinue).'cadca5fe-87d3-4b96-b7fb-a231484277cc'
if ($val -eq 0) { Write-Output "AV compatibility key: SET (OK)" }
else {
    New-Item $qcPath -Force -ErrorAction SilentlyContinue | Out-Null
    Set-ItemProperty $qcPath -Name 'cadca5fe-87d3-4b96-b7fb-a231484277cc' -Value 0 -Type DWord
    Write-Output "AV compatibility key: CREATED (was missing)"
}
```

Expected output: Compatibility key status
On failure: continue

### Step 3: Add Windows Update exclusions for common AV paths

```powershell
# Add exclusions to Windows Defender (if active)
$defenderActive = (Get-Service WinDefend -ErrorAction SilentlyContinue).Status -eq 'Running'
if ($defenderActive) {
    $exclusions = @(
        "$env:SystemRoot\SoftwareDistribution",
        "$env:SystemRoot\WinSxS",
        "$env:SystemRoot\System32\catroot2",
        "$env:SystemRoot\Temp\MpCmdRun.log"
    )
    foreach ($ex in $exclusions) { Add-MpPreference -ExclusionPath $ex -ErrorAction SilentlyContinue }
    Write-Output "Defender exclusions added for WU paths"
} else { Write-Output "Defender not active — third-party AV likely in use" }
```

Expected output: Exclusions added or third-party AV noted
On failure: continue

### Step 4: Temporarily disable real-time protection for patch installation

> Note: Real-time protection is disabled ONLY for the patch window and MUST be restored afterward — Step 6 (on success) and Rollback (on failure) both re-enable it.

```powershell
$defenderActive = (Get-Service WinDefend -ErrorAction SilentlyContinue).Status -eq 'Running'
if ($defenderActive) {
    Set-MpPreference -DisableRealtimeMonitoring $true -ErrorAction SilentlyContinue
    Write-Output "Defender real-time monitoring disabled temporarily"
} else {
    Write-Output "MANUAL ACTION: Third-party AV real-time scan should be temporarily disabled"
    Write-Output "Cannot programmatically disable third-party AV"
}
```

Expected output: Protection disabled or manual action noted
On failure: continue

### Step 5: Verify no file locks on update directories

```powershell
$testFile = "$env:SystemRoot\SoftwareDistribution\test_write_$(Get-Random).tmp"
try {
    [System.IO.File]::WriteAllText($testFile, "test")
    Remove-Item $testFile -Force
    Write-Output "AV INTERFERENCE CLEARED: Write access OK"
} catch {
    Write-Output "AV STILL BLOCKING: $($_.Exception.Message)"
}
```

Expected output: "AV INTERFERENCE CLEARED"
On failure: abort

### Step 6: Re-enable Defender real-time protection (restore security posture)

```powershell
$defenderActive = (Get-Service WinDefend -ErrorAction SilentlyContinue).Status -eq 'Running'
if ($defenderActive) {
    Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $rtOff = (Get-MpPreference).DisableRealtimeMonitoring
    if (-not $rtOff) { Write-Output "Defender real-time monitoring RE-ENABLED (verified ON)" }
    else { Write-Output "WARNING: Defender real-time monitoring still OFF - manual restoration required" }
} else {
    Write-Output "MANUAL ACTION: Re-enable third-party AV real-time scan disabled in Step 4"
}
```

Expected output: "Defender real-time monitoring RE-ENABLED (verified ON)"
On failure: abort

## Validation

```powershell
$testFile = "$env:SystemRoot\SoftwareDistribution\verify_$(Get-Random).tmp"
try {
    [System.IO.File]::WriteAllText($testFile, "verify")
    Remove-Item $testFile -Force
    $qc = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\QualityCompat' -Name 'cadca5fe-87d3-4b96-b7fb-a231484277cc' -ErrorAction SilentlyContinue).'cadca5fe-87d3-4b96-b7fb-a231484277cc'
    if ($qc -eq 0) { "AV REMEDIATION OK" } else { "AV COMPAT KEY MISSING" }
} catch { "AV STILL INTERFERING" }
```

Expected: "AV REMEDIATION OK"

## Rollback

```powershell
# Re-enable Defender real-time protection
Set-MpPreference -DisableRealtimeMonitoring $false -ErrorAction SilentlyContinue
Write-Output "Defender real-time monitoring re-enabled"
```

## Escalation

If AV interference persists:
- For CrowdStrike: sensor exclusions must be configured in Falcon Console (not locally)
- For Symantec/Broadcom: add `TrustedInstaller.exe` and `TiWorker.exe` to scan exclusions
- For Carbon Black: ensure `svchost.exe` with WUA service is on the approved list
- Contact customer security team to add patching maintenance window in AV policy
- For Server 2012 R2/2016: ensure AV compatibility key exists — Microsoft blocks updates without it
- If dual-AV scenario (Defender + third-party): disable Defender via GPO
