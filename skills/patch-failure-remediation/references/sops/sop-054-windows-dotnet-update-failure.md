# SOP-054: Resolve Windows .NET Framework Update Failure

| Field | Value |
|-------|-------|
| ID | SOP-054 |
| Category | windows_dotnet_update_failure |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- .NET Framework security update fails repeatedly
- `0x80070643` ("Fatal error during installation") for .NET patches
- `0x80096004` ("The signed cryptographic message or certificate is invalid") on .NET updates
- KB article for .NET update shows "Failed" in patch compliance
- Windows Update succeeds for all patches except .NET Framework updates
- Event log shows .NET Framework Setup errors (Source: .NETRuntime or NGen)

## Root Cause

.NET Framework patches fail when:

- .NET Framework installation is partially corrupted
- NGen (Native Image Generator) cache is out of sync
- Previous .NET update left pending file operations incomplete
- .NET optimization service (mscorsvw.exe) is hung or crashed
- Multiple .NET versions have conflicting shared assemblies
- .NET Setup cleanup tool was previously run leaving orphaned entries
- Server 2012 R2 specific: .NET 4.5/4.6 in-place upgrade conflicts

## Related Failure Patterns

- SOP-051 (Corrupt CBS) — .NET is a Windows component, CBS corruption affects it
- SOP-052 (WUA Hang) — .NET optimization can block WUA

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No .NET applications actively compiling or running NGen tasks

## Diagnosis

```powershell
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse | Get-ItemProperty -Name Version -ErrorAction SilentlyContinue | Select-Object PSChildName,Version
Get-WinEvent -LogName Application -MaxEvents 20 | Where-Object { $_.ProviderName -match 'NGen|\.NET' -and $_.Level -le 3 } | Select-Object TimeCreated,Message
```

## Remediation Steps

### Step 1: Identify installed .NET versions

```powershell
$versions = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse | Get-ItemProperty -Name Version,Release -ErrorAction SilentlyContinue | Where-Object { $_.Version } | Select-Object PSChildName,Version
$versions | ForEach-Object { Write-Output "$($_.PSChildName): $($_.Version)" }
Write-Output "Found $($versions.Count) .NET entries"
```

Expected output: .NET versions listed
On failure: continue

### Step 2: Stop .NET optimization service

```powershell
# Stop NGen via its owning service rather than force-killing every mscorsvw on the host:
# a blanket kill can interrupt legitimate NGen compilation for other applications.
# Stopping clr_optimization_* cleanly terminates the mscorsvw workers it owns.
Stop-Service clr_optimization_v4.0.30319_64,clr_optimization_v4.0.30319_32 -Force -ErrorAction SilentlyContinue
Write-Output "NGen optimization stopped"
```

Expected output: "NGen optimization stopped"
On failure: continue

### Step 3: Clear NGen cache and re-queue compilation

```powershell
$ngen64 = "$env:SystemRoot\Microsoft.NET\Framework64\v4.0.30319\ngen.exe"
$ngen32 = "$env:SystemRoot\Microsoft.NET\Framework\v4.0.30319\ngen.exe"
if (Test-Path $ngen64) { & $ngen64 update /force 2>&1 | Select-Object -Last 3 }
if (Test-Path $ngen32) { & $ngen32 update /force 2>&1 | Select-Object -Last 3 }
Write-Output "NGen cache updated"
```

Expected output: "NGen cache updated"
On failure: continue

### Step 4: Repair .NET Framework using DISM

```powershell
$feature = & DISM /Online /Get-Features 2>&1 | Select-String "NetFx"
if ($feature) {
    # Run the long-running DISM feature enablement under a bounded timeout so it cannot hang unattended.
    # Launch it directly with -PassThru so on timeout we terminate ONLY this DISM child by PID, never every dism.exe on the host (a concurrent DISM must not be killed mid-transaction).
    $out = [System.IO.Path]::GetTempFileName(); $err = [System.IO.Path]::GetTempFileName()
    $proc = Start-Process -FilePath DISM -ArgumentList '/Online','/Enable-Feature','/FeatureName:NetFx4','/All' -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
    if ($proc.WaitForExit(1800000)) {
        (Get-Content $out, $err) | Select-String "operation completed|already enabled|error"
        Write-Output "DISM .NET repair exit: $($proc.ExitCode)"
    } else {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        # dism.exe is only a thin client; the actual servicing runs in TrustedInstaller/TiWorker out-of-process and is NOT stopped by killing the client
        Write-Output "DISM .NET repair: TIMEOUT - exceeded 1800s. The dism client was stopped, but TrustedInstaller/TiWorker servicing may still be running in the background - do NOT force a reboot; let servicing finish or escalate."
    }
    Remove-Item $out, $err -ErrorAction SilentlyContinue
} else {
    Write-Output "DISM .NET repair exit: $LASTEXITCODE"
}
```

Expected output: "DISM .NET repair exit: 0"
On failure: if DISM returned a non-zero exit code, continue. **If the output was a TIMEOUT, stop here** — TrustedInstaller/TiWorker servicing is still active in the background, so do NOT run Step 5 (it stops `wuauserv` and clears `SoftwareDistribution\Download`, which would contend with the in-flight servicing and can corrupt state). Wait for servicing to finish (or reboot per change policy) or escalate.

### Step 5: Reset Windows Update state and validate readiness

```powershell
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
Start-Service wuauserv
Write-Output ".NET UPDATE BLOCKER RESOLVED - ready for next patch cycle"
```

Expected output: ".NET UPDATE BLOCKER RESOLVED - ready for next patch cycle"
On failure: abort

## Validation

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$pending = $searcher.Search("IsInstalled=0 and Type='Software'").Updates | Where-Object { $_.Title -match '\.NET|Framework' }
if ($pending.Count -eq 0) { "DOTNET PATCHES OK: No pending .NET updates" }
else { "DOTNET PATCHES PENDING: $($pending.Count) .NET update(s) still needed" }
```

Expected: "DOTNET PATCHES OK" or reduced pending count after next patch cycle

## Rollback

```powershell
Start-Service clr_optimization_v4.0.30319_64,clr_optimization_v4.0.30319_32 -ErrorAction SilentlyContinue
Write-Output "NGen services restarted - no destructive changes made"
```

## Escalation

If .NET updates continue to fail:
- Run .NET Framework Repair Tool (Microsoft downloadable)
- For Server 2012 R2: may need to uninstall/reinstall .NET 4.x
- Check if ASP.NET IIS registration is corrupted: `aspnet_regiis -ir`
- For Server 2016+: .NET 4.6+ is an OS component — use `DISM /Online /Cleanup-Image /RestoreHealth`
- Consider installing latest .NET cumulative update manually via standalone installer
