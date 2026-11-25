# SOP-065: Resolve Windows Patch Failure Due to Pending Servicing Transactions

| Field | Value |
|-------|-------|
| ID | SOP-065 |
| Category | windows_pending_servicing_transactions |
| Severity | High |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x800F0831` ("CBS_E_STORE_CORRUPTION") with pending transaction references
- `0x800F081F` ("CBS_E_SOURCE_MISSING") — source files needed for pending operation
- `0x800F0922` ("CBS_E_INSTALLERS_FAILED") due to stalled transaction
- DISM shows "Packages are pending servicing"
- New updates cannot install because previous transaction is incomplete
- CBS.log shows "transaction halted" or "pending.xml" errors
- Boot takes extremely long as TrustedInstaller retries a failed transaction

## Root Cause

Pending servicing transactions occur when:

- Previous update installation was interrupted mid-transaction (crash, power loss)
- TrustedInstaller started a multi-package install but failed partway through
- Reboot was required to complete servicing but never happened
- pending.xml in CBS folder references packages that no longer exist
- In-place upgrade stalled leaving a partial transaction
- Server 2016: Feature update transaction left in intermediate state
- Multiple cumulative updates queued but system rebooted during processing

## Related Failure Patterns

- SOP-051 (Corrupt CBS) — pending transactions can corrupt the store
- SOP-055 (Pending Install) — pending state vs pending transactions
- SOP-058 (SSU Prerequisite) — SSU transaction must complete before LCU

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance should be rebooted after remediation to complete any valid pending operations

## Diagnosis

```powershell
$pending = & DISM /Online /Get-Packages 2>&1 | Select-String "Install Pending|Uninstall Pending"
Write-Output "Pending packages: $($pending.Count)"
$pending | ForEach-Object { Write-Output $_.Line }
$cbsPending = Test-Path "$env:SystemRoot\servicing\Packages\pending.xml"
Write-Output "pending.xml exists: $cbsPending"
```

## Remediation Steps

### Step 1: Identify pending servicing operations

```powershell
$packages = & DISM /Online /Get-Packages /Format:Table 2>&1
$pending = $packages | Select-String "Pending"
Write-Output "Pending servicing operations: $($pending.Count)"
$pending | ForEach-Object { Write-Output "  $($_.Line.Trim())" }
$pendingXml = "$env:SystemRoot\servicing\Packages\pending.xml"
Write-Output "pending.xml: $(if (Test-Path $pendingXml) { 'EXISTS' } else { 'NOT FOUND' })"
```

Expected output: Pending operations listed
On failure: continue

### Step 2: Attempt to revert pending actions via DISM

```powershell
$result = & DISM /Online /Cleanup-Image /RevertPendingActions 2>&1
$result | Select-String "operation completed|error|pending actions"
Write-Output "RevertPendingActions exit: $LASTEXITCODE"
```

Expected output: "operation completed successfully" or exit code reported
On failure: continue

### Step 3: Clear pending.xml if stale

```powershell
$pendingXml = "$env:SystemRoot\servicing\Packages\pending.xml"
if (Test-Path $pendingXml) {
    $age = ((Get-Date) - (Get-Item $pendingXml).LastWriteTime).TotalHours
    if ($age -gt 24) {
        Rename-Item $pendingXml "$pendingXml.bak_$(Get-Date -Format 'yyyyMMdd')" -Force
        Write-Output "Stale pending.xml renamed (age: $([math]::Round($age))h)"
    } else { Write-Output "pending.xml is recent ($([math]::Round($age))h) — may be valid" }
} else { Write-Output "No pending.xml found" }
```

Expected output: pending.xml handled or not present
On failure: continue

### Step 4: Reset component-based servicing state

```powershell
$cbsReg = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing'
$stamp = Get-Date -Format 'yyyyMMdd'
$backupDir = "$env:SystemRoot\Temp\SOP065_regbackup_$stamp"
# Reset the backup dir fresh per run so a second run the same day cannot clobber a good backup with empty exports
if (Test-Path $backupDir) { Remove-Item $backupDir -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $backupDir -Force -ErrorAction SilentlyContinue | Out-Null

# Back up the keys BEFORE any removal so they can be restored on rollback
& reg export 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\SessionsPending' "$backupDir\SessionsPending.reg" /y 2>&1 | Out-Null
# RebootPending is itself a SUBKEY (its mere existence signals a pending reboot), not a registry value - back it up as a key with reg export, exactly like SessionsPending. Do NOT export the whole Component Based Servicing tree (large; a wholesale re-import on rollback would clobber unrelated servicing state changed after the backup). Step 4 only mutates the SessionsPending and RebootPending subkeys.
& reg export 'HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending' "$backupDir\RebootPending.reg" /y 2>&1 | Out-Null
Write-Output "Backed up SessionsPending and RebootPending subkeys to $backupDir"

# Only clear SessionsPending when it is SAFE — gated the same way as pending.xml in Step 3:
# a recent (in-progress) transaction is left alone; only a stale one (>24h) is removed.
$pendingXml = "$env:SystemRoot\servicing\Packages\pending.xml"
$xmlRecent = (Test-Path $pendingXml) -and ((((Get-Date) - (Get-Item $pendingXml).LastWriteTime).TotalHours) -le 24)
$spKey = "$cbsReg\SessionsPending"
if ($xmlRecent) {
    # Genuine transaction may be in progress — leave BOTH SessionsPending and RebootPending untouched (wiping RebootPending here would strip real servicing state). Do NOT bounce TrustedInstaller/wuauserv when we are leaving keys intact.
    Write-Output "pending.xml is recent — genuine transaction may be in progress; leaving SessionsPending and RebootPending intact"
} elseif (Test-Path $spKey) {
    # We are about to mutate servicing state — stop the servicing services only in this removal branch
    Stop-Service wuauserv,TrustedInstaller -Force -ErrorAction SilentlyContinue
    # Only remove each key if its backup .reg was actually produced, so Rollback can always restore it
    if (Test-Path "$backupDir\SessionsPending.reg") {
        Remove-Item $spKey -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Output "SessionsPending backup missing - not removing"
    }
    if (Test-Path "$backupDir\RebootPending.reg") {
        Remove-Item "$cbsReg\RebootPending" -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Output "RebootPending backup missing - not removing"
    }
    Write-Output "Stale SessionsPending and RebootPending removed (backup at $backupDir)"
    Start-Service TrustedInstaller -ErrorAction SilentlyContinue
    Start-Service wuauserv -ErrorAction SilentlyContinue
} else {
    if (Test-Path "$backupDir\RebootPending.reg") {
        Remove-Item "$cbsReg\RebootPending" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Output "No SessionsPending key present; cleared stale RebootPending key"
    } else {
        Write-Output "No SessionsPending key present; RebootPending backup missing - not removing"
    }
}
Write-Output "CBS servicing state reset"
```

Expected output: "CBS servicing state reset"
On failure: continue

### Step 5: Verify no blocking pending transactions remain

```powershell
$pending = & DISM /Online /Get-Packages 2>&1 | Select-String "Install Pending|Uninstall Pending"
if ($pending.Count -eq 0) { Write-Output "PENDING TRANSACTIONS CLEARED" }
else { Write-Output "STILL PENDING: $($pending.Count) package(s)" }
```

Expected output: "PENDING TRANSACTIONS CLEARED"
On failure: abort

## Validation

```powershell
$pending = & DISM /Online /Get-Packages 2>&1 | Select-String "Install Pending|Uninstall Pending"
$pendingXml = Test-Path "$env:SystemRoot\servicing\Packages\pending.xml"
if ($pending.Count -eq 0 -and -not $pendingXml) { "TRANSACTION REMEDIATION OK" }
else { "STILL PENDING: Packages=$($pending.Count) XML=$pendingXml" }
```

Expected: "TRANSACTION REMEDIATION OK"

## Rollback

```powershell
# Restore pending.xml from backup
$bak = Get-ChildItem "$env:SystemRoot\servicing\Packages\pending.xml.bak_*" -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($bak) {
    Rename-Item $bak.FullName "$env:SystemRoot\servicing\Packages\pending.xml" -Force
    Write-Output "pending.xml restored from backup"
} else { Write-Output "No pending.xml backup to restore" }

# Restore the CBS registry keys (SessionsPending / RebootPending) removed in Step 4
$regBackup = Get-ChildItem "$env:SystemRoot\Temp\SOP065_regbackup_*" -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
if ($regBackup) {
    if (Test-Path "$($regBackup.FullName)\SessionsPending.reg") { & reg import "$($regBackup.FullName)\SessionsPending.reg" 2>&1 | Out-Null }
    # Re-import ONLY the RebootPending subkey removed in Step 4 - never re-import the whole CBS subtree
    if (Test-Path "$($regBackup.FullName)\RebootPending.reg") { & reg import "$($regBackup.FullName)\RebootPending.reg" 2>&1 | Out-Null }
    Write-Output "CBS registry keys restored from $($regBackup.FullName)"
} else { Write-Output "No CBS registry backup to restore" }
```

## Escalation

If pending transactions cannot be cleared:
- Reboot the instance — some transactions can only complete during boot
- If boot loops due to pending transaction: boot to Safe Mode and run RevertPendingActions
- For Server 2012 R2: use `bcdedit /set {default} safeboot minimal` to force Safe Mode boot
- Check CBS.log for specific package causing transaction failure
- Consider `DISM /Online /Remove-Package /PackageName:<stuck_package>` for specific offenders
- If in-place upgrade transaction is stuck: may need to complete or roll back the upgrade
