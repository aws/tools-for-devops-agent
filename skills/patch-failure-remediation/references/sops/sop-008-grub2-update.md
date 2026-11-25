# SOP-008: Resolve GRUB2 Update Issues During Kernel Patching

| Field | Value |
|-------|-------|
| ID | SOP-008 |
| Category | grub2_update |
| Severity | Critical |
| Risk Level | High |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, CentOS 7 |
| Requires Reboot | Yes |
| Estimated Duration | 240 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Kernel patch installs but GRUB configuration not updated
- "grub2-mkconfig" or "grub2-install" failures in patch logs
- Instance fails to boot into new kernel after patch reboot
- "/boot partition full" preventing kernel installation
- GRUB menu shows stale or missing kernel entries
- "error: /vmlinuz-<version> has invalid signature" on Secure Boot systems
- Post-patch reboot hangs at GRUB or drops to rescue shell

## Root Cause

GRUB2 update failures during patching caused by:

- /boot partition full with old kernel artifacts (initramfs, vmlinuz, System.map files accumulate ~250MB per kernel)
- GRUB configuration file corruption from interrupted grub2-mkconfig
- Incorrect root device UUID in GRUB config after volume changes or snapshot restores
- grub2-mkconfig fails due to missing dependencies (os-prober, dracut, grub2-tools)
- EFI partition mount issues on UEFI systems (/boot/efi not mounted or vfat filesystem errors)
- BLS (Boot Loader Specification) entries in /boot/loader/entries/ inconsistent with installed kernels
- SELinux contexts on /boot files preventing grub2-mkconfig from reading them

This is a CRITICAL SOP because GRUB misconfiguration can render the instance unbootable. An AMI/snapshot backup should exist before kernel patching.

## Related Failure Patterns

- SOP-002 (Disk Full) — /boot full is the most common trigger for this SOP
- SOP-004 (Corrupt RPM DB) — RPM database issues can leave kernel packages in an inconsistent state

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Backup/AMI of instance taken before kernel patching
- /boot partition accessible and writable

## Diagnosis

Determine boot method (BIOS vs UEFI) and current kernel:

```bash
[ -d /sys/firmware/efi ] && echo "UEFI" || echo "BIOS"; uname -r; ls /boot/vmlinuz-* 2>/dev/null
```

Check BLS entries on AL2023/RHEL 9:

```bash
ls -la /boot/loader/entries/ 2>/dev/null; cat /boot/loader/entries/*.conf 2>/dev/null | grep -E "^(title|linux|initrd)"
```

## Remediation Steps

### Step 1: Check /boot partition space

```bash
df -h /boot; ls -la /boot/vmlinuz-* 2>/dev/null | wc -l; echo "Boot check done"
```

Expected output: Disk usage and kernel count
On failure: abort

### Step 2: Remove old kernel files if /boot is full (keep current + 1 previous)

```bash
CURRENT=$(uname -r); if command -v package-cleanup &>/dev/null; then package-cleanup --oldkernels --count=2 -y; elif command -v dnf &>/dev/null; then dnf remove --oldinstallonly --setopt installonly_limit=2 -y; fi; echo "Old kernels removed, current: $CURRENT"
```

Expected output: "Old kernels removed, current: <version>"
On failure: continue

### Step 3: Verify GRUB configuration file exists

```bash
GRUB_CFG=""; [ -f /boot/grub2/grub.cfg ] && GRUB_CFG="/boot/grub2/grub.cfg"; EFI_GRUB=$(ls /boot/efi/EFI/*/grub.cfg 2>/dev/null | head -1); [ -n "$EFI_GRUB" ] && GRUB_CFG="$EFI_GRUB"; [ -f /etc/grub2.cfg ] && GRUB_CFG="/etc/grub2.cfg"; echo "GRUB_CFG: ${GRUB_CFG:-NOT FOUND}"
```

Expected output: "GRUB_CFG: /path/to/grub.cfg"
On failure: abort

### Step 4: Regenerate GRUB2 configuration

```bash
if [ -d /boot/efi/EFI ]; then grub2-mkconfig -o /boot/efi/EFI/$(ls /boot/efi/EFI/ | grep -iv BOOT | head -1)/grub.cfg; else grub2-mkconfig -o /boot/grub2/grub.cfg; fi; echo "GRUB config regenerated"
```

Expected output: "GRUB config regenerated"
On failure: abort

### Step 5: Verify default kernel is set correctly

```bash
grubby --default-kernel; grubby --default-index; echo "Default kernel verified"
```

Expected output: Kernel path, index number, "Default kernel verified"
On failure: continue

## Validation

```bash
grub2-mkconfig -o /dev/null 2>&1 | tail -5; grubby --default-kernel | grep -q vmlinuz && echo "GRUB OK" || echo "GRUB FAILED"
```

Expected: "GRUB OK"

## Rollback

```bash
PREV_KERNEL=$(grubby --info=ALL | grep "^kernel=" | sed -n '2p' | cut -d= -f2)
if [ -n "$PREV_KERNEL" ]; then grubby --set-default="$PREV_KERNEL"; echo "Reverted to: $PREV_KERNEL"; else echo "No previous kernel found"; fi
```

## Escalation

If the instance is unbootable after kernel patching:
- Use EC2 Serial Console (if enabled) to access GRUB menu and select previous kernel
- Detach the root volume, attach to a rescue instance, mount /boot, and fix grub.cfg manually
- Restore from the pre-patch AMI/snapshot
- For UEFI instances, the EFI System Partition may need to be remounted and the bootloader reinstalled with `grub2-install --target=x86_64-efi`
