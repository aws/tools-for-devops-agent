# AWSSDK.Core missing from the GAC (breaks AWS-RunPatchBaseline)

**Signatures:** patch baseline fails with `Invoke-PatchBaselineOperation : Could not load type
'Amazon.Runtime.Internal.InvokeOptions' from assembly 'AWSSDK.Core'`; the `AWS-RunPatchBaseline`
PatchWindows plugin fails immediately with a .NET type-load exception; prereq checks pass but the
actual scan/install throws. Cause: the `AWSSDK.Core` .NET assembly was removed/corrupted in the GAC
(a .NET update, GAC cleanup, or AV quarantine), so the PatchBaselineOperations module can't load AWS
SDK types.

**Snapshot the root volume before remediation.**

## Diagnose
```powershell
[System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")   # null => missing from GAC
Get-ChildItem "C:\Program Files*\AWS SDK for .NET" -Recurse -Filter AWSSDK.Core.dll -EA SilentlyContinue | Select FullName
```

## Fix — re-register AWSSDK.Core.dll into the GAC with gacutil
```powershell
$dll = Get-ChildItem "C:\Program Files*\AWS SDK for .NET" -Recurse -Filter AWSSDK.Core.dll -EA SilentlyContinue | Select -First 1
$gac = Get-ChildItem "C:\Program Files*\Microsoft SDKs\Windows" -Recurse -Filter gacutil.exe -EA SilentlyContinue | ? {$_.FullName -match 'NETFX'} | Select -First 1
if($dll -and $gac){ & $gac.FullName /i $dll.FullName 2>&1 } else { "MISSING: dll=$($dll.FullName) gacutil=$($gac.FullName)" }
```

## Verify
```powershell
$a=[System.Reflection.Assembly]::LoadWithPartialName("AWSSDK.Core")
if($a -and $a.GetType("Amazon.Runtime.Internal.InvokeOptions")){"AWSSDK GAC OK"}else{"STILL BROKEN"}
```
Then re-run `AWS-RunPatchBaseline` in Scan mode to confirm.

## Prevention / escalation
- Exclude `C:\Program Files (x86)\AWS SDK for .NET` from AV quarantine; don't run GAC-cleanup scripts that strip third-party assemblies.
- AWSSDK.Core.dll not on disk → reinstall the AWS SDK for .NET.
- gacutil.exe absent → install the Windows/.NET Framework SDK, or copy AWSSDK.Core.dll from a known-good same-OS instance.
- Rollback: `gacutil /u AWSSDK.Core`.
