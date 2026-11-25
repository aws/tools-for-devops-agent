# SOP-076: Resolve Windows Patch Failure Due to Credential Guard / Device Guard Interference

| Field | Value |
|-------|-------|
| ID | SOP-076 |
| Category | windows_credential_guard_interference |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Virtualization-Based Security (VBS) updates fail with `0x800F0984`
- `0x800F0922` ("CBS_E_INSTALLERS_FAILED") on Secure Kernel updates
- Credential Guard / HVCI update fails to enable post-reboot
- Device Guard policy prevents loading of update-required drivers
- Code Integrity policy blocks unsigned Windows Update components
- Boot failure after enabling Credential Guard via patch

## Root Cause

Credential Guard / Device Guard interference when:

- VBS (Virtualization-Based Security) requires specific CPU features not available on instance type
- HVCI (Hypervisor-Enforced Code Integrity) blocks unsigned kernel components during update
- Code Integrity (CI) policy rejects update drivers that aren't in policy
- Credential Guard enablement patch fails because instance lacks nested virtualization
- UEFI lock of Credential Guard prevents security patch configuration changes
- EC2 instance type doesn't support the required virtualization extensions for VBS

## Related Failure Patterns

- SOP-057 (Driver Update) — HVCI blocks unsigned drivers
- SOP-068 (Execution Policy) — WDAC is related to Device Guard
- SOP-074 (BitLocker) — VBS/BitLocker share Secure Boot dependencies

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of customer's security baseline requirements

## Diagnosis

```powershell
$vbs = Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root\Microsoft\Windows\DeviceGuard -ErrorAction SilentlyContinue
if ($vbs) {
    Write-Output "VBS Status: $($vbs.VirtualizationBasedSecurityStatus)"
    Write-Output "Credential Guard: $($vbs.SecurityServicesRunning -contains 1)"
    Write-Output "HVCI: $($vbs.SecurityServicesRunning -contains 2)"
} else { Write-Output "Device Guard WMI class not available" }
$reg = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' -ErrorAction SilentlyContinue
Write-Output "EnableVirtualizationBasedSecurity: $($reg.EnableVirtualizationBasedSecurity)"
```

## Remediation Steps

### Step 1: Check VBS and Credential Guard configuration

```powershell
$dgReg = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' -ErrorAction SilentlyContinue
$lsaReg = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -ErrorAction SilentlyContinue
Write-Output "VBS Enabled: $($dgReg.EnableVirtualizationBasedSecurity)"
Write-Output "HVCI Enabled: $($dgReg.HypervisorEnforcedCodeIntegrity)"
Write-Output "Credential Guard: $($lsaReg.LsaCfgFlags)"
Write-Output "RequirePlatformSecurityFeatures: $($dgReg.RequirePlatformSecurityFeatures)"
```

Expected output: Security feature state displayed
On failure: continue

### Step 2: Check if instance supports required virtualization features

```powershell
$proc = Get-CimInstance Win32_Processor | Select-Object -First 1
$vm = Get-CimInstance Win32_ComputerSystem
Write-Output "Processor: $($proc.Name)"
Write-Output "Virtualization: $($proc.VirtualizationFirmwareEnabled)"
Write-Output "Model: $($vm.Model)"
Write-Output "Manufacturer: $($vm.Manufacturer)"
$hypervisor = (Get-CimInstance Win32_ComputerSystem).HypervisorPresent
Write-Output "Hypervisor present: $hypervisor"
```

Expected output: Hardware capability info
On failure: continue

### Step 3: Disable VBS/HVCI if causing update failures (temporary for patching)

```powershell
$dgPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard'
if (Test-Path $dgPath) {
    $vbs = (Get-ItemProperty $dgPath -Name 'EnableVirtualizationBasedSecurity' -ErrorAction SilentlyContinue).EnableVirtualizationBasedSecurity
    if ($vbs -eq 1) {
        Set-ItemProperty $dgPath -Name 'EnableVirtualizationBasedSecurity' -Value 0
        Write-Output "VBS disabled (will take effect after reboot)"
    } else { Write-Output "VBS not enabled" }
    $hvci = (Get-ItemProperty $dgPath -Name 'HypervisorEnforcedCodeIntegrity' -ErrorAction SilentlyContinue).HypervisorEnforcedCodeIntegrity
    if ($hvci -eq 1) {
        Set-ItemProperty $dgPath -Name 'HypervisorEnforcedCodeIntegrity' -Value 0
        Write-Output "HVCI disabled (will take effect after reboot)"
    }
} else { Write-Output "No DeviceGuard configuration found" }
```

Expected output: VBS/HVCI disabled or not configured
On failure: continue

### Step 4: Disable Credential Guard if blocking updates

```powershell
$lsaPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa'
$lsaCfg = (Get-ItemProperty $lsaPath -Name 'LsaCfgFlags' -ErrorAction SilentlyContinue).LsaCfgFlags
if ($lsaCfg -and $lsaCfg -ne 0) {
    Set-ItemProperty $lsaPath -Name 'LsaCfgFlags' -Value 0
    Write-Output "Credential Guard disabled (requires reboot)"
} else { Write-Output "Credential Guard not configured or already disabled" }
```

Expected output: CG status
On failure: continue

### Step 5: Verify configuration changes applied

```powershell
$dgPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard'
$vbs = (Get-ItemProperty $dgPath -Name 'EnableVirtualizationBasedSecurity' -ErrorAction SilentlyContinue).EnableVirtualizationBasedSecurity
$lsa = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name 'LsaCfgFlags' -ErrorAction SilentlyContinue).LsaCfgFlags
if ($vbs -ne 1 -and $lsa -ne 1) { Write-Output "VBS/CG REMEDIATION OK (reboot needed to apply)" }
else { Write-Output "VBS/CG STILL CONFIGURED: VBS=$vbs CG=$lsa" }
```

Expected output: "VBS/CG REMEDIATION OK"
On failure: abort

## Validation

```powershell
$vbs = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard' -Name 'EnableVirtualizationBasedSecurity' -ErrorAction SilentlyContinue).EnableVirtualizationBasedSecurity
if ($vbs -ne 1) { "CREDENTIAL GUARD REMEDIATION OK" } else { "VBS STILL ENABLED" }
```

Expected: "CREDENTIAL GUARD REMEDIATION OK"

## Rollback

```powershell
$dgPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\DeviceGuard'
Set-ItemProperty $dgPath -Name 'EnableVirtualizationBasedSecurity' -Value 1 -ErrorAction SilentlyContinue
Set-ItemProperty $dgPath -Name 'HypervisorEnforcedCodeIntegrity' -Value 1 -ErrorAction SilentlyContinue
Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name 'LsaCfgFlags' -Value 1 -ErrorAction SilentlyContinue
Write-Output "VBS/HVCI/Credential Guard re-enabled (reboot required)"
```

## Escalation

If VBS/CG cannot be disabled:
- Check if UEFI lock is preventing changes: requires firmware-level intervention
- For EC2: most instance types don't support nested virtualization for VBS
- Nitro instances on metal: may support VBS if customer specifically enabled
- Customer security team must approve disabling CG even temporarily
- If HVCI is blocking driver updates: add driver hash to CI supplemental policy
- Consider moving to instance type that fully supports VBS if customer requires it
