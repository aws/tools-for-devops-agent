# /boot partition full blocking kernel install

**Signatures:** "No space left on device" specifically on /boot, "insufficient space in /boot",
"cpio: write failed - No space left on device" unpacking kernel-*, initramfs/initrd generation
fails, `df /boot` at 95–100%. /boot is a small fixed partition (~200–500MB on older AMIs); each
kernel uses 30–80MB, so it fills after 3–5 kernels.

**Never remove the running kernel** (`uname -r`); keep it + one previous.

## Prune old kernels (RPM)
```bash
dnf remove --oldinstallonly --setopt installonly_limit=2 -y 2>&1 \
  || package-cleanup --oldkernels --count=2 -y 2>&1
```

## Prune old kernels (DEB)
```bash
CUR=$(uname -r)
OLD=$(dpkg -l 'linux-image-*' | grep '^ii' | awk '{print $2}' | grep -v "$CUR" | grep -vE 'linux-image-(generic|aws)')
[ -n "$OLD" ] && apt-get purge -y $OLD && apt-get autoremove -y
```

## Clear orphaned boot files (not matching an installed kernel, not running)
```bash
CUR=$(uname -r)
for f in /boot/vmlinuz-* /boot/initramfs-* /boot/initrd.img-* /boot/System.map-* /boot/config-*; do
  [ -f "$f" ] || continue; VER=$(echo "$f" | sed 's|/boot/[^-]*-||')
  [ "$VER" != "$CUR" ] && ! (rpm -qa 2>/dev/null | grep -qF "$VER") && ! (dpkg -l 2>/dev/null | grep -qF "$VER") && rm -f "$f" && echo "removed orphan $f"
done
# still tight? rescue/kdump images:
[ "$(df /boot|tail -1|awk '{print $4}')" -lt 102400 ] && rm -f /boot/vmlinuz-0-rescue-* /boot/initramfs-0-rescue-*
```

## Prevent recurrence + verify
```bash
grep -q '^installonly_limit' /etc/dnf/dnf.conf 2>/dev/null && sed -i 's/^installonly_limit=.*/installonly_limit=2/' /etc/dnf/dnf.conf || echo 'installonly_limit=2' >> /etc/dnf/dnf.conf 2>/dev/null
df -h /boot; echo "free KB: $(df /boot|tail -1|awk '{print $4}') (want >=102400)"
```

## Escalation
- /boot too small even after pruning (legacy 200MB) → resize via snapshot→larger-/boot workflow.
- UEFI: also check `/boot/efi` space.
- Only the running kernel left and still full → oversized initramfs (dracut modules/firmware blobs); trim dracut.
