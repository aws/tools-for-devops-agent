# SOP-053: Resolve Windows Patch Failure Due to Disk Space Exhaustion

| Field | Value |
|-------|-------|
| ID | SOP-053 |
| Category | windows_disk_space_exhaustion |
| Severity | High |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with `0x80070070` ("ERROR_DISK_FULL")
- `0x80070071` ("No more files") during update extraction
- `0x80070008` ("Not enough storage is available")
- CBS.log shows "insufficient disk space" errors
- Windows Update downloads succeed but installation fails
- TiWorker.exe crashes during component staging

## Root Cause

Windows requires significant temporary disk space for patching:

- C:\Windows\SoftwareDistribution\Download accumulates stale packages
- C:\Windows\WinSxS grows over time with superseded component versions
- C:\Windows\Temp fills with extraction artifacts from prior failed patches
- Previous Windows.old folder from feature updates consuming space
- IIS log files, crash dumps, or application logs consuming available space
- Cumulative updates on Server 2016+ require 10–15 GB free for staging

## Related Failure Patterns

- SOP-051 (Corrupt CBS) — failed writes due to disk full can corrupt CBS
- SOP-052 (WUA Hang) — insufficient space can cause WUA to hang during download

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No active patch installation in progress

## Diagnosis

```powershell
$c = Get-PSDrive C
Write-Output "C: Free=$([math]::Round($c.Free/1GB,2))GB Used=$([math]::Round($c.Used/1GB,2))GB"
Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | ForEach-Object { "SoftwareDistribution Download: $([math]::Round($_.Sum/1MB))MB" }
Get-ChildItem "$env:SystemRoot\Temp" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum | ForEach-Object { "Windows Temp: $([math]::Round($_.Sum/1MB))MB" }
```

## Remediation Steps

### Step 1: Check current disk space

```powershell
$c = Get-PSDrive C
$freeGB = [math]::Round($c.Free/1GB,2)
Write-Output "C: drive free space: ${freeGB}GB"
if ($freeGB -lt 5) { Write-Output "CRITICAL: Below 5GB threshold" }
```

Expected output: Free space reported
On failure: abort

### Step 2: Clear Windows Update download cache

```powershell
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
$before = (Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
$after = (Get-ChildItem "$env:SystemRoot\SoftwareDistribution\Download" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
Start-Service wuauserv -ErrorAction SilentlyContinue
Write-Output "Cleared $([math]::Round(($before - $after)/1MB))MB from SoftwareDistribution"
```

Expected output: Space cleared amount reported
On failure: continue

### Step 3: Clean Windows Temp folder (files older than 7 days)

```powershell
$cutoff = (Get-Date).AddDays(-7)
$old = Get-ChildItem "$env:SystemRoot\Temp" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -lt $cutoff }
$size = ($old | Measure-Object -Property Length -Sum).Sum
$old | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Output "Cleared $([math]::Round($size/1MB))MB from Windows Temp"
```

Expected output: Space cleared amount reported
On failure: continue

### Step 4: Run DISM component cleanup (superseded versions)

```powershell
# Run DISM under a bounded timeout so it cannot hang the maintenance window unattended.
# Launch it directly with -PassThru so on timeout we terminate ONLY this DISM child by PID, never every dism.exe on the host (a concurrent DISM must not be killed mid-transaction).
$out = [System.IO.Path]::GetTempFileName(); $err = [System.IO.Path]::GetTempFileName()
$proc = Start-Process -FilePath DISM -ArgumentList '/Online','/Cleanup-Image','/StartComponentCleanup' -PassThru -NoNewWindow -RedirectStandardOutput $out -RedirectStandardError $err
if ($proc.WaitForExit(1800000)) {
    (Get-Content $out, $err) | Select-String "operation completed|error"
    Write-Output "Component cleanup exit: $($proc.ExitCode)"
} else {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    # dism.exe is only a thin client; the actual servicing runs in TrustedInstaller/TiWorker out-of-process and is NOT stopped by killing the client
    Write-Output "Component cleanup: TIMEOUT - exceeded 1800s. The dism client was stopped, but TrustedInstaller/TiWorker servicing may still be running in the background - do NOT force a reboot; let servicing finish or escalate."
}
Remove-Item $out, $err -ErrorAction SilentlyContinue
```

Expected output: "Component cleanup exit: 0"
On failure: continue

### Step 5: Clear crash dumps and error reports

```powershell
$paths = @("$env:SystemRoot\Minidump", "$env:SystemRoot\MEMORY.DMP", "$env:LOCALAPPDATA\CrashDumps", "$env:ProgramData\Microsoft\Windows\WER")
$total = 0
foreach ($p in $paths) {
    if (Test-Path $p) {
        $item = Get-Item $p -Force
        if ($item.PSIsContainer) {
            $size = (Get-ChildItem $p -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
            Remove-Item "$p\*" -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            $size = $item.Length
            Remove-Item $p -Force -ErrorAction SilentlyContinue
        }
        $total += $size
    }
}
Write-Output "Cleared $([math]::Round($total/1MB))MB from dumps/WER"
```

Expected output: Space cleared amount reported
On failure: continue

### Step 6: Verify adequate free space

```powershell
$c = Get-PSDrive C
$freeGB = [math]::Round($c.Free/1GB,2)
if ($freeGB -ge 5) { Write-Output "DISK SPACE OK: ${freeGB}GB free" }
else { Write-Output "DISK SPACE INSUFFICIENT: ${freeGB}GB free (need 5GB+)" }
```

Expected output: "DISK SPACE OK"
On failure: abort

## Validation

```powershell
$c = Get-PSDrive C
$freeGB = [math]::Round($c.Free/1GB,2)
if ($freeGB -ge 5) { "DISK SPACE REMEDIATION OK: ${freeGB}GB free" } else { "STILL LOW: ${freeGB}GB" }
```

Expected: "DISK SPACE REMEDIATION OK"

## Rollback

No destructive changes — only cached/temporary files removed. No rollback needed.

## Escalation

If disk space cannot be recovered:
- Check for large IIS logs: `Get-ChildItem C:\inetpub\logs -Recurse | Measure-Object Length -Sum`
- Check for large application logs in C:\ProgramData
- Consider extending EBS volume if cleanup is insufficient
- For Server 2012 R2: WinSxS grows significantly — run `DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase`
- For Server 2016+: check if Windows.old exists from previous feature update
