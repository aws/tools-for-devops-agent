# WUA / BITS / TrustedInstaller hung; scan never returns

**Signatures:** patch scan hangs indefinitely, wuauserv stuck "Stopping"/"Starting", BITS not
running, `0x80246008` download failed, svchost 100% CPU in WUA context, TiWorker.exe hung for a long
time, patch times out with no error.

## Diagnose
```powershell
Get-Service wuauserv,bits,cryptSvc,TrustedInstaller | Select Name,Status,StartType
Get-Process TiWorker,wuauclt,svchost -ErrorAction SilentlyContinue | ? {$_.CPU -gt 60} | Select Name,Id,CPU,StartTime
```

## Fix — reset services, clear download cache, re-register DLLs
```powershell
# kill processes hung >30 min
Get-Process TiWorker,wuauclt -EA SilentlyContinue | ? {((Get-Date)-$_.StartTime).TotalMinutes -gt 30} | Stop-Process -Force
Stop-Service wuauserv,bits,cryptSvc,msiserver -Force -EA SilentlyContinue; Start-Sleep 5
Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -EA SilentlyContinue
# re-register WUA DLLs:
'wuaueng.dll','wups.dll','wups2.dll','wuwebv.dll','atl.dll','msxml3.dll' | % { $p="$env:SystemRoot\System32\$_"; if(Test-Path $p){ regsvr32.exe /s $p } }
Start-Service bits,cryptSvc,msiserver,wuauserv -EA SilentlyContinue
```

## If the scan database is corrupt (svchost pegged, scan never completes)
```powershell
Stop-Service wuauserv,bits -Force
Rename-Item "$env:SystemRoot\SoftwareDistribution" "$env:SystemRoot\SoftwareDistribution.old" -Force   # rebuilds DataStore.edb on next scan
Start-Service wuauserv,bits
```

## Verify
```powershell
try{ $r=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software'"); "WUA SEARCH OK: $($r.Updates.Count)" }catch{ "WUA SEARCH FAILED: $($_.Exception.Message)" }
```

## Escalation
- If resetting doesn't hold → the underlying cause is often a stale SSU or CBS store corruption (servicing-store skill).
- Killing TiWorker can leave a pending servicing transaction → clear it (servicing-store skill) before retry.
- Persistent svchost 100% CPU → the DataStore.edb reset above is the targeted fix.
