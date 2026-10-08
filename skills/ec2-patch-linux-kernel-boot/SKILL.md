---
name: ec2-patch-linux-kernel-boot
description: >-
  Recover a Linux EC2 instance whose kernel patching fails or leaves it
  unbootable — faults around kernel install and boot config: a full /boot
  partition blocking the new kernel, GRUB2/BLS regeneration failures, kernel
  headers / DKMS rebuild failures for third-party modules (ENA, EFA, NVIDIA,
  CrowdStrike), and Oracle Linux UEK-vs-RHCK dual-kernel conflicts. Use when a
  patch run fails with "No space left on device" on /boot, "grub2-mkconfig"
  errors, the instance fails to boot the new kernel or drops to a rescue shell,
  "Unable to find kernel headers for the running kernel", "DKMS module build
  failed", or "kernel-uek conflicts with kernel". The correct fix depends on the
  fault — /boot-full needs old-kernel pruning that preserves the running kernel,
  DKMS needs the matching -devel/headers, and a UEK/RHCK clash needs disabling
  the unused kernel repo. High-risk (a bad GRUB config can render the instance
  unbootable) — back up / snapshot before kernel work.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Patching, Kernel, Boot"
  domains: "EC2, SSM, Patch Manager, kernel, GRUB2, BLS, DKMS, UEK"
  platforms: "Linux"
  supported-os: "Amazon Linux 2, Amazon Linux 2023, RHEL 7, RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, CentOS 7, SLES 12, SLES 15, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04"
  operation-type: "read-and-mutate"
---

# Recover Linux kernel patching / boot configuration

## When this applies
A kernel patch fails to install, fails to update the bootloader, or leaves the
instance unable to boot the new kernel. Instance is Online in SSM (or reachable
via serial console / rescue if already unbootable). If patching fails on the
package DB or repo access rather than the kernel/boot path, that is a different skill.

## ⚠️ High-risk domain — back up first
A wrong GRUB config or removing the running kernel can render the instance
**unbootable**. Ensure an AMI/EBS snapshot exists before kernel work, and never
remove the currently running kernel (`uname -r`).

## The key insight: identify the kernel/boot fault — fixes differ and some are dangerous
- **/boot partition full** (the most common blocker): `/boot` is a small, fixed partition (~200–500MB on older AMIs); each kernel uses 30–80MB, so it fills after a few. Prune **old** kernels while **keeping the running kernel + one previous**, and set `installonly_limit=2`. NOT a general `/` disk-full.
- **GRUB2 / BLS regeneration**: kernel installed but boot config stale/corrupt. Regenerate the correct config (UEFI `/boot/efi/EFI/.../grub.cfg` vs BIOS `/boot/grub2/grub.cfg`), fix BLS entries in `/boot/loader/entries/`, set the default kernel with `grubby`.
- **Kernel headers / DKMS**: third-party modules (ENA/EFA/NVIDIA/CrowdStrike) fail to build because `kernel-devel`/`linux-headers` for the running kernel is missing. Install the **matching-version** headers, then `dkms autoinstall`.
- **Oracle UEK vs RHCK conflict**: both UEK and RHCK repos enabled → unsolvable kernel transaction. Disable the **unused** kernel repo (keep the one that matches `uname -r`), and disable ksplice during patching if it interferes.

## Diagnosis first
- [ ] Step 1: Classify before acting (and confirm a backup exists):
  ```bash
  df -h /boot; ls -lhS /boot | head             # /boot space + biggest files
  uname -r; (rpm -qa kernel kernel-core 2>/dev/null | sort -V) || dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii'
  [ -d /sys/firmware/efi ] && echo UEFI || echo BIOS; ls /boot/loader/entries/ 2>/dev/null   # BLS
  uname -r | grep -q uek && echo "UEK" || echo "RHCK"; dnf repolist 2>/dev/null | grep -iE 'uek|rhck|ksplice'
  test -d /lib/modules/$(uname -r)/build && echo "headers present" || echo "headers MISSING"; dkms status 2>/dev/null
  ```
- [ ] Step 2: Route to the fault (load the matching reference):
  - /boot full → read [boot space](reference/boot-space.md).
  - GRUB/BLS / unbootable → read [grub and bls](reference/grub-and-bls.md).
  - kernel headers / DKMS → read [kernel headers dkms](reference/kernel-headers-dkms.md).
  - Oracle UEK/RHCK conflict → read [uek rhck conflict](reference/uek-rhck-conflict.md).

## Ordered recovery (preserve the running kernel; back up first)
- [ ] Step 3: **Free /boot if full** — prune old kernels keeping running+1, clear orphaned initramfs/vmlinuz, set `installonly_limit=2`. Do this first; a full /boot causes the GRUB/initramfs step to fail too.
- [ ] Step 4: **Install matching kernel headers and rebuild DKMS** if third-party modules are involved, so the new kernel boots with working drivers.
- [ ] Step 5: **Resolve a UEK/RHCK repo conflict** (disable the unused stream) if this is Oracle Linux and the kernel transaction won't solve.
- [ ] Step 6: **Regenerate the bootloader config** for the correct firmware (UEFI vs BIOS) and confirm the default kernel with `grubby`.
- [ ] Step 7: **Verify** before any reboot — GRUB config valid, running kernel present, /boot has headroom.

## Validation (check your own work before reporting success — especially before reboot)
- [ ] A snapshot/AMI backup exists (kernel/boot changes are the highest-risk).
- [ ] The **running kernel was NOT removed** and at least one previous kernel remains as fallback.
- [ ] `/boot` has ≥100MB free (kernel install + initramfs need headroom).
- [ ] `grub2-mkconfig -o /dev/null` succeeds and `grubby --default-kernel` points at a real `vmlinuz`.
- [ ] For DKMS: `/lib/modules/$(uname -r)/build` exists and `dkms status` shows modules installed.
Only after all pass is a reboot safe. If any fail, do not reboot — re-diagnose or restore from snapshot.

## Gotchas
- **Never remove the running kernel** (`uname -r`) — keep it plus one previous as fallback.
- **/boot is a separate small partition** — a general `df -h` looking healthy can still hide a 100%-full `/boot`; check `/boot` specifically.
- **Regenerate the config for the right firmware** — writing BIOS `grub.cfg` on a UEFI instance (or vice versa) leaves it unbootable; check `/sys/firmware/efi`.
- **UEK and RHCK repos both enabled = unsolvable kernel transaction** on Oracle Linux — disable the unused stream (match `uname -r`), don't try to force both.
- **DKMS needs the headers for the RUNNING kernel version**, not just any headers — install `kernel-devel-$(uname -r)` / `linux-headers-$(uname -r)` (UEK uses `kernel-uek-devel`).
- **Do not reboot to validate** — validate the GRUB config and kernel presence first; a reboot into a broken config needs serial-console/rescue recovery.
