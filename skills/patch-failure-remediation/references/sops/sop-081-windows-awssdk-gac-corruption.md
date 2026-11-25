# SOP-081: Resolve AWSSDK.Core Assembly Missing from GAC Blocking Patch Baseline

| Field | Value |
|-------|-------|
| ID | SOP-081 |
| Category | awssdk_gac_corruption |
| Severity | High |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-23 |

## Symptoms

- Patch baseline scan or install fails with: `Invoke-PatchBaselineOperation : Could not load type 'Amazon.Runtime.Internal.InvokeOptions' from assembly 'AWSSDK.Core'`
- `AWS-RunPatchBaseline` PatchWindows plugin fails immediately after starting
- Patch pre-requisite checks pass but the actual scan/install operation throws a .NET type load exception
- Error references `AWSSDK.Core` assembly version mismatch or missing type

## Root Cause

The AWSSDK.Core .NET assembly has been removed or corrupted in the Global Assembly Cache (GAC). This prevents the PatchBaselineOperations module from loading required AWS SDK types at runtime. Common causes:

- A .NET framework update or repair removed third-party GAC entries
- Manual or scripted cleanup of the GAC inadvertently removed AWS SDK assemblies
- AWS SDK for .NET was partially uninstalled or upgraded, leaving the GAC entry stale
- Anti-malware software quarantined the DLL
- File system corruption affecting the GAC folder structure under `C:\Windows\Microsoft.NET\assembly`

## Related Failure Patterns

- SOP-054 (Windows .NET Update Failure) — .NET framework issues can also corrupt GAC
- SOP-058 (Windows SSU Prerequisite) — servicing stack issues may coexist

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- **Create an EBS snapshot of the root volume before remediation as backup**
- AWS SDK for .NET is installed on the instance (check `C:\Program Files (x86)\AWS SDK for .NET`)

## Diagnosis

```powershell
# Check if AWSSDK.Core is in the GAC
$gac = [System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")
if ($gac) { Write-Output "GAC: $($gac.FullName) Location: $($gac.Location)" } else { Write-Output "AWSSDK.Core NOT in GAC" }
# Check if the DLL exists on disk
$paths = @("C:\Program Files (x86)\AWS SDK for .NET\bin\Net45\AWSSDK.Core.dll", "C:\Program Files\AWS SDK for .NET\bin\Net45\AWSSDK.Core.dll")
foreach ($p in $paths) { if (Test-Path $p) { Write-Output "Found: $p" } }
```

## Remediation Steps

### Step 1: Locate AWSSDK.Core.dll and gacutil.exe on the instance

```powershell
$sdkDll = Get-ChildItem -Path "C:\Program Files*\AWS SDK for .NET" -Recurse -Filter "AWSSDK.Core.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
$gacutil = Get-ChildItem -Path "C:\Program Files*\Microsoft SDKs\Windows" -Recurse -Filter "gacutil.exe" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "NETFX" } | Select-Object -First 1
if ($sdkDll) { Write-Output "SDK DLL: $($sdkDll.FullName)" } else { Write-Output "AWSSDK.Core.dll NOT FOUND" }
if ($gacutil) { Write-Output "gacutil: $($gacutil.FullName)" } else { Write-Output "gacutil.exe NOT FOUND" }
```

Expected output: Paths to both files
On failure: abort — SDK or Windows SDK not installed; requires manual installation

### Step 2: Register AWSSDK.Core.dll into the Global Assembly Cache

```powershell
$sdkDll = Get-ChildItem -Path "C:\Program Files*\AWS SDK for .NET" -Recurse -Filter "AWSSDK.Core.dll" -ErrorAction SilentlyContinue | Select-Object -First 1
$gacutil = Get-ChildItem -Path "C:\Program Files*\Microsoft SDKs\Windows" -Recurse -Filter "gacutil.exe" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "NETFX" } | Select-Object -First 1
if ($sdkDll -and $gacutil) {
    $result = & $gacutil.FullName /i $sdkDll.FullName 2>&1
    Write-Output $result
    if ($result -match "successfully added") { Write-Output "GAC REGISTRATION OK" } else { Write-Output "GAC REGISTRATION FAILED" }
} else { Write-Output "MISSING FILES - cannot register" }
```

Expected output: "Assembly successfully added to the cache" followed by "GAC REGISTRATION OK"
On failure: abort

### Step 3: Verify the assembly loads correctly

```powershell
$asm = [System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")
if ($asm) { Write-Output "LOADED: $($asm.FullName)" } else { Write-Output "LOAD FAILED" }
```

Expected output: Assembly full name with version
On failure: abort

### Step 4: Run Patch Baseline in scan mode to verify fix

```powershell
Write-Output "Run AWS-RunPatchBaseline in Scan mode via SSM to confirm the fix"
Write-Output "REMEDIATION COMPLETE - ready for scan verification"
```

Expected output: "REMEDIATION COMPLETE - ready for scan verification"
On failure: continue

## Validation

```powershell
$asm = [System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")
if ($asm -and $asm.GetType("Amazon.Runtime.Internal.InvokeOptions")) {
    Write-Output "AWSSDK GAC REMEDIATION OK"
} else {
    Write-Output "AWSSDK GAC REMEDIATION FAILED"
}
```

Expected: "AWSSDK GAC REMEDIATION OK"

## Rollback

```powershell
$gacutil = Get-ChildItem -Path "C:\Program Files*\Microsoft SDKs\Windows" -Recurse -Filter "gacutil.exe" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match "NETFX" } | Select-Object -First 1
if ($gacutil) { & $gacutil.FullName /u "AWSSDK.Core" 2>&1; Write-Output "AWSSDK.Core removed from GAC" }
```

## Prevention

- Do not run GAC cleanup scripts that remove AWS SDK assemblies
- Exclude `C:\Program Files (x86)\AWS SDK for .NET` from antivirus quarantine actions
- After .NET framework updates, verify AWS SDK assemblies are intact

## Escalation

If AWSSDK.Core.dll is not found on the instance:
- The AWS SDK for .NET may need to be reinstalled
- Download from: https://aws.amazon.com/sdk-for-net/
- If gacutil.exe is not available, the Windows SDK (or at minimum the .NET Framework SDK) must be installed
- Alternative: copy AWSSDK.Core.dll from a known-good instance with the same OS version
