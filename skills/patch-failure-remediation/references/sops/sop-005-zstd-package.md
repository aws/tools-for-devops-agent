# SOP-005: Resolve Zstd Package Issues Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-005 |
| Category | zstd_package |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2023, RHEL 9, Fedora |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "zstd: command not found" or "cannot decompress .zst payload"
- RPM packages fail to install with compression-related errors
- "libzstd.so: cannot open shared object file" during patching
- DNF transaction fails with zstd decompression errors
- "rpmlib(PayloadIsZstd) <= 5.4.18-1 is needed" dependency error
- "Payload decompression failed: Input/output error"

## Root Cause

Zstd (Zstandard) compression issues occur when:

- The zstd package or libzstd library is missing or corrupted after a failed previous update
- Upgrade from older distro (AL2 to AL2023, RHEL 8 to RHEL 9) introduced zstd-compressed RPMs without the decompressor being present
- Shared library symlinks are broken after partial update (e.g., libzstd.so.1 -> missing target)
- Conflicting zstd versions between system RPM and application-bundled installations (pip-installed zstd)
- Minimal/container-derived AMIs may not include zstd by default despite repos containing zstd-compressed packages

This is increasingly common because AL2023 and RHEL 9 default to zstd compression for RPM payloads, whereas older distros used xz or gzip.

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — if zstd removal was caused by a dependency conflict resolution gone wrong
- SOP-010 (Python Missing) — similar pattern of a core system utility being absent

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Base system libraries (glibc) are functional
- At least one working compression method (gzip/xz) to bootstrap installation

## Diagnosis

Determine what compression the failing package uses:

```bash
rpm -qip /var/cache/dnf/*/packages/*.rpm 2>/dev/null | grep -i payload | head -5
```

Check library search path:

```bash
ldconfig -p | grep zstd; ldd $(which rpm) 2>/dev/null | grep zstd
```

## Remediation Steps

### Step 1: Check current zstd status

```bash
rpm -q zstd libzstd 2>/dev/null; which zstd 2>/dev/null; echo "Check done"
```

Expected output: Package version info or "not installed"
On failure: continue

### Step 2: Check for broken libzstd symlinks

```bash
ldconfig -p | grep zstd; ls -la /usr/lib64/libzstd* 2>/dev/null || ls -la /usr/lib/x86_64-linux-gnu/libzstd* 2>/dev/null; echo "Symlink check done"
```

Expected output: Library paths listed
On failure: continue

### Step 3: Force reinstall zstd and libzstd

```bash
dnf reinstall -y zstd libzstd 2>/dev/null || dnf install -y zstd libzstd 2>/dev/null || yum reinstall -y zstd libzstd 2>/dev/null || yum install -y zstd libzstd 2>/dev/null; echo "Reinstall done"
```

Expected output: "Reinstall done"
On failure: go to Step 4

### Step 4: Manual RPM install from cache or download

```bash
ARCH=$(uname -m); dnf download --destdir /tmp zstd libzstd 2>/dev/null && rpm -ivh --force /tmp/zstd*.rpm /tmp/libzstd*.rpm 2>/dev/null; ldconfig; echo "Manual install done"
```

Expected output: "Manual install done"
On failure: abort

### Step 5: Refresh library cache

```bash
ldconfig; echo "Library cache refreshed"
```

Expected output: "Library cache refreshed"
On failure: continue

## Validation

```bash
zstd --version && rpm -q zstd libzstd && echo "ZSTD OK"
```

Expected: Version output followed by "ZSTD OK"

## Rollback

```bash
echo "No rollback required - reinstallation is safe and non-destructive"
```

## Escalation

If zstd cannot be installed because the RPM for zstd itself is zstd-compressed (bootstrap problem):
- Download the xz-compressed version from a known-good mirror
- Use `rpm2cpio` with an older decompressor to extract manually
- Consider restoring from AMI if the bootstrap loop cannot be broken
