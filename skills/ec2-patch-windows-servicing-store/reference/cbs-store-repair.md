# CBS / WinSxS component store repair (only after pending + SSU are handled)

**Signatures:** `0x80073712` ("component store corrupted"), `0x800F0831`
(CBS_E_STORE_CORRUPTION) with no pending-transaction or SSU cause, `0x800736B3`
("referenced assembly not installed"), Error 14098; DISM ScanHealth reports corruption;
CBS.log "store corruption"/"manifest missing".

**Preconditions:** pending transactions cleared, SSU current, ≥5 GB free on C:.

## Steps
1. Assess: `DISM /Online /Cleanup-Image /ScanHealth`.
2. Repair: `DISM /Online /Cleanup-Image /RestoreHealth`.
   - On an isolated/patched fleet WU is blocked as the repair source — supply an explicit source:
     `DISM /Online /Cleanup-Image /RestoreHealth /Source:WIM:<path>\install.wim:<idx> /LimitAccess`.
   - **`/Source` build must match the running OS build+UBR exactly** or RestoreHealth fails generically.
3. System files: `sfc /scannow` (only after the store is healthy — SFC uses the store to repair).
4. If WU components are implicated, reset them:
   ```powershell
   Stop-Service wuauserv,cryptSvc,bits,msiserver -Force -EA SilentlyContinue
   Rename-Item "$env:SystemRoot\SoftwareDistribution" "$env:SystemRoot\SoftwareDistribution.old" -Force -EA SilentlyContinue
   Rename-Item "$env:SystemRoot\System32\catroot2" "$env:SystemRoot\System32\catroot2.old" -Force -EA SilentlyContinue
   Start-Service wuauserv,cryptSvc,bits,msiserver -EA SilentlyContinue
   ```
5. Verify: `DISM /Online /Cleanup-Image /CheckHealth` reports **healthy**.

## Rollback
Restore `SoftwareDistribution.old` / `catroot2.old` if the reset caused a regression.

## Escalation
- RestoreHealth still fails → confirm WU reachability or supply `/Source`; read CBS.log for the exact missing manifest.
- Severe corruption → in-place upgrade repair or rebuild from AMI.
