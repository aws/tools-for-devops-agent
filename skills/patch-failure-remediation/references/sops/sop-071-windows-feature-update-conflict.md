# SOP-071: Resolve Windows Patch Failure Due to Feature Update / In-Place Upgrade Conflict

| Field | Value |
|-------|-------|
| ID | SOP-071 |
| Category | windows_feature_update_conflict |
| Severity | High |
| Risk Level | High |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 600 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0xC1900101` ("SAFE_OS" or "SECOND_BOOT" phase failures)
- `0x80240020` ("WU_E_NO_INTERACTIVE_USER") during feature update
- `0x80070490` ("ERROR_NOT_FOUND") after partial feature update
- System stuck between OS versions after failed upgrade
- Windows.old folder present with no matching upgrade completion
- Cumulative updates fail with "not applicable to this image"
- OS reports unexpected build number

## Root Cause

Feature update conflicts during patching when:

- In-place upgrade (e.g., 2016→2019) was started but never completed
- Feature update left Windows.old and $WINDOWS.~BT folders in inconsistent state
- LCU targets a different OS version than actually installed
- System image was captured mid-upgrade and deployed
- Upgrade rollback occurred but CBS state not fully reset
- Server SAC to LTSC conversion left mixed package state
- Group Policy offering feature updates not appropriate for server

## Related Failure Patterns

- SOP-065 (Pending Transactions) — upgrade leaves pending servicing
- SOP-053 (Disk Space) — Windows.old consuming critical space
- SOP-051 (CBS Corruption) — upgrade corruption of component store

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Confirm actual OS version vs expected version before remediation

## Diagnosis

```powershell
$os = Get-CimInstance Win32_OperatingSystem
Write-Output "Caption: $($os.Caption)"
Write-Output "Version: $($os.Version)"
Write-Output "Build: $($os.BuildNumber)"
$ubr = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR
Write-Output "UBR: $ubr"
Write-Output "Windows.old exists: $(Test-Path 'C:\Windows.old')"
Write-Output "WINDOWS.~BT exists: $(Test-Path 'C:\$WINDOWS.~BT')"
$upgradeReg = Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name 'UpgradeInProgress' -ErrorAction SilentlyContinue
Write-Output "Upgrade in progress flag: $($upgradeReg.UpgradeInProgress)"
```

## Remediation Steps

### Step 1: Verify actual OS version and build state

```powershell
$nt = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
Write-Output "Product: $($nt.ProductName)"
Write-Output "Build: $($nt.CurrentBuildNumber).$($nt.UBR)"
Write-Output "Edition: $($nt.EditionID)"
Write-Output "Install type: $($nt.InstallationType)"
$upgradeKeys = @(
    @{Path='HKLM:\SYSTEM\Setup'; Name='UpgradeInProgress'},
    @{Path='HKLM:\SYSTEM\Setup'; Name='SetupType'}
)
foreach ($k in $upgradeKeys) {
    $val = (Get-ItemProperty $k.Path -Name $k.Name -ErrorAction SilentlyContinue).$($k.Name)
    Write-Output "$($k.Name): $val"
}
```

Expected output: OS version and upgrade state
On failure: continue

### Step 2: Clear stale upgrade-in-progress flags

```powershell
$setupReg = 'HKLM:\SYSTEM\Setup'
$flags = @('UpgradeInProgress', 'SetupType')
foreach ($f in $flags) {
    $val = (Get-ItemProperty $setupReg -Name $f -ErrorAction SilentlyContinue).$f
    if ($val -and $val -ne 0) {
        Set-ItemProperty $setupReg -Name $f -Value 0
        Write-Output "Cleared $f (was $val)"
    }
}
Write-Output "Upgrade flags cleared"
```

Expected output: "Upgrade flags cleared"
On failure: continue

### Step 3: Remove stale upgrade staging folders

```powershell
$stagingPaths = @('C:\$WINDOWS.~BT', 'C:\$WINDOWS.~WS', 'C:\$Windows.~LS')
$freed = 0
foreach ($p in $stagingPaths) {
    if (Test-Path $p) {
        $size = (Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        Remove-Item $p -Recurse -Force -ErrorAction SilentlyContinue
        $freed += $size
        Write-Output "Removed: $p ($([math]::Round($size/1GB,2))GB)"
    }
}
if ($freed -eq 0) { Write-Output "No upgrade staging folders found" }
else { Write-Output "Freed $([math]::Round($freed/1GB,2))GB from staging" }
```

Expected output: Staging cleanup status
On failure: continue

### Step 4: Verify Windows Update targets correct OS version

```powershell
$build = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuildNumber
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$updates = $searcher.Search("IsInstalled=0 and Type='Software'").Updates
$mismatch = $updates | Where-Object { $_.Title -match "Version \d+" -and $_.Title -notmatch $build }
if ($mismatch.Count -gt 0) {
    Write-Output "WARNING: $($mismatch.Count) update(s) targeting different build"
    $mismatch | ForEach-Object { Write-Output "  $($_.Title)" }
} else { Write-Output "All pending updates target current build $build" }
```

Expected output: Update targeting confirmation
On failure: continue

### Step 5: Run DISM to confirm component store consistency

```powershell
$result = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
if ($result -match "healthy") { Write-Output "FEATURE UPDATE CONFLICT REMEDIATION OK" }
else { Write-Output "CBS ISSUE: $($result | Select-String 'repairable|corrupted')" }
```

Expected output: "FEATURE UPDATE CONFLICT REMEDIATION OK"
On failure: abort

## Validation

```powershell
$upgradeFlag = (Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name 'UpgradeInProgress' -ErrorAction SilentlyContinue).UpgradeInProgress
$staging = Test-Path 'C:\$WINDOWS.~BT'
$health = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
if (-not $upgradeFlag -and -not $staging -and $health -match "healthy") { "FEATURE UPDATE REMEDIATION OK" }
else { "ISSUES REMAIN: Upgrade=$upgradeFlag Staging=$staging" }
```

Expected: "FEATURE UPDATE REMEDIATION OK"

## Rollback

Upgrade staging folder removal is irreversible but does not affect the running OS. If a feature update is genuinely needed, it must be re-initiated.

## Escalation

If feature update conflict cannot be resolved:
- If Windows.old exists and system is on wrong build: rollback may be possible within 10 days
- For stuck-between-versions: in-place upgrade repair install is typically required
- Check if WSUS/SCCM is offering feature updates to servers (should not for LTSC)
- For Server 2016→2019 migrations: ensure complete migration or clean install
- If CBS reports current build but packages reference old build: `DISM /Online /Cleanup-Image /RestoreHealth`
- Consider rebuilding from AMI if OS is in fundamentally inconsistent state
