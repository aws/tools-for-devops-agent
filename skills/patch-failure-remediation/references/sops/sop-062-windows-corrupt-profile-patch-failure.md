# SOP-062: Resolve Windows Update Failure Due to Corrupt User Profile / SYSTEM Hive

| Field | Value |
|-------|-------|
| ID | SOP-062 |
| Category | windows_corrupt_profile_patch_failure |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x800704CF` ("The network location cannot be reached") during patch scan
- `0x80070002` ("The system cannot find the file specified") for update cache
- Windows Update agent runs under SYSTEM but Temp folder path is invalid
- CBS.log references non-existent user profile paths
- `%USERPROFILE%` for LocalSystem resolves to deleted or corrupt profile
- Patches fail with "Error writing to temporary folder"
- Environment variable expansion fails during update installation

## Root Cause

Windows Update relies on SYSTEM account profile and environment:

- SYSTEM profile's Temp/TMP folder deleted or permissions changed
- Default user profile (C:\Users\Default) corrupted
- ProfileList registry contains orphaned SID entries causing profile load delays
- NTUSER.DAT for Default profile corrupted
- Roaming profile GPO affecting SYSTEM account behavior
- Disk quota applied to SYSTEM account's profile folder
- Server 2012 R2: SID cleanup broke SYSTEM profile registry links

## Related Failure Patterns

- SOP-053 (Disk Space) — full disk can corrupt profile writes
- SOP-059 (DB Corruption) — profile issues can trigger DB write failures

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No active user sessions with profile issues (to avoid data loss)

## Diagnosis

```powershell
$systemTemp = [System.Environment]::GetEnvironmentVariable('TEMP', 'Machine')
$systemProfile = "$env:SystemRoot\System32\config\systemprofile"
Write-Output "SYSTEM Temp: $systemTemp"
Write-Output "SYSTEM Profile exists: $(Test-Path $systemProfile)"
Write-Output "SYSTEM Temp writable: $(Test-Path "$systemProfile\AppData\Local\Temp")"
Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList' -ErrorAction SilentlyContinue | Select-Object ProfilesDirectory
```

## Remediation Steps

### Step 1: Verify SYSTEM profile and Temp folder exist

```powershell
$systemProfile = "$env:SystemRoot\System32\config\systemprofile"
$tempPaths = @(
    "$systemProfile\AppData\Local\Temp",
    "$systemProfile\AppData\Local",
    "$systemProfile\AppData",
    "$systemProfile\Desktop"
)
foreach ($p in $tempPaths) {
    if (-not (Test-Path $p)) {
        New-Item $p -ItemType Directory -Force | Out-Null
        Write-Output "Created: $p"
    } else { Write-Output "OK: $p" }
}
```

Expected output: All paths verified/created
On failure: continue

### Step 2: Reset SYSTEM Temp folder permissions

```powershell
$tempPath = "$env:SystemRoot\System32\config\systemprofile\AppData\Local\Temp"
& icacls $tempPath /grant "SYSTEM:(OI)(CI)F" /T 2>&1 | Out-Null
& icacls $tempPath /grant "Administrators:(OI)(CI)F" /T 2>&1 | Out-Null
Write-Output "SYSTEM Temp permissions reset"
```

Expected output: "SYSTEM Temp permissions reset"
On failure: continue

### Step 3: Clear orphaned profile list entries

```powershell
$profileList = Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'
$orphaned = 0
foreach ($p in $profileList) {
    $imagePath = (Get-ItemProperty $p.PSPath -Name ProfileImagePath -ErrorAction SilentlyContinue).ProfileImagePath
    if ($imagePath -and -not (Test-Path $imagePath) -and $imagePath -notmatch 'systemprofile|ServiceProfiles') {
        Write-Output "Orphaned: $imagePath"
        $orphaned++
    }
}
Write-Output "Orphaned profile entries: $orphaned"
```

Expected output: Orphan count reported
On failure: continue

### Step 4: Verify Default user profile integrity

```powershell
$defaultProfile = "$env:SystemDrive\Users\Default"
$requiredPaths = @("$defaultProfile\AppData\Local\Temp", "$defaultProfile\Desktop", "$defaultProfile\Documents")
foreach ($p in $requiredPaths) {
    if (-not (Test-Path $p)) {
        New-Item $p -ItemType Directory -Force | Out-Null
        Write-Output "Restored: $p"
    }
}
# Check NTUSER.DAT
if (Test-Path "$defaultProfile\NTUSER.DAT") { Write-Output "Default NTUSER.DAT: OK" }
else { Write-Output "WARNING: Default NTUSER.DAT missing" }
```

Expected output: Default profile verified
On failure: continue

### Step 5: Validate SYSTEM can write to Temp

```powershell
$tempPath = "$env:SystemRoot\System32\config\systemprofile\AppData\Local\Temp"
$testFile = Join-Path $tempPath "wu_test_$(Get-Random).tmp"
try {
    [System.IO.File]::WriteAllText($testFile, "test")
    Remove-Item $testFile -Force
    Write-Output "PROFILE REMEDIATION OK: SYSTEM write access confirmed"
} catch {
    Write-Output "PROFILE ISSUE: $($_.Exception.Message)"
}
```

Expected output: "PROFILE REMEDIATION OK"
On failure: abort

## Validation

```powershell
$tempPath = "$env:SystemRoot\System32\config\systemprofile\AppData\Local\Temp"
$canWrite = $false
try { [System.IO.File]::WriteAllText("$tempPath\verify.tmp","ok"); Remove-Item "$tempPath\verify.tmp" -Force; $canWrite = $true } catch {}
if ($canWrite -and (Test-Path $tempPath)) { "PROFILE REMEDIATION OK" } else { "PROFILE STILL BROKEN" }
```

Expected: "PROFILE REMEDIATION OK"

## Rollback

Profile folder creation and permission fixes are non-destructive. No rollback needed.

## Escalation

If SYSTEM profile issues persist:
- Check if roaming profile GPO is affecting SYSTEM: `gpresult /SCOPE COMPUTER /V`
- For missing NTUSER.DAT in Default profile: copy from a working instance of same OS version
- If ProfileList registry is severely corrupted: export, clean, and re-import
- For Server 2012 R2: check if SID-to-name resolution is failing (domain trust issue)
- Consider rebuilding SYSTEM profile from Windows install media
