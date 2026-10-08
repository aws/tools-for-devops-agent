# .NET Framework update failure

**Signatures:** `0x80070643` (fatal error during install) or `0x80096004` (invalid signature) on .NET
patches, .NET KB shows Failed while everything else succeeds, Application log .NETRuntime/NGen errors,
hung `mscorsvw.exe`.

**Key fact:** on Server 2016+ .NET 4.x is an **OS component** — repair it via DISM, not a standalone
reinstall as the first move.

## Diagnose
```powershell
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP' -Recurse | Get-ItemProperty -Name Version,Release -EA SilentlyContinue | ? {$_.Version} | Select PSChildName,Version
Get-WinEvent -LogName Application -MaxEvents 20 | ? {$_.ProviderName -match 'NGen|\.NET' -and $_.Level -le 3} | Select TimeCreated,Message
```

## Repair sequence
```powershell
# 1. stop the optimization service so it doesn't fight the repair:
Get-Process mscorsvw -EA SilentlyContinue | Stop-Process -Force
Stop-Service clr_optimization_v4.0.30319_64,clr_optimization_v4.0.30319_32 -Force -EA SilentlyContinue
# 2. resync NGen native images:
& "$env:SystemRoot\Microsoft.NET\Framework64\v4.0.30319\ngen.exe" update /force 2>&1 | Select -Last 3
& "$env:SystemRoot\Microsoft.NET\Framework\v4.0.30319\ngen.exe" update /force 2>&1 | Select -Last 3
# 3. repair the component store (2016+ treats .NET as an OS component):
DISM /Online /Cleanup-Image /RestoreHealth
# 4. clear stale WU downloads and retry:
Stop-Service wuauserv -Force; Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue; Start-Service wuauserv
```

## Verify
```powershell
$pending=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software'").Updates | ? {$_.Title -match '\.NET|Framework'}
if($pending.Count -eq 0){"DOTNET OK"}else{"still pending: $($pending.Count)"}
```

## Escalation
- Run the Microsoft .NET Framework Repair Tool.
- ASP.NET/IIS registration corrupt → `aspnet_regiis -ir`.
- 2012 R2: .NET 4.x is not an OS component — may need uninstall/reinstall of .NET 4.x.
- Last resort: install the latest .NET cumulative via the standalone installer.
