# SOP-059: Resolve Windows Update Database Corruption (esent/DataStore.edb)

| Field | Value |
|-------|-------|
| ID | SOP-059 |
| Category | windows_update_database_corruption |
| Severity | High |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x8024400A` ("WU_E_PT_SOAPCLIENT_PARSE") on scan
- `0x80244010` ("WU_E_PT_EXCEEDED_MAX_SERVER_TRIPS")
- `0x8007000E` ("E_OUTOFMEMORY") during Windows Update scan
- Windows Update scan takes extremely long (>2 hours)
- svchost.exe WUA process consuming >2GB RAM during scan
- Event ID 455/489 from ESENT in Application log referencing DataStore.edb
- DataStore.edb file size >1GB (normally 10-100MB)

## Root Cause

The Windows Update database (DataStore.edb) becomes corrupted when:

- Power loss or forced shutdown during update scan write operations
- Database journal file (edb.log) inconsistent with main database
- Excessive WUA scan history accumulated over years without cleanup
- Disk I/O errors during transaction commit to DataStore.edb
- WUA process killed during active database transaction
- Server 2012 R2: ESENT database engine bug with large update catalogs
- Antivirus scanning DataStore.edb during active write operations

## Related Failure Patterns

- SOP-052 (WUA Hang) — DB corruption can present as service hang
- SOP-053 (Disk Space) — large DataStore.edb contributes to disk usage

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No active Windows Update scan in progress

## Diagnosis

```powershell
$dbPath = "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb"
if (Test-Path $dbPath) {
    $size = (Get-Item $dbPath).Length
    Write-Output "DataStore.edb size: $([math]::Round($size/1MB,1))MB"
}
Get-WinEvent -LogName Application -MaxEvents 20 | Where-Object { $_.ProviderName -eq 'ESENT' -and $_.Level -le 3 } | Select-Object TimeCreated,Id,Message | Format-List
```

## Remediation Steps

### Step 1: Check DataStore.edb health indicators

```powershell
$dbPath = "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb"
$logPath = "$env:SystemRoot\SoftwareDistribution\DataStore\Logs"
$dbSize = if (Test-Path $dbPath) { [math]::Round((Get-Item $dbPath).Length/1MB,1) } else { 0 }
$logCount = if (Test-Path $logPath) { (Get-ChildItem $logPath -Filter "*.log" -ErrorAction SilentlyContinue).Count } else { 0 }
Write-Output "DataStore.edb: ${dbSize}MB, Log files: $logCount"
$esent = Get-WinEvent -LogName Application -MaxEvents 100 -ErrorAction SilentlyContinue | Where-Object { $_.ProviderName -eq 'ESENT' -and $_.Level -le 3 }
Write-Output "Recent ESENT errors: $($esent.Count)"
```

Expected output: Database size and error count
On failure: continue

### Step 2: Stop Windows Update service

```powershell
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 5
$s = Get-Service wuauserv
if ($s.Status -eq 'Stopped') { Write-Output "WUA stopped" }
else { $wuPid = (Get-CimInstance Win32_Service -Filter "Name='wuauserv'").ProcessId; if ($wuPid -and $wuPid -ne 0) { Stop-Process -Id $wuPid -Force -ErrorAction SilentlyContinue }; Write-Output "WUA force-killed" }
```

Expected output: "WUA stopped"
On failure: continue

### Step 3: Rename corrupt DataStore folder

```powershell
$ds = "$env:SystemRoot\SoftwareDistribution\DataStore"
$backup = "$env:SystemRoot\SoftwareDistribution\DataStore.old_$(Get-Date -Format 'yyyyMMdd')"
if (Test-Path $ds) {
    Rename-Item $ds $backup -Force
    Write-Output "DataStore renamed to $backup"
} else { Write-Output "No DataStore folder found" }
```

Expected output: "DataStore renamed"
On failure: abort — database file may be locked

### Step 4: Clear download cache to force fresh state

```powershell
$dl = "$env:SystemRoot\SoftwareDistribution\Download"
if (Test-Path $dl) {
    Remove-Item "$dl\*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Output "Download cache cleared"
} else { Write-Output "No download folder" }
```

Expected output: "Download cache cleared"
On failure: continue

### Step 5: Restart Windows Update service (rebuilds database)

```powershell
Start-Service wuauserv -ErrorAction SilentlyContinue
Start-Sleep -Seconds 10
$s = Get-Service wuauserv
$newDb = "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb"
$exists = Test-Path $newDb
Write-Output "WUA status: $($s.Status), New DB created: $exists"
if ($s.Status -eq 'Running' -or $exists) { Write-Output "DATABASE REBUILD OK" }
else { Write-Output "DATABASE REBUILD ISSUE" }
```

Expected output: "DATABASE REBUILD OK"
On failure: abort

## Validation

```powershell
$dbPath = "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb"
$svc = Get-Service wuauserv
if ((Test-Path $dbPath) -and ($svc.Status -eq 'Running' -or $svc.Status -eq 'Stopped')) {
    $size = [math]::Round((Get-Item $dbPath).Length/1MB,1)
    "DATABASE REMEDIATION OK: New DB ${size}MB"
} else { "DATABASE ISSUE: Check WUA service" }
```

Expected: "DATABASE REMEDIATION OK"

## Rollback

```powershell
$backup = Get-ChildItem "$env:SystemRoot\SoftwareDistribution" -Filter "DataStore.old_*" -Directory | Sort-Object Name -Descending | Select-Object -First 1
if ($backup) {
    Stop-Service wuauserv -Force
    Remove-Item "$env:SystemRoot\SoftwareDistribution\DataStore" -Recurse -Force -ErrorAction SilentlyContinue
    Rename-Item $backup.FullName "$env:SystemRoot\SoftwareDistribution\DataStore"
    Start-Service wuauserv
    "DataStore restored from backup"
} else { "No backup DataStore found" }
```

## Escalation

If database rebuild doesn't resolve:
- Delete entire SoftwareDistribution folder and let WUA recreate: `Rename-Item $env:SystemRoot\SoftwareDistribution SoftwareDistribution.bak`
- Check disk health: `Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,OperationalStatus`
- If ESENT errors persist after rebuild: check for disk I/O errors in System event log
- For Server 2012 R2: bloated scan times are often resolved by installing latest Monthly Rollup manually
- Consider running `esentutl /d DataStore.edb` for defragmentation on very large databases
