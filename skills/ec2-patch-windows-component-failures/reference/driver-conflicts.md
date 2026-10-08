# Driver update conflicts on EC2 (ENA / NVMe / PV)

**Signatures:** BSOD or unreachable instance after a WU driver update, `0x800F0217`
(CBS_E_NEED_REBOOT with driver failure), Device Manager yellow bang on network/storage adapter, ENA
driver regression, NVMe boot-volume loss on Nitro, Citrix/AWS PV conflict. **High-risk.**

**Root cause:** Windows Update pushes a **generic in-box driver that overrides the AWS-specific
ENA/NVMe/PV driver.** The fix is to keep WU away from drivers, not to reinstall a generic one.

## Diagnose
```powershell
Get-WinEvent -LogName System -MaxEvents 50 | ? {$_.ProviderName -match 'BugCheck|Driver|ndis|storport' -and $_.Level -le 3} | Select TimeCreated,Id,Message
Get-WindowsDriver -Online | ? {$_.ProviderName -match 'Amazon|AWS' -or $_.OriginalFileName -match 'ena|nvme|xen'} | Select ClassName,ProviderName,Version,Date
Get-NetAdapter | Select Name,InterfaceDescription,Status
```

## Prevent WU from overriding AWS drivers
```powershell
# hide pending driver updates for critical device classes:
$s=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
foreach($u in $s.Search("IsInstalled=0 and Type='Driver'").Updates){ if($u.Title -match 'network|ethernet|storage|scsi|nvme'){ $u.IsHidden=$true; "hidden: $($u.Title)" } }
# policy: exclude drivers from quality updates:
$p='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
New-Item $p -Force | Out-Null; Set-ItemProperty $p -Name ExcludeWUDriversInQualityUpdate -Value 1 -Type DWord
```

## Verify AWS drivers intact + reachability
```powershell
$ena=Get-NetAdapter | ? {$_.InterfaceDescription -match 'ENA|Elastic'}
$imds=Test-NetConnection 169.254.169.254 -Port 80 -WarningAction SilentlyContinue
if($ena -and $imds.TcpTestSucceeded){"DRIVER OK: ENA active, IMDS reachable"}else{"CHECK: ENA=$([bool]$ena) IMDS=$($imds.TcpTestSucceeded)"}
```

## Recover an unreachable instance / escalation
- Use **EC2 Serial Console** for the recovery environment; or attach the root volume to a rescue instance and roll back the driver from `\Windows\System32\DriverStore`.
- ENA: install the latest AWS ENA driver from the official EC2 Windows driver downloads (not WU).
- NVMe boot loss on Nitro: boot Safe Mode via `bcdedit`, roll back the NVMe driver; engage AWS Support.
- 2012 R2 on PV: ensure AWS PV drivers are installed before allowing any driver WU updates.
- Rollback the policy only if AWS driver currency is otherwise ensured: remove `ExcludeWUDriversInQualityUpdate`.
