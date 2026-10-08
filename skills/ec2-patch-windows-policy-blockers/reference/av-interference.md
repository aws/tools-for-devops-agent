# Antivirus / EDR interference & the QualityCompat gate

**Signatures:** `0x80070005` (access denied) or `0x80070020` (file in use) on system files during
install, CBS.log "access denied" on WinSxS, TrustedInstaller can't replace AV-locked files, updates
roll back after an AV driver-compat check, scan returns 0 updates on 2012 R2/2016 (missing
QualityCompat key).

## The QualityCompat (Spectre/Meltdown) gate — check FIRST on 2012 R2/2016
Microsoft will NOT offer updates until the AV-compat key is set:
```powershell
$qc='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\QualityCompat'
$v=(Get-ItemProperty $qc -Name 'cadca5fe-87d3-4b96-b7fb-a231484277cc' -EA SilentlyContinue).'cadca5fe-87d3-4b96-b7fb-a231484277cc'
if($v -ne 0){ New-Item $qc -Force|Out-Null; Set-ItemProperty $qc -Name 'cadca5fe-87d3-4b96-b7fb-a231484277cc' -Value 0 -Type DWord; "QualityCompat key set" } else { "QualityCompat OK" }
```

## Identify AV/EDR + add WU exclusions
```powershell
Get-Service | ? {$_.DisplayName -match 'CrowdStrike|Symantec|McAfee|Carbon|SentinelOne|Trend|Sophos|Cylance|Defender|ESET|Kaspersky' -and $_.Status -eq 'Running'} | Select DisplayName,Name
# Defender exclusions for WU paths (on-box):
if((Get-Service WinDefend -EA SilentlyContinue).Status -eq 'Running'){
  'SoftwareDistribution','WinSxS','System32\catroot2' | % { Add-MpPreference -ExclusionPath "$env:SystemRoot\$_" -EA SilentlyContinue }
  # temporary, patch-window only:
  Set-MpPreference -DisableRealtimeMonitoring $true -EA SilentlyContinue
}
```

## Verify write access
```powershell
$t="$env:SystemRoot\SoftwareDistribution\wtest_$(Get-Random).tmp"
try{ [IO.File]::WriteAllText($t,'x'); Remove-Item $t -Force; "WRITE OK" }catch{ "AV STILL BLOCKING: $($_.Exception.Message)" }
```

## Escalation / cleanup
- **Third-party AV/EDR exclusions are set in the vendor console, not locally:** CrowdStrike (Falcon Console), Carbon Black (approved list for svchost/TiWorker), Symantec/Broadcom (exclude TrustedInstaller.exe/TiWorker.exe).
- Dual-AV (Defender + third-party) → disable Defender via GPO.
- **Re-enable real-time protection after the window:** `Set-MpPreference -DisableRealtimeMonitoring $false`.
