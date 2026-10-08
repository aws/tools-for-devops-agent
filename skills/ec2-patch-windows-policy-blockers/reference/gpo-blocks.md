# Group Policy blocking Windows Update

**Signatures:** `0x8024002E` (WU_E_WU_DISABLED), "managed by your organization", `NoAutoUpdate=1`,
`DisableWindowsUpdateAccess=1`, `DoNotConnectToWindowsUpdateInternetLocations=1`, patches download
but never install, WSUS GPO pointing at a decommissioned server.

**Registry edits here are TEMPORARY — a domain GPO reverts them on the next refresh (~90 min).**

## Diagnose
```powershell
$wu='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
Get-ItemProperty "$wu\AU" -EA SilentlyContinue | Select NoAutoUpdate,UseWUServer,AUOptions
Get-ItemProperty $wu -EA SilentlyContinue | Select DisableWindowsUpdateAccess,WUServer,DoNotConnectToWindowsUpdateInternetLocations
```

## Clear for this cycle (temporary)
```powershell
$au="$wu\AU"
Set-ItemProperty $au -Name NoAutoUpdate -Value 0 -EA SilentlyContinue
Set-ItemProperty $wu -Name DisableWindowsUpdateAccess -Value 0 -EA SilentlyContinue
# if WSUS is the wrong/unreachable target and Microsoft Update is allowed (needs approval):
# Set-ItemProperty $au -Name UseWUServer -Value 0
Restart-Service wuauserv -Force
```

## Verify
```powershell
$au=Get-ItemProperty "$wu\AU" -EA SilentlyContinue; $w=Get-ItemProperty $wu -EA SilentlyContinue
if(($au.NoAutoUpdate -ne 1) -and ($w.DisableWindowsUpdateAccess -ne 1)){"GPO cleared this cycle"}else{"STILL BLOCKED"}
```

## Escalation (the durable fix)
- Changes revert on GPO refresh — **the AD/GPO team must fix the policy for the patching OU**, or move the instance to a patching-friendly OU.
- Server 2012 R2 domain-joined: dual-scan may need `DisableDualScan=0`.
- Server 2019+: check for Intune/MDM policy overriding WU.
- WSUS GPO pointing at a decommissioned host → see the connectivity skill's WSUS routing.
