# SOP-037: Resolve Oracle Linux UEK/RHCK Kernel Conflict During Patching

| Field | Value |
|-------|-------|
| ID | SOP-037 |
| Category | oracle_linux_kernel_conflict |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Oracle Linux 8, Oracle Linux 9 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Error: Package kernel-uek conflicts with kernel" during patching
- Both UEK and RHCK kernel updates attempted causing transaction failure
- "Protected multilib versions" errors involving kernel packages
- ksplice-related errors blocking kernel updates
- "Problem: cannot install both kernel-uek-X and kernel-X"
- Oracle Linux yum server metadata references packages not available in configured repos
- "No package kernel-uek-devel available" when DKMS modules need rebuild

## Root Cause

Oracle Linux kernel conflicts occur when:

- Both UEK (Unbreakable Enterprise Kernel) and RHCK (Red Hat Compatible Kernel) repos are enabled simultaneously
- Patch baseline selects both kernel streams for update creating an unresolvable transaction
- ksplice-aware patching tries to apply userspace patches while kernel-level patches are also queued
- UEK repo version mismatches the installed UEK kernel branch (UEK6 vs UEK7)
- oraclelinux-release package update changes default kernel channel
- kernel-uek-devel package missing from UEK repo causing DKMS failures post-patch

## Related Failure Patterns

- SOP-026 (Kernel Headers Mismatch) — UEK needs specific kernel-uek-devel
- SOP-001 (Dependency Conflicts) — kernel multi-stream is a dependency resolution problem
- SOP-008 (GRUB2 Update) — kernel conflicts affect boot configuration

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is running Oracle Linux 8 or 9
- Knowledge of whether instance should use UEK or RHCK

## Diagnosis

Determine running kernel type and available repos:

```bash
uname -r | grep -q "uek" && echo "Running: UEK" || echo "Running: RHCK"; echo "Kernel: $(uname -r)"; echo "---"; yum repolist 2>/dev/null | grep -iE "uek|rhck|ksplice|oracle"; echo "---"; rpm -qa | grep -i "kernel" | sort
```

## Remediation Steps

### Step 1: Identify running kernel channel

```bash
KERN=$(uname -r); if echo "$KERN" | grep -q "uek"; then CHANNEL="UEK"; UEK_VER=$(echo "$KERN" | grep -oP 'uek\K[0-9]+' || echo "unknown"); echo "Running UEK version: $UEK_VER (kernel: $KERN)"; else CHANNEL="RHCK"; echo "Running RHCK (kernel: $KERN)"; fi; echo "Channel: $CHANNEL"
```

Expected output: Kernel channel identification
On failure: continue

### Step 2: Disable conflicting kernel repo

```bash
KERN=$(uname -r); if echo "$KERN" | grep -q "uek"; then dnf config-manager --set-disabled ol*_RHCK 2>/dev/null || yum-config-manager --disable ol*_RHCK 2>/dev/null; echo "Disabled RHCK repos (keeping UEK)"; else dnf config-manager --set-disabled ol*_UEK* 2>/dev/null || yum-config-manager --disable ol*_UEK* 2>/dev/null; echo "Disabled UEK repos (keeping RHCK)"; fi
```

Expected output: "Disabled RHCK repos" or "Disabled UEK repos"
On failure: continue

### Step 3: Disable ksplice if causing conflicts

```bash
if rpm -q ksplice-tools &>/dev/null; then systemctl stop uptrack 2>/dev/null; dnf config-manager --set-disabled ol*_ksplice 2>/dev/null || yum-config-manager --disable ol*_ksplice 2>/dev/null; echo "Ksplice disabled for patching"; else echo "Ksplice not installed"; fi
```

Expected output: "Ksplice disabled for patching" or "Ksplice not installed"
On failure: continue

### Step 4: Clean metadata and verify resolution

```bash
dnf clean all 2>/dev/null || yum clean all 2>/dev/null; dnf makecache 2>/dev/null || yum makecache 2>/dev/null; echo "Cache rebuilt"
```

Expected output: "Cache rebuilt"
On failure: continue

### Step 5: Verify kernel update is possible

```bash
if command -v dnf &>/dev/null; then dnf check-update kernel* 2>&1 | tail -10; echo "Kernel update check exit: $?"; elif command -v yum &>/dev/null; then yum check-update kernel* 2>&1 | tail -10; echo "Kernel update check exit: $?"; fi
```

Expected output: Available kernel updates without conflicts
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 && echo "ORACLE LINUX KERNEL CONFIG OK"; elif command -v yum &>/dev/null; then yum check 2>&1 && echo "ORACLE LINUX KERNEL CONFIG OK"; fi
```

Expected: "ORACLE LINUX KERNEL CONFIG OK"

## Rollback

```bash
dnf config-manager --set-enabled ol*_UEK* ol*_RHCK 2>/dev/null || yum-config-manager --enable ol*_UEK* ol*_RHCK 2>/dev/null
if rpm -q ksplice-tools &>/dev/null; then dnf config-manager --set-enabled ol*_ksplice 2>/dev/null; systemctl start uptrack 2>/dev/null; fi
echo "All Oracle Linux repos re-enabled"
```

## Escalation

If kernel conflicts persist:
- Determine definitively which kernel stream (UEK vs RHCK) is required for the workload
- For UEK: ensure the correct UEK version repo is enabled (ol8_UEK6 vs ol8_UEK7)
- Consider removing the unused kernel stream entirely: `dnf remove kernel-uek` or `dnf remove kernel`
- Check /etc/yum.repos.d/oracle-linux-ol*.repo for duplicate or conflicting repo definitions
- For ksplice issues: `uptrack-remove --all` to clear applied patches before standard kernel update
