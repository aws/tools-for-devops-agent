# GRUB2 / BLS regeneration & unbootable recovery

**Signatures:** kernel installed but GRUB not updated, "grub2-mkconfig"/"grub2-install" failures,
stale/missing kernel entries in the GRUB menu, "error: /vmlinuz-<ver> has invalid signature"
(Secure Boot), post-patch reboot hangs at GRUB or drops to rescue, BLS entries in
`/boot/loader/entries/` inconsistent with installed kernels.

**Back up first.** Determine firmware and write the CORRECT config path.

## Determine firmware + config path
```bash
[ -d /sys/firmware/efi ] && echo UEFI || echo BIOS
ls /boot/grub2/grub.cfg /boot/efi/EFI/*/grub.cfg /etc/grub2.cfg 2>/dev/null
ls -la /boot/loader/entries/ 2>/dev/null   # BLS (AL2023/RHEL9)
```

## Regenerate the config for the right firmware
```bash
if [ -d /boot/efi/EFI ]; then
  DIST=$(ls /boot/efi/EFI/ | grep -iv BOOT | head -1)
  grub2-mkconfig -o "/boot/efi/EFI/$DIST/grub.cfg"
else
  grub2-mkconfig -o /boot/grub2/grub.cfg
fi
grubby --default-kernel; grubby --default-index
```

## Verify (do NOT reboot to test)
```bash
grub2-mkconfig -o /dev/null 2>&1 | tail -3
grubby --default-kernel | grep -q vmlinuz && echo "GRUB OK" || echo "GRUB FAILED"
```

## Rollback / unbootable recovery
```bash
# set previous kernel as default:
PREV=$(grubby --info=ALL | awk -F= '/^kernel=/{print $2}' | sed -n '2p'); [ -n "$PREV" ] && grubby --set-default="$PREV"
```
If already unbootable:
- EC2 Serial Console → pick previous kernel at the GRUB menu.
- Or detach root volume → attach to rescue instance → mount /boot → fix grub.cfg/BLS → reattach.
- Or restore the pre-patch AMI/snapshot.
- UEFI: may need `grub2-install --target=x86_64-efi` after remounting the ESP.

## Escalation
- Missing os-prober/dracut/grub2-tools cause mkconfig to fail → install them first.
- SELinux contexts on /boot blocking mkconfig → `restorecon -Rv /boot`.
- Wrong root UUID after snapshot restore → fix the `root=` in the entry/GRUB defaults.
