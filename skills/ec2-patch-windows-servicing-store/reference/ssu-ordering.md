# Servicing Stack Update (SSU) ordering (install BEFORE the LCU)

**Signatures:** `0x80070BC9` (ERROR_FAIL_NOACTION_REBOOT), `0x80073701`
(ERROR_SXS_ASSEMBLY_MISSING) on LCU; CBS.log "Servicing stack must be updated before this
package can be installed"; LCU downloads then fails at "Installing"; Server 2016 stuck on old CU.

**Why:** the servicing stack is what *processes* update manifests. An outdated SSU cannot parse a
newer LCU manifest, and the failure surfaces as store corruption — so RestoreHealth "fixes"
nothing. SSU must be current first.

## Steps
1. Report OS build + servicing stack:
   ```powershell
   $os=Get-CimInstance Win32_OperatingSystem
   "$($os.Caption) Build $($os.BuildNumber).$((Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR)"
   ```
2. Find pending SSU vs LCU (SSU installs separately on 2016; combined on 2019+):
   ```powershell
   $s=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software'").Updates
   $s|?{$_.Title -match 'Servicing Stack'}|%{ "SSU: $($_.Title)" }
   ```
3. Install the SSU first (download+install just the "Servicing Stack" updates via
   `Microsoft.Update.Session`; ResultCode 2=Succeeded, 3=SucceededWithErrors), then let the LCU proceed.
4. Re-evaluate the component store: `DISM /Online /Cleanup-Image /StartComponentCleanup`.
5. Verify no SSU remains pending before installing the LCU.

## Escalation
- Server 2012 R2: download SSU from Microsoft Update Catalog, install via `wusa.exe`; SHA-2 chain may be required.
- Server 2016: specific LCUs require a specific SSU version — check the KB prerequisites.
- WSUS: ensure the SSU (not just the LCU) is approved.
- 2019+: ensure the combined SSU+LCU package is being offered.
- Since 2024, a SafeOS/WinRE update may also be required.
- **SSU is forward-only — it cannot be uninstalled.**
