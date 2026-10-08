# Stalled feature update / in-place upgrade state (NOT store corruption)

**Signatures:** `0xC1900101` (SAFE_OS / SECOND_BOOT phase), `0x80240020`
(WU_E_NO_INTERACTIVE_USER), `0x80070490` (ERROR_NOT_FOUND) after a partial upgrade; system
between OS versions; `Windows.old` / `$WINDOWS.~BT` present with no completed upgrade; LCU "not
applicable to this image"; unexpected build number.

**Why it matters:** a half-completed in-place upgrade leaves mixed package state. RestoreHealth
against a half-upgraded image wastes the maintenance window — resolve the upgrade state first.

## Steps
1. Determine the true build vs the intended one, and detect leftover upgrade folders:
   ```powershell
   (Get-CimInstance Win32_OperatingSystem).Version
   Get-ChildItem "$env:SystemRoot\Windows.old","$env:SystemDrive\`$WINDOWS.~BT","$env:SystemDrive\`$WINDOWS.~WS" -EA SilentlyContinue
   ```
2. Decide: complete the upgrade, or roll it back. Do not attempt a normal LCU until the OS is on a single consistent build.
3. If rolling back and within the window, use the built-in rollback; otherwise clean the leftover folders only after confirming the running OS is consistent:
   ```powershell
   DISM /Online /Cleanup-Image /StartComponentCleanup
   ```
4. Re-verify the LCU is now "applicable" before retrying the patch scan.

## Escalation
- Server SAC→LTSC or 2016→2019 mixed state → may require finishing the upgrade or rebuilding from a known-good AMI.
- GPO offering feature updates to a server inappropriately → block feature updates via policy so patching targets LCUs only.
