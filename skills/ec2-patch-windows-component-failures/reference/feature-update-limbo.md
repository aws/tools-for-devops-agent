# Feature update / in-place upgrade limbo

**Signatures:** `0xC1900101` (SAFE_OS / SECOND_BOOT phase failure), `0x80240020`
(WU_E_NO_INTERACTIVE_USER during a feature update), `0x80070490` after a partial upgrade, system
stuck between OS versions, `C:\Windows.old` with no matching completion, cumulative updates fail "not
applicable to this image", unexpected build number. **High-risk.**

**Root cause:** an in-place upgrade (e.g. 2016→2019) started but never completed, or an image was
captured mid-upgrade; the LCU targets a build the system isn't actually on.

## Diagnose — confirm the ACTUAL build first
```powershell
$nt=Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
"Product=$($nt.ProductName) Build=$($nt.CurrentBuildNumber).$($nt.UBR) Edition=$($nt.EditionID) InstallType=$($nt.InstallationType)"
"Windows.old=$(Test-Path 'C:\Windows.old')  ~BT=$(Test-Path 'C:\$WINDOWS.~BT')"
(Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name UpgradeInProgress -EA SilentlyContinue).UpgradeInProgress
(Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name SetupType -EA SilentlyContinue).SetupType
```

## Clear the limbo
```powershell
# 1. clear stale upgrade flags:
foreach($f in 'UpgradeInProgress','SetupType'){ $v=(Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name $f -EA SilentlyContinue).$f; if($v -and $v -ne 0){ Set-ItemProperty 'HKLM:\SYSTEM\Setup' -Name $f -Value 0; "cleared $f (was $v)" } }
# 2. remove stale staging (irreversible but doesn't affect the running OS):
'C:\$WINDOWS.~BT','C:\$WINDOWS.~WS','C:\$Windows.~LS' | % { if(Test-Path $_){ Remove-Item $_ -Recurse -Force -EA SilentlyContinue; "removed $_" } }
# 3. confirm the store is consistent:
DISM /Online /Cleanup-Image /CheckHealth
```

## Verify
```powershell
$flag=(Get-ItemProperty 'HKLM:\SYSTEM\Setup' -Name UpgradeInProgress -EA SilentlyContinue).UpgradeInProgress
$health=DISM /Online /Cleanup-Image /CheckHealth 2>&1
if(-not $flag -and -not (Test-Path 'C:\$WINDOWS.~BT') -and ($health -match 'healthy')){"FEATURE UPDATE LIMBO CLEARED"}else{"issues remain"}
```

## Escalation
- On the wrong build with `Windows.old` present → rollback may be possible within ~10 days.
- Stuck between versions → an in-place upgrade repair install is usually required.
- **WSUS/SCCM should NOT offer feature updates to LTSC servers** — fix the deployment ring.
- CBS references an old build while the OS is current → `DISM /Online /Cleanup-Image /RestoreHealth`.
- Fundamentally inconsistent OS → rebuild from a known-good AMI.
