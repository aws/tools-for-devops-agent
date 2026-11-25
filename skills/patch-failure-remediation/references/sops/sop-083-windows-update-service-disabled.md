# SOP-083: Resolve Windows Update Service Disabled Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-083 |
| Category | windows_update_service_disabled |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-23 |

## Symptoms

- Patch baseline scan/install fails because Windows Update service cannot start
- `0x80070422` ("The service cannot be started") during patch operations
- `Get-Service wuauserv` shows StartType: Disabled
- AWS-RunPatchBaseline exits with no patches scanned

## Root Cause

The Windows Update service (`wuauserv`) StartupType has been set to Disabled, preventing the patch baseline operation from starting it. Common causes:

- Hardening scripts or GPO intentionally disabled the service
- Administrator manually disabled to prevent auto-updates
- Third-party patch management tool disabled native Windows Update
- Server image/AMI was baked with the service disabled

Note: StartupType of Manual or Automatic with service Stopped is fine — SSM can start it. Only Disabled prevents operation.

## Related Failure Patterns

- SOP-052 (WU Service Hang) — service exists but is stuck
- SOP-056 (GPO Blocking) — GPO may re-disable after fix

## Prerequisites

- Instance reachable via SSM (PingStatus: Online)
- Requires customer approval if service was intentionally disabled

## Diagnosis

```powershell
Get-Service wuauserv | Select-Object Status, StartType
```

## Remediation Steps

### Step 1: Check current Windows Update service state

```powershell
$svc = Get-Service wuauserv
Write-Output "Status: $($svc.Status), StartType: $($svc.StartType)"
if ($svc.StartType -eq 'Disabled') { Write-Output "SERVICE IS DISABLED - requires fix" } else { Write-Output "StartType OK - issue is elsewhere" }
```

Expected output: Service state identified
On failure: abort

### Step 2: Enable and start the Windows Update service

```powershell
Set-Service -Name wuauserv -StartupType Automatic
Start-Service -Name wuauserv -ErrorAction SilentlyContinue
$svc = Get-Service wuauserv
Write-Output "StartType: $($svc.StartType), Status: $($svc.Status)"
if ($svc.StartType -ne 'Disabled') { Write-Output "WU SERVICE ENABLED" } else { Write-Output "FAILED TO ENABLE" }
```

Expected output: "WU SERVICE ENABLED"
On failure: abort

### Step 3: Verify patch scan can proceed

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
try { $result = $searcher.Search("IsInstalled=0 and Type='Software'"); Write-Output "SCAN OK: $($result.Updates.Count) updates found" } catch { Write-Output "SCAN FAILED: $($_.Exception.Message)" }
```

Expected output: "SCAN OK"
On failure: abort

## Validation

```powershell
$svc = Get-Service wuauserv
if ($svc.StartType -ne 'Disabled') { "WU SERVICE REMEDIATION OK" } else { "WU SERVICE REMEDIATION FAILED" }
```

Expected: "WU SERVICE REMEDIATION OK"

## Rollback

```powershell
Set-Service -Name wuauserv -StartupType Disabled
Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
Write-Output "wuauserv reverted to Disabled"
```

## Escalation

- If GPO re-disables the service on next refresh (~90 min), customer must fix the GPO
- If a third-party tool manages patching, coordinate with customer on coexistence
- Check if BITS service is also disabled — it's required for update downloads
