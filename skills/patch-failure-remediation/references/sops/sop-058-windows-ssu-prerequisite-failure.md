# SOP-058: Resolve Windows Servicing Stack Update (SSU) Prerequisite Failure

| Field | Value |
|-------|-------|
| ID | SOP-058 |
| Category | windows_ssu_prerequisite_failure |
| Severity | High |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Cumulative Update fails with `0x80070BC9` ("ERROR_FAIL_NOACTION_REBOOT")
- `0x80073701` ("ERROR_SXS_ASSEMBLY_MISSING") on LCU installation
- Monthly cumulative update repeatedly fails but SSU is outdated
- CBS.log shows "Servicing stack must be updated before this package can be installed"
- Windows Update downloads LCU but fails at "Installing" phase
- Server 2016 stuck on old cumulative update due to SSU mismatch

## Root Cause

Servicing Stack Updates (SSU) must be current before Latest Cumulative Updates (LCU) can install:

- SSU is severely outdated relative to the target LCU
- Previous SSU installation was incomplete (interrupted reboot)
- Server 2016/2019: SSU and LCU were separate until recent combined packages
- WSUS approved the LCU but not the prerequisite SSU
- CBS cannot process the update manifest with an old servicing stack
- Server 2012 R2: requires specific SSU chain before latest monthly rollup

## Related Failure Patterns

- SOP-051 (Corrupt CBS) — outdated SSU can manifest as CBS corruption
- SOP-052 (WUA Hang) — old SSU causes TiWorker hangs on new updates
- SOP-021 (WSUS Unreachable) — WSUS may not have approved SSU

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance has internet access or WSUS has SSU approved

## Diagnosis

```powershell
$ssu = Get-HotFix | Where-Object { $_.Description -eq 'Update' -and $_.HotFixID -match 'KB5' } | Sort-Object InstalledOn -Descending | Select-Object -First 5
$ssu | ForEach-Object { Write-Output "$($_.HotFixID) installed $($_.InstalledOn)" }
$os = (Get-CimInstance Win32_OperatingSystem).BuildNumber
Write-Output "OS Build: $os"
```

## Remediation Steps

### Step 1: Identify current OS build and installed servicing stack

```powershell
$os = Get-CimInstance Win32_OperatingSystem
$build = "$($os.Version) (Build $($os.BuildNumber).$((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR))"
Write-Output "OS: $($os.Caption) - $build"
$ssuKey = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Version' -ErrorAction SilentlyContinue
if ($ssuKey) { Write-Output "SSU Version: $($ssuKey.'(default)')" }
```

Expected output: OS and SSU version reported
On failure: continue

### Step 2: Check if combined SSU+LCU is available (Server 2019+)

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$results = $searcher.Search("IsInstalled=0 and Type='Software'").Updates
$ssuUpdates = $results | Where-Object { $_.Title -match 'Servicing Stack' }
$lcuUpdates = $results | Where-Object { $_.Title -match 'Cumulative Update' -and $_.Title -notmatch 'Servicing' }
Write-Output "Pending SSU: $($ssuUpdates.Count), Pending LCU: $($lcuUpdates.Count)"
if ($ssuUpdates.Count -gt 0) { $ssuUpdates | ForEach-Object { Write-Output "  SSU: $($_.Title)" } }
```

Expected output: SSU and LCU counts
On failure: continue

### Step 3: Install SSU first if pending

```powershell
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$ssuUpdates = $searcher.Search("IsInstalled=0 and Type='Software'").Updates | Where-Object { $_.Title -match 'Servicing Stack' }
if ($ssuUpdates.Count -gt 0) {
    $downloader = $session.CreateUpdateDownloader()
    $toInstall = New-Object -ComObject Microsoft.Update.UpdateColl
    foreach ($u in $ssuUpdates) { $toInstall.Add($u) | Out-Null }
    $downloader.Updates = $toInstall
    $downloader.Download() | Out-Null
    $installer = $session.CreateUpdateInstaller()
    $installer.Updates = $toInstall
    $result = $installer.Install()
    Write-Output "SSU install result: $($result.ResultCode) (2=Succeeded, 3=SucceededWithErrors)"
} else { Write-Output "No SSU pending — servicing stack may already be current" }
```

Expected output: "SSU install result: 2" or "No SSU pending"
On failure: continue

### Step 4: Trigger component store re-evaluation

```powershell
# Run DISM under a bounded timeout so it cannot hang the maintenance window unattended.
# Launch it directly with -PassThru so on timeout we terminate ONLY this DISM child by PID, never every dism.exe on the host (a concurrent DISM must not be killed mid-transaction).
$out = [System.IO.Path]::GetTempFileName(); $err = [System.IO.Path]::GetTempFileName()
$proc = Start-Process -FilePath DISM -ArgumentList '/Online','/Cleanup-Image','/StartComponentCleanup' -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
if ($proc.WaitForExit(1800000)) {
    (Get-Content $out, $err) | Select-String "operation completed|error"
    Write-Output "Component cleanup done (exit $($proc.ExitCode))"
} else {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    # dism.exe is only a thin client; the actual servicing runs in TrustedInstaller/TiWorker out-of-process and is NOT stopped by killing the client
    Write-Output "Component cleanup: TIMEOUT - exceeded 1800s. The dism client was stopped, but TrustedInstaller/TiWorker servicing may still be running in the background - do NOT force a reboot; let servicing finish or escalate."
}
Remove-Item $out, $err -ErrorAction SilentlyContinue
```

Expected output: "Component cleanup done"
On failure: continue

### Step 5: Verify SSU is installed and LCU can proceed

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$ssuPending = $searcher.Search("IsInstalled=0 and Type='Software'").Updates | Where-Object { $_.Title -match 'Servicing Stack' }
if ($ssuPending.Count -eq 0) { Write-Output "SSU CURRENT - LCU ready to install" }
else { Write-Output "SSU STILL PENDING: $($ssuPending.Count) SSU update(s)" }
```

Expected output: "SSU CURRENT - LCU ready to install"
On failure: abort

## Validation

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$ssu = $searcher.Search("IsInstalled=0 and Type='Software'").Updates | Where-Object { $_.Title -match 'Servicing Stack' }
if ($ssu.Count -eq 0) { "SSU REMEDIATION OK" } else { "SSU STILL NEEDED: $($ssu.Count)" }
```

Expected: "SSU REMEDIATION OK"

## Rollback

SSU installations cannot be uninstalled. They are forward-only updates to the Windows servicing infrastructure.

## Escalation

If SSU cannot install:
- For Server 2012 R2: manually download SSU from Microsoft Update Catalog and install via `wusa.exe`
- For Server 2016: certain LCUs require a specific SSU version — check KB article prerequisites
- If WSUS is in use: ensure SSU is approved in WSUS before the LCU
- For combined SSU+LCU packages (2019+): ensure the combined package is being offered
- Check if SafeOS update is also needed (for WinRE patching requirements since 2024)
