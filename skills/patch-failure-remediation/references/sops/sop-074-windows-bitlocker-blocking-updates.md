# SOP-074: Resolve Windows Patch Failure Due to Bitlocker/Encryption Blocking Updates

| Field | Value |
|-------|-------|
| ID | SOP-074 |
| Category | windows_bitlocker_blocking_updates |
| Severity | Medium |
| Risk Level | High |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch requires reboot but BitLocker triggers recovery mode on reboot
- `0x80070032` ("The request is not supported") during update installation
- Updates install but system enters BitLocker recovery after reboot
- UEFI firmware update triggers BitLocker recovery key prompt
- Secure Boot update blocked because PCR measurements will change
- System hangs at "Preparing to configure Windows" then rolls back

## Root Cause

BitLocker/encryption blocks update completion when:

- Updates modify boot components that change TPM PCR measurements
- UEFI/firmware updates alter Secure Boot state
- BitLocker is not suspended before boot-critical updates
- TPM is in locked state or has stale PCR policy
- Recovery key not available after boot component update
- Windows RE (Recovery Environment) partition update triggers recovery
- Dual-boot configuration with BitLocker changes boot order

## Related Failure Patterns

- SOP-055 (Pending Install) — BitLocker recovery can create stuck pending state
- SOP-065 (Pending Transactions) — rolled-back updates leave pending transactions
- SOP-057 (Driver Update) — firmware/driver updates most likely to trigger

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding that EC2 instances rarely have BitLocker but some customers enable it
- Recovery key must be available before proceeding

## Diagnosis

```powershell
$bl = Get-BitLockerVolume -ErrorAction SilentlyContinue
if ($bl) {
    $bl | ForEach-Object { Write-Output "Volume $($_.MountPoint): Protection=$($_.ProtectionStatus) Encryption=$($_.VolumeStatus)" }
} else { Write-Output "BitLocker not detected or cmdlet unavailable" }
$tpm = Get-Tpm -ErrorAction SilentlyContinue
if ($tpm) { Write-Output "TPM Present=$($tpm.TpmPresent) Ready=$($tpm.TpmReady)" }
```

## Remediation Steps

### Step 1: Check BitLocker status on all volumes

```powershell
$blModule = Get-Module BitLocker -ListAvailable
if ($blModule) {
    $volumes = Get-BitLockerVolume -ErrorAction SilentlyContinue
    if ($volumes) {
        $volumes | ForEach-Object {
            Write-Output "$($_.MountPoint): Protection=$($_.ProtectionStatus) Status=$($_.VolumeStatus) Method=$($_.EncryptionMethod)"
        }
        $protected = $volumes | Where-Object { $_.ProtectionStatus -eq 'On' }
        Write-Output "Protected volumes: $($protected.Count)"
    } else { Write-Output "No BitLocker volumes found" }
} else { Write-Output "BitLocker module not available — feature not installed" }
```

Expected output: BitLocker status or not present
On failure: continue

### Step 2: Suspend BitLocker protection for next reboot

```powershell
$protected = Get-BitLockerVolume -ErrorAction SilentlyContinue | Where-Object { $_.ProtectionStatus -eq 'On' }
if ($protected) {
    foreach ($vol in $protected) {
        Suspend-BitLocker -MountPoint $vol.MountPoint -RebootCount 1 -ErrorAction SilentlyContinue
        Write-Output "Suspended BitLocker on $($vol.MountPoint) for 1 reboot"
    }
} else { Write-Output "No BitLocker protection active — issue may be elsewhere" }
```

Expected output: BitLocker suspended or not active
On failure: continue

### Step 3: Verify TPM state if applicable

```powershell
$tpm = Get-Tpm -ErrorAction SilentlyContinue
if ($tpm) {
    Write-Output "TPM Present: $($tpm.TpmPresent)"
    Write-Output "TPM Ready: $($tpm.TpmReady)"
    Write-Output "TPM Enabled: $($tpm.TpmEnabled)"
    if ($tpm.TpmPresent -and -not $tpm.TpmReady) {
        Write-Output "WARNING: TPM present but not ready"
    }
} else { Write-Output "No TPM (virtual instance — BitLocker likely uses password/key protector)" }
```

Expected output: TPM status or virtual note
On failure: continue

### Step 4: Check for UEFI/firmware updates that may trigger recovery

```powershell
$searcher = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()
$updates = $searcher.Search("IsInstalled=0 and Type='Software'").Updates
$firmware = $updates | Where-Object { $_.Title -match 'firmware|UEFI|Secure Boot|BIOS' }
if ($firmware.Count -gt 0) {
    Write-Output "WARNING: Firmware updates pending that may trigger BitLocker recovery:"
    $firmware | ForEach-Object { Write-Output "  $($_.Title)" }
} else { Write-Output "No firmware updates pending" }
```

Expected output: Firmware update status
On failure: continue

### Step 5: Verify BitLocker is suspended and patching can proceed

```powershell
$vol = Get-BitLockerVolume -MountPoint "C:" -ErrorAction SilentlyContinue
if ($vol) {
    if ($vol.ProtectionStatus -eq 'Off') { Write-Output "BITLOCKER REMEDIATION OK: Protection suspended" }
    else { Write-Output "BITLOCKER STILL ON: Cannot guarantee safe reboot" }
} else { Write-Output "BITLOCKER REMEDIATION OK: No BitLocker on system" }
```

Expected output: "BITLOCKER REMEDIATION OK"
On failure: abort

## Validation

```powershell
$vol = Get-BitLockerVolume -MountPoint "C:" -ErrorAction SilentlyContinue
if (-not $vol -or $vol.ProtectionStatus -eq 'Off') { "BITLOCKER REMEDIATION OK" }
else { "BITLOCKER STILL BLOCKING" }
```

Expected: "BITLOCKER REMEDIATION OK"

## Rollback

```powershell
# Resume BitLocker protection immediately
$vol = Get-BitLockerVolume -ErrorAction SilentlyContinue | Where-Object { $_.ProtectionStatus -eq 'Off' -and $_.VolumeStatus -ne 'FullyDecrypted' }
$vol | ForEach-Object { Resume-BitLocker -MountPoint $_.MountPoint }
Write-Output "BitLocker protection resumed"
```

## Escalation

If BitLocker recovery is triggered:
- Recovery key is needed — check AD, Azure AD, or customer key management
- For EC2 without TPM: BitLocker uses network unlock or startup key — verify configuration
- If system is in recovery: must enter 48-digit recovery key via EC2 Serial Console
- Consider disabling BitLocker on EC2 if not required (encryption at rest via EBS encryption)
- For persistent issues: add WU executables to BitLocker PCR exemption policy
- Contact customer security team for recovery key and encryption policy guidance
