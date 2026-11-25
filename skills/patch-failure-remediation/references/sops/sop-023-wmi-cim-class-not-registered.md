# SOP-023: Resolve WMI/CIM Failure During Patching (`HRESULT 0x80040154`)

| Field | Value |
|-------|-------|
| ID | SOP-023 |
| Category | wmi_cim_class_not_registered |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | No (unless WMI repository rebuild requires it) |
| Estimated Duration | 240 seconds |
| Last Validated | 2026-06-12 |

## Symptoms

- Patch fails with `+ FullyQualifiedErrorId : HRESULT 0x80040154,Microsoft.Management.Infrastructure.CimCmdlets.GetCimInstanceCommand`
- `0x80040154` = `REGDB_E_CLASSNOTREG` ("Class not registered")
- The failure occurs while the patch baseline operation queries the system via CIM/WMI (e.g., `Get-CimInstance`), before or during install
- Patch command exits non-zero; pre-patch validation may pass or fail depending on where the CIM call occurs

## Root Cause

The patch baseline operation relies on **WMI/CIM** to query OS and update state (via `Get-CimInstance` and related calls). `HRESULT 0x80040154 (REGDB_E_CLASSNOTREG)` means a required **COM/WMI class is not registered** on the instance, so the CIM query fails and the patch operation aborts. Common underlying causes:

- A corrupt or unhealthy **WMI repository** (`%WINDIR%\System32\wbem\Repository`)
- WMI provider DLLs unregistered or missing (incomplete update, third-party software uninstall, image drift)
- The `Winmgmt` (Windows Management Instrumentation) service stopped or unhealthy
- A recent failed servicing operation that left COM/WMI registration inconsistent

This is an **OS/WMI health** problem on the instance, not a patch-content, connectivity, or timing problem.

## Related Failure Patterns

- SOP-018 (Transient Post-Scan Auto-Close) — distinguish: C11 has a specific `0x80040154` CIM error, not a bare exit-1
- SOP-021 (Windows Update / WSUS) — a different pre-patch failure (update source), not WMI

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Operator can run `AWS-RunPowerShellScript`
- A maintenance/change window is open (WMI repository repair is a system-level change — see Safety note)

> **Safety note:** Rebuilding the WMI repository (Step 3) is a system-level change that can affect other WMI-dependent software (monitoring, inventory agents). Perform only in an approved window and prefer the non-destructive consistency check (Step 2) first.

## Diagnosis

All read-only. Run via `AWS-RunPowerShellScript`:

```powershell
# 1. WMI service state
Get-Service Winmgmt | Select-Object Status,StartType
# 2. WMI repository consistency (read-only verify)
winmgmt /verifyrepository
# 3. Can we run the exact CIM query the patch op uses?
try { Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop | Select-Object -First 1 Caption; "CIM_OK" }
catch { "CIM_FAIL: " + $_.Exception.Message }
```

**Decision rule (evaluate once):**
- `winmgmt /verifyrepository` returns `WMI repository is consistent` AND `CIM_OK` → WMI is healthy; the error was transient → confirm readiness for next patch cycle (Step 4).
- `verifyrepository` reports inconsistent OR `CIM_FAIL` with `0x80040154` → WMI repository/registration issue → Step 2, then Step 3 if needed.

## Remediation Steps

> This SOP makes a **bounded, escalating** repair attempt: salvage (non-destructive) → re-register providers → repository rebuild (last resort, approval) → validate readiness. It does not loop or re-invoke patching.

### Step 1: Ensure the WMI service is running

```powershell
if ((Get-Service Winmgmt).Status -ne 'Running') { Start-Service Winmgmt }
(Get-Service Winmgmt).Status
```

Expected: `Running`. On failure: escalate (service won't start → deeper OS issue).

### Step 2: Non-destructive repository salvage + re-register WMI/COM providers

```powershell
winmgmt /salvagerepository
# re-register WMI provider DLLs and MOF classes
$p = "$env:WINDIR\System32\wbem"
Get-ChildItem "$p\*.dll" | ForEach-Object { regsvr32 /s $_.FullName }
Get-ChildItem "$p\*.mof" -ErrorAction SilentlyContinue | ForEach-Object { mofcomp $_.FullName } | Out-Null
"salvage+reregister done"
```

Expected: `salvage+reregister done`; re-run Diagnosis Step 3 — if `CIM_OK`, go to Step 4.
On failure / still `CIM_FAIL`: Step 3 (requires approval).

### Step 3 (REQUIRES APPROVAL — destructive to WMI repo): Rebuild the repository

```powershell
# Only with change approval; impacts other WMI-dependent agents until rebuilt
Stop-Service Winmgmt -Force
Rename-Item "$env:WINDIR\System32\wbem\Repository" "Repository.bak_$(Get-Date -Format yyyyMMddHHmmss)"
Start-Service Winmgmt   # WMI rebuilds the repository on next start
Start-Sleep 10
winmgmt /verifyrepository
```

Expected: `WMI repository is consistent`. On failure: abort and escalate (do not retry rebuild repeatedly).

### Step 4: Confirm WMI is healthy and ready for next patch cycle

The underlying WMI issue has been resolved. The patch will be retried automatically by the next scheduled maintenance window run.

```powershell
try { Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop | Select-Object -First 1 Caption; "WMI HEALTHY - ready for next patch cycle" } catch { "WMI STILL BROKEN: $($_.Exception.Message)" }
```

Expected output: OS caption followed by "WMI HEALTHY - ready for next patch cycle"
On failure: abort — escalate for OS-level WMI repair. Do not retry patching against a broken WMI repository.

## Validation

```powershell
try { Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop | Select-Object Caption; winmgmt /verifyrepository; "WMI REMEDIATION OK" } catch { "WMI REMEDIATION FAILED: $($_.Exception.Message)" }
```

Expected: "WMI repository is consistent" followed by "WMI REMEDIATION OK"

## Rollback

- Steps 1–2 are non-destructive (service start, provider re-registration).
- If Step 3 was performed and WMI is unhealthy after rebuild, the renamed `Repository.bak_*` can be restored:

```powershell
Stop-Service Winmgmt -Force
Remove-Item "$env:WINDIR\System32\wbem\Repository" -Recurse -Force
Rename-Item "$env:WINDIR\System32\wbem\Repository.bak_<timestamp>" "Repository"
Start-Service Winmgmt
```

## Prevention

- Monitor WMI health (`winmgmt /verifyrepository`) on instances that have raised `0x80040154`; add a pre-patch WMI consistency check.
- Investigate image/software that may unregister WMI providers (failed updates, agent uninstalls).
- Treat instances with recurring C11 as needing a golden-image/baseline review rather than per-cycle patching.

## Escalation

If `0x80040154` persists after repository repair and a single retry:
- Capture `winmgmt /verifyrepository`, the `Get-CimInstance` error, `Winmgmt` service state, and `CBS.log`.
- Escalate to your OS engineering team — the instance may need deeper servicing or rebuild. Do not repeatedly retry patching against a broken WMI repository.
