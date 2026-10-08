# BitLocker blocking boot-critical updates

**Signatures:** patch requires reboot but the reboot enters BitLocker recovery, `0x80070032`
"request not supported", updates install then the system enters recovery after reboot, a UEFI/firmware
or Secure Boot update triggers the recovery-key prompt, "Preparing to configure Windows" hangs then
rolls back.

**High-risk.** Boot-critical updates change TPM PCR measurements; if BitLocker isn't suspended, the
reboot demands the 48-digit recovery key. **Confirm the recovery key is available BEFORE proceeding.**

## Diagnose
```powershell
Get-BitLockerVolume -EA SilentlyContinue | Select MountPoint,ProtectionStatus,VolumeStatus,EncryptionMethod
Get-Tpm -EA SilentlyContinue | Select TpmPresent,TpmReady
# firmware/secure-boot updates pending (most likely to trigger recovery):
(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software'").Updates | ? {$_.Title -match 'firmware|UEFI|Secure Boot|BIOS'} | Select Title
```

## Suspend BitLocker for ONE reboot BEFORE patching
```powershell
Get-BitLockerVolume -EA SilentlyContinue | ? {$_.ProtectionStatus -eq 'On'} | % {
  Suspend-BitLocker -MountPoint $_.MountPoint -RebootCount 1
  "suspended $($_.MountPoint) for 1 reboot"
}
```
`-RebootCount 1` auto-resumes protection after the single reboot — the patch reboot won't demand the key.

## Verify (before reboot)
```powershell
$v=Get-BitLockerVolume -MountPoint C: -EA SilentlyContinue
if(-not $v -or $v.ProtectionStatus -eq 'Off'){"BITLOCKER SUSPENDED - safe to patch/reboot"}else{"STILL PROTECTED - do NOT reboot"}
```

## Escalation / recovery
- If recovery is already triggered: enter the 48-digit key via EC2 Serial Console; get the key from AD / Azure AD / customer KMS.
- EC2 without TPM: BitLocker uses a key/password protector or network unlock — verify config.
- Consider EBS encryption instead of in-guest BitLocker if BitLocker isn't required.
- Rollback: `Resume-BitLocker -MountPoint <mp>` to re-protect immediately.
