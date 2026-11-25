# SOP-026: Resolve Kernel Headers Mismatch Blocking DKMS Module Rebuild

| Field | Value |
|-------|-------|
| ID | SOP-026 |
| Category | kernel_headers_mismatch |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Oracle Linux 8, Oracle Linux 9, SLES 15 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "DKMS module build failed" during kernel upgrade
- "Unable to find kernel headers for the running kernel"
- "ERROR: Cannot open /lib/modules/<version>/build" during DKMS rebuild
- Third-party kernel modules (NVIDIA, ENA, EFA, CrowdStrike) fail to compile against new kernel
- Kernel patch completes but instance reports degraded functionality post-reboot due to missing modules

## Root Cause

Kernel headers mismatch occurs when:

- kernel-devel or linux-headers package is not installed for the running kernel version
- Multiple kernel versions installed but headers only exist for one version
- Third-party repos provide kernel but not matching headers
- DKMS autoinstall triggers during patching but cannot find build dependencies
- Oracle Linux UEK kernel has separate header packages from RHCK kernel
- SLES kernel-default-devel not installed alongside kernel-default updates

## Related Failure Patterns

- SOP-008 (GRUB2 Update) — kernel patching issues often co-occur
- SOP-002 (Disk Full) — /usr/src/kernels consuming space

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Package manager functional (no corrupt DB or lock issues)

## Diagnosis

Check current kernel vs available headers:

```bash
echo "Running: $(uname -r)"; rpm -qa kernel-devel kernel-headers 2>/dev/null; dpkg -l linux-headers-$(uname -r) 2>/dev/null; dkms status 2>/dev/null
```

## Remediation Steps

### Step 1: Identify running kernel and installed headers

```bash
KERN=$(uname -r); echo "Running kernel: $KERN"; if command -v rpm &>/dev/null; then rpm -qa | grep -E "kernel-devel|kernel-headers" | sort; elif command -v dpkg &>/dev/null; then dpkg -l | grep linux-headers | awk '{print $2}'; fi; echo "Headers check done"
```

Expected output: List of installed header packages
On failure: continue

### Step 2: Install matching kernel headers

```bash
KERN=$(uname -r); if command -v dnf &>/dev/null; then dnf install -y "kernel-devel-$KERN" kernel-headers 2>&1; elif command -v yum &>/dev/null; then yum install -y "kernel-devel-$KERN" kernel-headers 2>&1; elif command -v apt-get &>/dev/null; then apt-get install -y "linux-headers-$KERN" 2>&1 || apt-get install -y linux-headers-generic 2>&1; elif command -v zypper &>/dev/null; then zypper install -y kernel-default-devel 2>&1; fi; echo "Headers install exit: $?"
```

Expected output: "Headers install exit: 0"
On failure: abort

### Step 3: Rebuild DKMS modules

```bash
if command -v dkms &>/dev/null; then dkms autoinstall -k $(uname -r) 2>&1; echo "DKMS rebuild exit: $?"; else echo "DKMS not installed - skipping"; fi
```

Expected output: "DKMS rebuild exit: 0" or "DKMS not installed - skipping"
On failure: continue

### Step 4: Verify modules are available

```bash
KERN=$(uname -r); ls /lib/modules/$KERN/build/Makefile && echo "Headers symlink OK" || echo "Headers symlink MISSING"
```

Expected output: "Headers symlink OK"
On failure: abort

## Validation

```bash
KERN=$(uname -r); test -d /lib/modules/$KERN/build && echo "KERNEL HEADERS OK" || echo "KERNEL HEADERS MISSING"
```

Expected: "KERNEL HEADERS OK"

## Rollback

```bash
echo "No rollback needed - installing headers is additive and non-destructive"
```

## Escalation

If kernel headers cannot be installed:
- Check if the kernel is from a third-party repo (Oracle UEK, elrepo) and ensure the matching -devel repo is enabled
- For Oracle Linux UEK: `yum install -y kernel-uek-devel-$(uname -r)`
- If headers are unavailable for the running kernel version, the kernel may be too old — consider updating the kernel first
