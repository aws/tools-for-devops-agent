# SOP-073: Resolve Windows Patch Failure Due to DCOM/RPC Configuration Errors

| Field | Value |
|-------|-------|
| ID | SOP-073 |
| Category | windows_dcom_rpc_failure |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80080005` ("Server execution failed") during Windows Update COM operations
- `0x800706BA` ("The RPC server is unavailable") on WUA initialization
- `0x80070721` ("A security package specific error occurred")
- Windows Update COM objects cannot be instantiated
- `Microsoft.Update.Session` creation fails in PowerShell
- Event ID 10016 DCOM permission errors for Windows Update related CLSIDs
- WMI queries to Win32_QuickFixEngineering fail

## Root Cause

DCOM/RPC failures during patching when:

- RPC service (RpcSs) not running or corrupted
- DCOM permissions changed by security hardening (2022 DCOM hardening enforcement)
- COM+ catalog corruption
- DCOM Launch/Activation permissions removed for SYSTEM or Network Service
- RPC endpoint mapper cannot resolve WUA service endpoint
- DCOM hardening update (KB5004442 chain) broke WUA COM registration
- Server 2012 R2: DCOM security level incompatible with newer update agent
- Third-party software registered conflicting COM class IDs

## Related Failure Patterns

- SOP-023 (WMI/CIM) — WMI depends on DCOM/RPC
- SOP-052 (WUA Hang) — RPC timeout can present as hang
- SOP-066 (Registry ACL) — DCOM config stored in registry

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Changes to DCOM security require reboot to take effect

## Diagnosis

```powershell
Get-Service RpcSs,DcomLaunch,RpcLocator | Select-Object Name,Status,StartType
try { $session = New-Object -ComObject Microsoft.Update.Session; Write-Output "COM: WUA Session created OK" }
catch { Write-Output "COM FAILURE: $($_.Exception.Message)" }
Get-WinEvent -LogName System -MaxEvents 20 | Where-Object { $_.Id -eq 10016 -or $_.ProviderName -match 'DCOM|RPC' } | Select-Object TimeCreated,Id,Message | Select-Object -First 5
```

## Remediation Steps

### Step 1: Verify RPC and DCOM services are running

```powershell
$services = @('RpcSs','DcomLaunch','RpcEptMapper')
foreach ($svc in $services) {
    $s = Get-Service $svc -ErrorAction SilentlyContinue
    Write-Output "$svc: $($s.Status) ($($s.StartType))"
    if ($s.Status -ne 'Running') {
        Start-Service $svc -ErrorAction SilentlyContinue
        Write-Output "  Started $svc"
    }
}
```

Expected output: Services running
On failure: continue

### Step 2: Test COM object creation for Windows Update

```powershell
$comObjects = @('Microsoft.Update.Session', 'Microsoft.Update.AutoUpdate', 'Microsoft.Update.SystemInfo')
foreach ($obj in $comObjects) {
    try {
        $instance = New-Object -ComObject $obj -ErrorAction Stop
        Write-Output "OK: $obj"
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($instance) | Out-Null
    } catch { Write-Output "FAIL: $obj - $($_.Exception.Message)" }
}
```

Expected output: COM objects created successfully
On failure: continue

### Step 3: Re-register Windows Update COM components

```powershell
$dlls = @('wuapi.dll','wuaueng.dll','wucltux.dll','wuwebv.dll','wups.dll','wups2.dll')
foreach ($dll in $dlls) {
    $path = "$env:SystemRoot\System32\$dll"
    if (Test-Path $path) { & regsvr32.exe /s $path }
}
Write-Output "WUA COM components re-registered"
```

Expected output: "WUA COM components re-registered"
On failure: continue

### Step 4: Reset DCOM default permissions if corrupted

```powershell
# Check DCOM machine-wide default permissions
$dcomReg = 'HKLM:\SOFTWARE\Microsoft\Ole'
$defaultPerm = (Get-ItemProperty $dcomReg -Name 'DefaultLaunchPermission' -ErrorAction SilentlyContinue).DefaultLaunchPermission
if (-not $defaultPerm) {
    Write-Output "WARNING: Default DCOM launch permissions missing — may need repair"
} else { Write-Output "DCOM default permissions present" }
# Ensure DCOM is enabled
$enableDCOM = (Get-ItemProperty $dcomReg -Name 'EnableDCOM' -ErrorAction SilentlyContinue).EnableDCOM
if ($enableDCOM -ne 'Y') {
    Set-ItemProperty $dcomReg -Name 'EnableDCOM' -Value 'Y'
    Write-Output "DCOM enabled"
} else { Write-Output "DCOM already enabled" }
```

Expected output: DCOM configuration verified
On failure: continue

### Step 5: Verify WUA COM objects work after remediation

```powershell
try {
    $session = New-Object -ComObject Microsoft.Update.Session
    $searcher = $session.CreateUpdateSearcher()
    Write-Output "DCOM/RPC REMEDIATION OK: WUA COM operational"
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($session) | Out-Null
} catch { Write-Output "DCOM STILL BROKEN: $($_.Exception.Message)" }
```

Expected output: "DCOM/RPC REMEDIATION OK"
On failure: abort

## Validation

```powershell
try {
    $s = New-Object -ComObject Microsoft.Update.Session
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($s) | Out-Null
    "DCOM REMEDIATION OK"
} catch { "DCOM STILL FAILING" }
```

Expected: "DCOM REMEDIATION OK"

## Rollback

COM re-registration is non-destructive. DCOM settings changes require reboot to fully revert.

## Escalation

If DCOM/RPC failures persist:
- Run `sfc /scannow` to repair corrupted system DLLs
- Check Component Services (dcomcnfg) for corrupted app registrations
- For Event 10016: specific CLSID permissions need repair via Component Services MMC
- For DCOM hardening (Server 2022+): ensure KB5004442 compatibility updates applied
- If RPC service won't start: check `HKLM:\SYSTEM\CurrentControlSet\Services\RpcSs` registry entries
- COM+ catalog repair: `comrepl.exe` or re-register all COM+ applications
