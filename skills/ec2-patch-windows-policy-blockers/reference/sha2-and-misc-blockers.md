# Server 2012 R2 SHA-2 prerequisite & misc policy blockers

## Server 2012 R2 SHA-2 signing prerequisite (the big one)
**Signatures:** `0x800B0101` (cert not within validity), `0x80096010` (signer not found), CBS
"signature hash algorithm is not supported", scan returns 0 applicable updates, all WU fails after
2019-07 — on **build 9600 (2012 R2)** only. Since 2019 all updates are SHA-2 signed; 2012 R2 needs
the prerequisites or **every** post-2019 update fails signature validation.
```powershell
if((Get-CimInstance Win32_OperatingSystem).BuildNumber -eq '9600'){
  Get-HotFix -Id KB4490628 -EA SilentlyContinue | Out-Null; "SSU KB4490628: $([bool](Get-HotFix -Id KB4490628 -EA SilentlyContinue))"
  "SHA2 KB4474419: $([bool](Get-HotFix -Id KB4474419 -EA SilentlyContinue))"
}
```
**Order: install KB4490628 (SHA-2 SSU) FIRST, reboot, then KB4474419 (SHA-2 code signing).** If WU
can't offer them, get standalone packages from the Microsoft Update Catalog. These can't be uninstalled.

## PowerShell execution policy
```powershell
Get-ExecutionPolicy -List
# a Restricted/AllSigned machine policy can block patch scripts; scope a bypass for the process:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
```

## Registry ACL corruption (access denied on WU keys)
```powershell
# CBS/WU keys with broken ACLs cause access-denied; restore inheritance/owner on the specific key
# (use with care; example for a WU key):
# $acl=Get-Acl 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate'; ...
```

## DCOM / RPC config
```powershell
# 0x80040154 class-not-registered / DCOM errors during WMI-based patch checks:
Get-Service RpcSs,DcomLaunch | Select Name,Status   # must be Running
```

## Credential Guard / Device Guard, scheduled task, language pack
- Credential/Device Guard can block driver/kernel updates → coordinate with security to disable for the update, then re-enable.
- A scheduled-task/maintenance-window conflict can preempt the patch → check `Get-ScheduledTask` for conflicting maintenance.
- Language-pack/MUI mismatch → align the LP with the OS build before the cumulative update.

## Verify
```powershell
# 2012 R2:
(Get-HotFix -Id KB4474419 -EA SilentlyContinue) -and (Get-HotFix -Id KB4490628 -EA SilentlyContinue)
```
