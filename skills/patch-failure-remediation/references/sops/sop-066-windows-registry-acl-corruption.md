# SOP-066: Resolve Windows Update Failure Due to Registry Permissions / ACL Corruption

| Field | Value |
|-------|-------|
| ID | SOP-066 |
| Category | windows_registry_acl_corruption |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80070005` ("Access is denied") when Windows Update writes to registry
- `0x8024401C` ("WU_E_PT_HTTP_STATUS_REQUEST_TIMEOUT") due to config read failure
- Windows Update Agent cannot read its own configuration
- CBS cannot write package state to Component Based Servicing registry
- Event ID 7000/7001 — services fail to start due to registry ACL
- WSUS configuration not readable despite registry values existing

## Root Cause

Registry ACL corruption blocks Windows Update when:

- Security hardening script overwrote registry key permissions too broadly
- Third-party cleanup tool removed inherited permissions from WU keys
- Domain GPO applied restrictive ACLs on HKLM\SOFTWARE\Microsoft\Windows
- Manual registry permission change propagated incorrectly
- CIS/STIG hardening removed SYSTEM/TrustedInstaller write access
- Server 2012 R2: security update broke ACL inheritance on servicing keys

## Related Failure Patterns

- SOP-056 (GPO Blocking) — GPO can also restrict registry access
- SOP-062 (Corrupt Profile) — profile issues can affect per-user registry ACLs

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Run commands as SYSTEM (SSM default) to match WUA execution context

## Diagnosis

```powershell
$keys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing',
    'HKLM:\SYSTEM\CurrentControlSet\Services\wuauserv'
)
foreach ($k in $keys) {
    try { $acl = Get-Acl $k; Write-Output "OK: $k (Owner: $($acl.Owner))" }
    catch { Write-Output "BLOCKED: $k - $($_.Exception.Message)" }
}
```

## Remediation Steps

### Step 1: Test read/write access to Windows Update registry keys

```powershell
$testKeys = @(
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing',
    'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
)
foreach ($k in $testKeys) {
    if (Test-Path $k) {
        try { Get-Acl $k | Out-Null; Write-Output "READ OK: $k" }
        catch { Write-Output "READ FAIL: $k" }
    } else { Write-Output "MISSING: $k" }
}
```

Expected output: Access test results
On failure: continue

### Step 2: Reset Windows Update registry key permissions

```powershell
$wuKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate'
if (Test-Path $wuKey) {
    # Repair on the EXISTING ACL so ACEs WU relies on (Users read, ALL APPLICATION PACKAGES, etc.)
    # are preserved — do NOT replace the DACL with only 3 ACEs.
    $acl = Get-Acl $wuKey
    $acl.SetOwner([System.Security.Principal.NTAccount]"NT AUTHORITY\SYSTEM")
    # Keep inheritance enabled and preserve existing inherited ACEs.
    $acl.SetAccessRuleProtection($false, $true)
    $rules = @(
        [System.Security.AccessControl.RegistryAccessRule]::new("NT AUTHORITY\SYSTEM", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"),
        [System.Security.AccessControl.RegistryAccessRule]::new("BUILTIN\Administrators", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"),
        [System.Security.AccessControl.RegistryAccessRule]::new("NT SERVICE\TrustedInstaller", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    )
    # AddAccessRule merges the required ACEs onto the existing DACL rather than replacing it.
    foreach ($r in $rules) { $acl.AddAccessRule($r) }
    Set-Acl $wuKey $acl
    Write-Output "WindowsUpdate key permissions repaired (required ACEs added, existing preserved)"
} else { Write-Output "WindowsUpdate key not found" }
```

Expected output: "WindowsUpdate key permissions repaired (required ACEs added, existing preserved)"
On failure: continue

### Step 3: Reset Component Based Servicing registry permissions

```powershell
$cbsKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing'
if (Test-Path $cbsKey) {
    # Repair on the EXISTING ACL so ACEs the servicing stack relies on are preserved —
    # do NOT replace the DACL with only 3 ACEs.
    $acl = Get-Acl $cbsKey
    $acl.SetOwner([System.Security.Principal.NTAccount]"NT AUTHORITY\SYSTEM")
    # Keep inheritance enabled and preserve existing inherited ACEs.
    $acl.SetAccessRuleProtection($false, $true)
    $rules = @(
        [System.Security.AccessControl.RegistryAccessRule]::new("NT AUTHORITY\SYSTEM", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"),
        [System.Security.AccessControl.RegistryAccessRule]::new("BUILTIN\Administrators", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"),
        [System.Security.AccessControl.RegistryAccessRule]::new("NT SERVICE\TrustedInstaller", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
    )
    # AddAccessRule merges the required ACEs onto the existing DACL rather than replacing it.
    foreach ($r in $rules) { $acl.AddAccessRule($r) }
    Set-Acl $cbsKey $acl
    Write-Output "CBS key permissions repaired (required ACEs added, existing preserved)"
} else { Write-Output "CBS key not found" }
```

Expected output: "CBS key permissions repaired (required ACEs added, existing preserved)"
On failure: continue

### Step 4: Reset WUA service registry permissions

```powershell
$svcKey = 'HKLM:\SYSTEM\CurrentControlSet\Services\wuauserv'
if (Test-Path $svcKey) {
    # Repair on the EXISTING ACL so ACEs the service relies on are preserved —
    # do NOT replace the DACL.
    $acl = Get-Acl $svcKey
    $acl.SetOwner([System.Security.Principal.NTAccount]"NT AUTHORITY\SYSTEM")
    # Keep inheritance enabled and preserve existing inherited ACEs.
    $acl.SetAccessRuleProtection($false, $true)
    # AddAccessRule merges the required ACEs onto the existing DACL rather than replacing it.
    $acl.AddAccessRule([System.Security.AccessControl.RegistryAccessRule]::new("NT AUTHORITY\SYSTEM", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"))
    $acl.AddAccessRule([System.Security.AccessControl.RegistryAccessRule]::new("BUILTIN\Administrators", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"))
    $acl.AddAccessRule([System.Security.AccessControl.RegistryAccessRule]::new("NT SERVICE\TrustedInstaller", "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"))
    Set-Acl $svcKey $acl
    Write-Output "WUA service key permissions repaired (required ACEs added, existing preserved)"
}
```

Expected output: "WUA service key permissions repaired (required ACEs added, existing preserved)"
On failure: continue

### Step 5: Verify Windows Update can read/write configuration

```powershell
$testVal = "SOP066_Test_$(Get-Random)"
$wuKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate'
try {
    Set-ItemProperty $wuKey -Name $testVal -Value 1 -ErrorAction Stop
    Remove-ItemProperty $wuKey -Name $testVal -Force
    Write-Output "REGISTRY ACL REMEDIATION OK"
} catch { Write-Output "REGISTRY STILL BLOCKED: $($_.Exception.Message)" }
```

Expected output: "REGISTRY ACL REMEDIATION OK"
On failure: abort

## Validation

```powershell
$keys = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate', 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing')
$allOk = $true
foreach ($k in $keys) {
    try { Get-Acl $k | Out-Null } catch { $allOk = $false }
}
if ($allOk) { "REGISTRY ACL REMEDIATION OK" } else { "REGISTRY ACL STILL BROKEN" }
```

Expected: "REGISTRY ACL REMEDIATION OK"

## Rollback

Registry permissions were set to Windows defaults. If more restrictive ACLs are required by security policy, reapply the hardening script after patching completes.

## Escalation

If registry ACLs cannot be fixed:
- **CAUTION — destructive, human-run only:** `secedit /configure /db reset.sdb /cfg %SystemRoot%\inf\defltbase.inf /overwrite` resets the ENTIRE system-wide security policy (all registry/file ACLs, user rights, and account policies) to Windows defaults. This can undo hardening, break other applications, and is not reversible by this SOP. It MUST NOT be run by automation — reserve it for a human operator who has taken a full backup and understands the blast radius.
- Check if STIG/CIS hardening script needs WU-specific exceptions
- For Server 2012 R2: `subinacl.exe` tool can reset registry tree permissions
- If TrustedInstaller SID is unresolvable: SFC scan may be needed to repair SID database
- Contact customer security team about patching-compatible hardening baselines
