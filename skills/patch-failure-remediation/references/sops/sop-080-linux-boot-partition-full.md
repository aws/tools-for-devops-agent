# SOP-080: Resolve /boot Partition Full Blocking Kernel Patching

| Field | Value |
|-------|-------|
| ID | SOP-080 |
| Category | boot_partition_full |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 7, RHEL 8, RHEL 9, CentOS 7, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, SLES 12, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-23 |

## Symptoms

- Kernel update fails with "No space left on device" specifically on /boot
- "insufficient space in /boot" or "not enough free space in /boot"
- DNF/YUM reports: "Error unpacking rpm package kernel-*: cpio: write failed - No space left on device"
- APT reports: "No space left on device" during linux-image installation
- initramfs/initrd generation fails during kernel post-install
- GRUB configuration update fails after kernel install
- `df /boot` shows 95-100% usage
- Patching partially succeeds but kernel package fails, leaving system non-compliant

## Root Cause

/boot partition is a small, fixed-size partition (typically 200MB-500MB on older AMIs) that accumulates old kernel packages over time. Each installed kernel consumes 30-80MB in /boot (vmlinuz + initramfs + System.map + config). After 3-5 kernel installations, /boot fills up and new kernels cannot be installed.

Common causes:
- `installonly_limit` not configured or set too high in yum/dnf (default keeps last 3 kernels)
- Ubuntu `autoremove` not run after kernel updates
- Manual kernel pinning preventing automatic removal
- Failed previous kernel installs leaving partial files (vmlinuz.old, initrd.img.old)
- RHEL/CentOS 7 with small 200MB /boot from legacy AMIs
- rescue kernels and kdump initramfs consuming additional space

## Related Failure Patterns

- SOP-002 (Disk Full) — general disk full; this SOP is specific to /boot
- SOP-008 (GRUB2 Update) — GRUB update may fail as a secondary symptom of /boot full

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- The currently running kernel must NOT be removed
- At least one previous known-good kernel should be retained as fallback

## Diagnosis

Check /boot usage and identify installed kernels:

```bash
echo "=== /boot usage ==="; df -h /boot; echo "=== Files in /boot by size ==="; ls -lhS /boot/ 2>/dev/null | head -20; echo "=== Installed kernels ==="; if command -v rpm &>/dev/null; then rpm -qa kernel kernel-core 2>/dev/null | sort -V; elif command -v dpkg &>/dev/null; then dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii'; fi; echo "=== Running kernel ==="; uname -r
```

## Remediation Steps

### Step 1: Identify current and old kernels

```bash
CURRENT=$(uname -r); echo "Running: $CURRENT"; echo "---"; if command -v rpm &>/dev/null; then rpm -qa kernel kernel-core 2>/dev/null | sort -V; elif command -v dpkg &>/dev/null; then dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii' | awk '{print $2}'; fi
```

Expected output: List of installed kernels with running kernel identified
On failure: abort

### Step 2: Remove old kernels (RPM-based: RHEL, CentOS, Amazon Linux, Oracle Linux)

```bash
if command -v dnf &>/dev/null; then
    dnf remove --oldinstallonly --setopt installonly_limit=2 -y 2>&1
    echo "Old kernels removed via dnf"
elif command -v package-cleanup &>/dev/null; then
    package-cleanup --oldkernels --count=2 -y 2>&1
    echo "Old kernels removed via package-cleanup"
elif command -v yum &>/dev/null; then
    CURRENT=$(uname -r | sed 's/.x86_64//;s/.aarch64//')
    for pkg in $(rpm -qa kernel kernel-core kernel-modules kernel-devel 2>/dev/null | grep -v "$CURRENT" | sort -V | head -n -1); do
        yum remove -y "$pkg" 2>&1
    done
    echo "Old kernels removed via yum"
else
    echo "SKIP: Not RPM-based"
fi
```

Expected output: "Old kernels removed" message
On failure: continue

### Step 3: Remove old kernels (DEB-based: Ubuntu, Debian)

```bash
if command -v dpkg &>/dev/null && [ -d /boot ] && command -v apt-get &>/dev/null; then
    CURRENT=$(uname -r)
    OLD_KERNELS=$(dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii' | awk '{print $2}' | grep -v "$CURRENT" | grep -v "linux-image-generic" | grep -v "linux-image-aws")
    if [ -n "$OLD_KERNELS" ]; then
        apt-get purge -y $OLD_KERNELS 2>&1
        apt-get autoremove -y 2>&1
        echo "Old kernels removed via apt"
    else
        echo "SKIP: No old kernels to remove (DEB)"
    fi
else
    echo "SKIP: Not DEB-based"
fi
```

Expected output: "Old kernels removed via apt" or "SKIP"
On failure: continue

### Step 4: Remove orphaned initramfs and vmlinuz files not matching installed kernels

```bash
CURRENT=$(uname -r)
INSTALLED=$(if command -v rpm &>/dev/null; then rpm -qa kernel kernel-core 2>/dev/null | sed 's/^kernel-core-//;s/^kernel-//' ; elif command -v dpkg &>/dev/null; then dpkg -l 'linux-image-*' 2>/dev/null | grep '^ii' | awk '{print $2}' | sed 's/linux-image-//'; fi)
for f in /boot/vmlinuz-* /boot/initramfs-* /boot/initrd.img-* /boot/System.map-* /boot/config-*; do
    [ -f "$f" ] || continue
    VER=$(echo "$f" | sed 's|/boot/[^-]*-||')
    if [ "$VER" != "$CURRENT" ] && ! echo "$INSTALLED" | grep -qF "$VER"; then
        rm -f "$f" 2>/dev/null && echo "Removed orphan: $f"
    fi
done
echo "Orphan cleanup done"
```

Expected output: "Orphan cleanup done"
On failure: continue

### Step 5: Remove rescue/kdump kernels if space still insufficient

```bash
BOOT_FREE=$(df /boot 2>/dev/null | tail -1 | awk '{print $4}')
if [ "${BOOT_FREE:-0}" -lt 102400 ]; then
    rm -f /boot/vmlinuz-0-rescue-* /boot/initramfs-0-rescue-* 2>/dev/null
    echo "Rescue kernels removed to free space"
else
    echo "SKIP: Sufficient space after kernel removal"
fi
```

Expected output: "SKIP" or "Rescue kernels removed"
On failure: continue

### Step 6: Set installonly_limit to prevent future accumulation (RPM-based)

```bash
if [ -f /etc/yum.conf ]; then
    if grep -q "^installonly_limit" /etc/yum.conf; then
        sed -i 's/^installonly_limit=.*/installonly_limit=2/' /etc/yum.conf
    else
        echo "installonly_limit=2" >> /etc/yum.conf
    fi
    echo "installonly_limit set to 2"
elif [ -f /etc/dnf/dnf.conf ]; then
    if grep -q "^installonly_limit" /etc/dnf/dnf.conf; then
        sed -i 's/^installonly_limit=.*/installonly_limit=2/' /etc/dnf/dnf.conf
    else
        echo "installonly_limit=2" >> /etc/dnf/dnf.conf
    fi
    echo "installonly_limit set to 2"
else
    echo "SKIP: Not RPM-based"
fi
```

Expected output: "installonly_limit set to 2" or "SKIP"
On failure: continue

### Step 7: Verify /boot has sufficient free space (need at least 100MB)

```bash
BOOT_FREE_KB=$(df /boot 2>/dev/null | tail -1 | awk '{print $4}')
if [ "${BOOT_FREE_KB:-0}" -ge 102400 ]; then
    echo "SUFFICIENT: $(( BOOT_FREE_KB / 1024 ))MB free on /boot"
else
    echo "INSUFFICIENT: $(( BOOT_FREE_KB / 1024 ))MB free on /boot"
    exit 1
fi
```

Expected output: "SUFFICIENT: XMB free on /boot"
On failure: abort

## Validation

```bash
BOOT_USE=$(df /boot 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')
CURRENT=$(uname -r)
KERNEL_OK=$(ls /boot/vmlinuz-${CURRENT} 2>/dev/null || ls /boot/vmlinuz-${CURRENT}.* 2>/dev/null)
if [ "${BOOT_USE:-100}" -le 70 ] && [ -n "$KERNEL_OK" ]; then
    echo "BOOT PARTITION OK: ${BOOT_USE}% used, running kernel present"
else
    echo "BOOT PARTITION NOT OK: ${BOOT_USE}% used"
    exit 1
fi
```

Expected: "BOOT PARTITION OK: X% used, running kernel present"

## Rollback

Kernel packages cannot easily be reinstalled if removed incorrectly. However, this SOP never removes the running kernel or the most recent previous kernel. If a rollback is needed:

```bash
# Re-install the latest available kernel
if command -v dnf &>/dev/null; then dnf install -y kernel; elif command -v yum &>/dev/null; then yum install -y kernel; elif command -v apt-get &>/dev/null; then apt-get install -y linux-image-aws; fi
```

## Escalation

If /boot cannot be freed sufficiently:
- Check if /boot is on a separate small partition that needs resizing (common on older AMIs with 200MB /boot)
- Consider migrating to a larger /boot partition via snapshot → resize workflow
- For UEFI instances, check /boot/efi space as well
- If only the running kernel remains and /boot is still full, investigate large initramfs (dracut modules, firmware blobs)
