# Pending servicing transactions (clear BEFORE any DISM repair)

**Signatures:** `0x800F0922` (CBS_E_INSTALLERS_FAILED), `0x800F081F` (CBS_E_SOURCE_MISSING),
`0x800F0831` with pending references; DISM "packages are pending servicing"; CBS.log
"transaction halted"/"pending.xml"; boot slow while TrustedInstaller retries.

**Why first:** a halted transaction poisons SSU installs and RestoreHealth alike — both will
loop or fail until the transaction is reverted or completed.

## Steps
1. Identify pending operations and the marker file:
   ```powershell
   DISM /Online /Get-Packages /Format:Table | Select-String "Pending"
   Test-Path "$env:SystemRoot\servicing\Packages\pending.xml"
   ```
2. Revert pending actions:
   ```powershell
   DISM /Online /Cleanup-Image /RevertPendingActions
   ```
3. Rename `pending.xml` ONLY if stale (>24h) — a recent one may be a valid in-flight operation:
   ```powershell
   $x="$env:SystemRoot\servicing\Packages\pending.xml"
   if((Test-Path $x) -and (((Get-Date)-(Get-Item $x).LastWriteTime).TotalHours -gt 24)){Rename-Item $x "$x.bak_$(Get-Date -Format yyyyMMdd)" -Force}
   ```
4. Clear orphaned session state:
   ```powershell
   Stop-Service wuauserv,TrustedInstaller -Force -EA SilentlyContinue
   Remove-Item 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\SessionsPending' -Recurse -Force -EA SilentlyContinue
   Start-Service TrustedInstaller -EA SilentlyContinue
   ```
5. **Reboot** — some transactions can only finalize during boot.

## Escalation
- Boot loop from a pending transaction → boot Safe Mode (`bcdedit /set {default} safeboot minimal`) then RevertPendingActions.
- Specific stuck package → `DISM /Online /Remove-Package /PackageName:<name>`.
- Rollback: restore the renamed `pending.xml.bak_*` if a revert removed a valid operation.
