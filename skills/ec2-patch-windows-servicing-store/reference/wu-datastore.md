# Windows Update datastore (DataStore.edb) bloat/corruption

**Signatures:** `0x8024400A` (WU_E_PT_SOAPCLIENT_PARSE), `0x80244010`
(WU_E_PT_EXCEEDED_MAX_SERVER_TRIPS), `0x8007000E` (E_OUTOFMEMORY) during scan; WU scan >2h;
svchost/WUA >2 GB RAM; ESENT Event ID 455/489 referencing DataStore.edb; DataStore.edb >1 GB
(normal 10–100 MB).

**Cause:** interrupted write / inconsistent `edb.log` journal, years of accumulated scan history,
disk I/O errors, or AV scanning the .edb during writes. Server 2012 R2 has an ESENT bug with large catalogs.

## Steps
1. Confirm size and ESENT errors:
   ```powershell
   (Get-Item "$env:SystemRoot\SoftwareDistribution\DataStore\DataStore.edb").Length/1MB
   Get-WinEvent -LogName Application -MaxEvents 200 | ?{$_.Id -in 455,489 -and $_.ProviderName -match 'ESENT'}
   ```
2. Rebuild the datastore by resetting SoftwareDistribution (this discards scan history, which is safe):
   ```powershell
   Stop-Service wuauserv,bits -Force -EA SilentlyContinue
   Rename-Item "$env:SystemRoot\SoftwareDistribution" "$env:SystemRoot\SoftwareDistribution.old" -Force
   Start-Service wuauserv,bits
   ```
3. Force a fresh scan so a new DataStore.edb is built; confirm the new file is small (<100 MB).
4. Exclude `DataStore.edb` from on-access AV scanning if AV interference recurs.

## Escalation
- Server 2012 R2 large-catalog ESENT hang → install the latest SSU + WU client update first, then reset.
- Persistent OOM during scan → increase instance memory temporarily for the initial catalog scan.
