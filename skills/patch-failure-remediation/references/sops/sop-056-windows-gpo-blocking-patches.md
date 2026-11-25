# SOP-056: Resolve Windows Group Policy Blocking Patch Installation

| Field | Value |
|-------|-------|
| ID | SOP-056 |
| Category | windows_gpo_blocking_patches |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Windows Update configured to "Never check for updates" via GPO
- `0x8024002E` ("WU_E_WU_DISABLED") — Windows Update disabled by policy
- Patches download but never install (NoAutoUpdate = 1)
- WSUS GPO pointing to decommissioned/incorrect WSUS server
- Windows Update reports "Some settings are managed by your organization"
- Scan succeeds but installation blocked with access denied

## Root Cause

Group Policy overrides prevent patching when:

- `NoAutoUpdate` registry value set to 1 by domain GPO
- `DisableWindowsUpdateAccess` set to 1 blocking all WU operations
- `WUServer` / `WUStatusServer` pointing to unreachable WSUS server
- `DoNotConnectToWindowsUpdateInternetLocations` blocking direct Microsoft Update
- GPO sets `AUOptions` to "Notify" only but SSM expects "Auto Install"
- Domain-joined instance inherits stale GPO from OU no longer appropriate
- Server 2012 R2: WSUS server TLS settings incompatible after domain policy change

## Related Failure Patterns

- SOP-021 (WSUS Unreachable) — WSUS GPO pointing to wrong server
- SOP-024 (TLS Failure) — GPO-enforced TLS version blocking WSUS communication

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding that changes may be reverted on next GPO refresh (every 90 minutes)

## Diagnosis

```powershell
$wuPolicy = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue
$auPolicy = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
Write-Output "WUServer: $($wuPolicy.WUServer)"
Write-Output "NoAutoUpdate: $($auPolicy.NoAutoUpdate)"
Write-Output "UseWUServer: $($auPolicy.UseWUServer)"
Write-Output "DisableWindowsUpdateAccess: $($wuPolicy.DisableWindowsUpdateAccess)"
```

## Remediation Steps

### Step 1: Identify blocking GPO settings

```powershell
$wu = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue
$au = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
$blocks = @()
if ($au.NoAutoUpdate -eq 1) { $blocks += "NoAutoUpdate=1" }
if ($wu.DisableWindowsUpdateAccess -eq 1) { $blocks += "DisableWindowsUpdateAccess=1" }
if ($au.UseWUServer -eq 1 -and $wu.WUServer) { $blocks += "WSUS=$($wu.WUServer)" }
if ($wu.DoNotConnectToWindowsUpdateInternetLocations -eq 1) { $blocks += "NoInternetWU=1" }
Write-Output "Blocking policies: $($blocks -join ', ')"
if ($blocks.Count -eq 0) { Write-Output "NO BLOCKING POLICIES FOUND" }
```

Expected output: Blocking policies identified
On failure: abort

### Step 2: Temporarily disable NoAutoUpdate if set

```powershell
$auPath = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
if (Test-Path $auPath) {
    $val = (Get-ItemProperty $auPath -Name NoAutoUpdate -ErrorAction SilentlyContinue).NoAutoUpdate
    if ($val -eq 1) {
        Set-ItemProperty $auPath -Name NoAutoUpdate -Value 0
        Write-Output "NoAutoUpdate cleared (was 1)"
    } else { Write-Output "NoAutoUpdate already not blocking" }
} else { Write-Output "No AU policy path exists" }
```

Expected output: NoAutoUpdate status
On failure: continue

### Step 3: Disable DisableWindowsUpdateAccess if set

```powershell
$wuPath = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
if (Test-Path $wuPath) {
    $val = (Get-ItemProperty $wuPath -Name DisableWindowsUpdateAccess -ErrorAction SilentlyContinue).DisableWindowsUpdateAccess
    if ($val -eq 1) {
        Set-ItemProperty $wuPath -Name DisableWindowsUpdateAccess -Value 0
        Write-Output "DisableWindowsUpdateAccess cleared"
    } else { Write-Output "WU access not disabled by policy" }
} else { Write-Output "No WU policy path" }
```

Expected output: Policy cleared or not blocking
On failure: continue

### Step 4: Override WSUS to allow direct Microsoft Update (if WSUS unreachable)

```powershell
$wuPath = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
if (Test-Path $wuPath) {
    $useWsus = (Get-ItemProperty $wuPath -Name UseWUServer -ErrorAction SilentlyContinue).UseWUServer
    if ($useWsus -eq 1) {
        Set-ItemProperty $wuPath -Name UseWUServer -Value 0
        Write-Output "UseWUServer disabled — will use Microsoft Update directly"
    } else { Write-Output "Not using WSUS policy" }
} else { Write-Output "No AU policy path" }
```

Expected output: WSUS override status
On failure: continue

### Step 5: Restart Windows Update to apply changes

```powershell
Restart-Service wuauserv -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
Write-Output "GPO OVERRIDE APPLIED - WUA restarted"
```

Expected output: "GPO OVERRIDE APPLIED - WUA restarted"
On failure: abort

## Validation

```powershell
$au = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -ErrorAction SilentlyContinue
$wu = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -ErrorAction SilentlyContinue
$blocked = ($au.NoAutoUpdate -eq 1) -or ($wu.DisableWindowsUpdateAccess -eq 1)
if (-not $blocked) { "GPO REMEDIATION OK" } else { "STILL BLOCKED BY POLICY" }
```

Expected: "GPO REMEDIATION OK"

## Rollback

```powershell
# Force GPO refresh to restore original policy
& gpupdate /force 2>&1 | Out-Null
Write-Output "GPO refreshed — original domain policies restored"
```

## Escalation

If GPO continues to block:
- Changes will be reverted on next group policy refresh (~90 min or at reboot)
- Contact customer AD/GPO team to fix policy for patching OU
- For non-domain instances: check local policy via `gpedit.msc`
- Consider moving the instance to a patching-friendly OU
- For Server 2012 R2 domain-joined: dual-scan may need to be enabled (`DisableDualScan = 0`)
- Verify no Intune/MDM policies overriding Windows Update settings (Server 2019+)
