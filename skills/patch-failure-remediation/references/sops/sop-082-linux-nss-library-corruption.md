# SOP-082: Resolve Linux NSS Library Corruption (libfreeblpriv3.so Segfault)

| Field | Value |
|-------|-------|
| ID | SOP-082 |
| Category | nss_library_corruption |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 7, RHEL 8, Oracle Linux 7, Oracle Linux 8, CentOS 7, Amazon Linux 2 |
| Requires Reboot | No |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-23 |

## Symptoms

- All yum/dnf commands fail with: `Segmentation fault` and exit status 139
- Patch prerequisite check shows: `YumDryRunResult: Failed`
- SSM RunCommand `AWS-RunShellScript` with yum commands returns segfault
- `/var/log/messages` shows segfault entries referencing `libfreeblpriv3.so`: `error 4 in libfreeblpriv3.so`
- `curl` commands also segfault with the same library reference
- Any process using NSS/SSL (yum, curl, wget, python requests) crashes

## Root Cause

The `libfreeblpriv3.so` library (part of the `nss-softokn-freebl` package) is corrupted on disk. This library is part of Mozilla's Network Security Services (NSS) and is required by any application performing cryptographic operations (TLS connections, package signature verification). When corrupted:

- Any process that loads the NSS library (yum, curl, python, etc.) triggers a segmentation fault when accessing the corrupted memory-mapped file
- The corruption typically occurs due to:
  - Interrupted package update (power loss, OOM kill, or forced termination during nss-softokn upgrade)
  - Disk I/O errors corrupting the shared library on disk
  - Incomplete yum transaction that partially wrote the library file
  - EBS volume snapshot restore where the file was mid-write

Since yum/dnf itself depends on NSS for repository HTTPS connections, **the package manager cannot self-repair** — the RPM must be reinstalled using `rpm` directly with a locally available package file.

## Related Failure Patterns

- SOP-004 (Corrupt RPM DB) — RPM database corruption may coexist
- SOP-032 (Incomplete Transaction) — the NSS corruption may have resulted from an interrupted transaction
- SOP-036 (Read-only Filesystem) — check filesystem is writable before attempting repair

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root or sudo access via SSM Run Command
- Access to RPM package files (either from local cache, S3, or Red Hat CDN)

## Diagnosis

Confirm the segfault is from the NSS library:

```bash
echo "=== Recent segfaults ==="; dmesg | grep -i "segfault.*libfreebl" | tail -5; echo "=== RPM verify ==="; rpm -V nss-softokn nss-softokn-freebl 2>&1 | head -10; echo "=== Library check ==="; ls -la /lib64/libfreeblpriv3.* 2>/dev/null || ls -la /usr/lib64/libfreeblpriv3.* 2>/dev/null
```

## Remediation Steps

### Step 1: Confirm segfault source and identify installed NSS package versions

```bash
echo "=== Segfault evidence ==="; dmesg | grep -i "segfault" | grep -i "libfreebl\|nss" | tail -3; echo "=== Installed versions ==="; rpm -qa | grep nss-softokn; echo "=== Library location ==="; rpm -ql nss-softokn-freebl | grep libfreeblpriv3
```

Expected output: Package versions and library path
On failure: continue

### Step 2: Check if RPM packages are available in local cache

```bash
CACHE_DIR="/var/cache/yum"; [ -d /var/cache/dnf ] && CACHE_DIR="/var/cache/dnf"; NSS_VER=$(rpm -q nss-softokn --qf '%{VERSION}-%{RELEASE}.%{ARCH}'); FREEBL_VER=$(rpm -q nss-softokn-freebl --qf '%{VERSION}-%{RELEASE}.%{ARCH}'); echo "Looking for nss-softokn-$NSS_VER and nss-softokn-freebl-$FREEBL_VER"; find $CACHE_DIR /tmp /root -name "nss-softokn-freebl-*.rpm" -o -name "nss-softokn-[0-9]*.rpm" 2>/dev/null | head -5; echo "Cache search done"
```

Expected output: RPM file paths if cached, or empty if not available
On failure: continue

### Step 3: Download NSS packages from AWS-accessible mirror (if not in cache)

```bash
NSS_VER=$(rpm -q nss-softokn --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}'); FREEBL_VER=$(rpm -q nss-softokn-freebl --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}'); echo "Need: $NSS_VER.rpm and $FREEBL_VER.rpm"; if command -v yumdownloader &>/dev/null; then cd /tmp && yumdownloader --destdir=/tmp nss-softokn nss-softokn-freebl 2>&1 && echo "Downloaded via yumdownloader" || echo "yumdownloader failed (expected if yum segfaults)"; else echo "yumdownloader not available"; fi
```

Expected output: Download status (may fail due to segfault — that's expected)
On failure: continue — will need manual RPM placement

### Step 4: Reinstall NSS packages using rpm (bypasses yum/dnf)

```bash
cd /tmp; NSS_RPM=$(find /tmp /var/cache -name "nss-softokn-[0-9]*.rpm" 2>/dev/null | head -1); FREEBL_RPM=$(find /tmp /var/cache -name "nss-softokn-freebl-*.rpm" 2>/dev/null | head -1); if [ -n "$NSS_RPM" ] && [ -n "$FREEBL_RPM" ]; then echo "Installing: $FREEBL_RPM $NSS_RPM"; rpm -ivh --force "$FREEBL_RPM" "$NSS_RPM" 2>&1; echo "RPM reinstall exit: $?"; else echo "RPM FILES NOT FOUND - manual placement required"; echo "Place nss-softokn and nss-softokn-freebl RPMs in /tmp then re-run"; exit 1; fi
```

Expected output: "Preparing... ######" with successful installation messages
On failure: abort — RPM files must be manually placed on the instance

### Step 5: Verify yum/dnf operations restored

```bash
yum clean all 2>&1; echo "---"; yum repolist 2>&1 | tail -5; echo "---"; yum check-update 2>&1 | head -5; echo "Exit: $?"
```

Expected output: Repository list without segfaults, exit code 0 or 100 (updates available)
On failure: abort

## Validation

```bash
yum check-update >/dev/null 2>&1; RC=$?; if [ $RC -eq 0 ] || [ $RC -eq 100 ]; then echo "NSS REMEDIATION OK"; else echo "NSS REMEDIATION FAILED (exit: $RC)"; fi
```

Expected: "NSS REMEDIATION OK"

## Rollback

No rollback needed — `rpm -ivh --force` reinstalls the same version that was previously installed. The operation replaces a corrupted file with a good copy.

## Prevention

- Monitor for segfault signals in `/var/log/messages` — early detection before patch windows
- Ensure UPS/stable power for instances during package updates
- Do not force-kill yum/dnf processes during NSS package updates
- Keep EBS volumes healthy — monitor for I/O errors via CloudWatch

## Escalation

If RPM files cannot be obtained:
- Download from Red Hat CDN using another instance with working yum: `yumdownloader nss-softokn nss-softokn-freebl`
- Copy RPMs to the affected instance via S3: upload to a bucket, then use `aws s3 cp` (aws cli may work if it doesn't use NSS)
- For RHEL instances: use `https://access.redhat.com/downloads/content/nss-softokn/<version>/<arch>/fd431d51/package`
- As a last resort: mount the root volume on a healthy instance, copy the RPM files to /tmp, then reattach
- If rpm command itself segfaults: the `ld-linux` or glibc may also be corrupt — requires volume mount repair from another instance
