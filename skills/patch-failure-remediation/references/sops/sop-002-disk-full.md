# SOP-002: Resolve Disk Full Condition Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-002 |
| Category | disk_full |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, Ubuntu 20.04, Ubuntu 22.04, RHEL 8, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-04-15 |

## Symptoms

- Patch fails with "No space left on device" or "Insufficient disk space"
- /var or /tmp filesystem at 95%+ utilization
- Package download or extraction fails mid-operation
- "write error in swap file" or "Cannot write to temporary file"
- DNF/YUM metadata download fails due to cache directory full
- dpkg reports "unable to write" errors during package extraction

## Root Cause

Disk space exhaustion typically caused by:

- Accumulated old kernel packages (each kernel consumes 200-400MB in /boot and /usr/lib/modules)
- Large log files not rotated properly (application logs, journal, audit logs)
- Leftover package cache from failed operations (/var/cache/yum or /var/cache/apt can grow to multiple GB)
- /tmp filled by application data, core dumps, or SSM agent working files
- Docker/container images and layers consuming /var/lib/docker space
- Snapshots or EBS volumes not appropriately sized for the workload
- Journal logs consuming excessive space in /var/log/journal

## Related Failure Patterns

This SOP may need to be combined with:
- SOP-008 (GRUB2 Update) — /boot specifically full prevents kernel patching
- SOP-004 (Corrupt RPM DB) — disk full during RPM write can corrupt the database

## Prerequisites

- Instance is reachable via SSM
- Root filesystem is not 100% full (agent needs some space to operate — at least 50MB free)
- No critical processes writing to the filled filesystem

## Diagnosis

Identify which mount points are full and what is consuming space:

```bash
df -h / /var /tmp /boot 2>/dev/null; echo "---"; du -sh /var/cache /var/log /tmp /var/lib/docker 2>/dev/null | sort -rh | head -10
```

Check for large individual files:

```bash
find /var /tmp -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -rh | head -10
```

## Remediation Steps

### Step 1: Check current disk usage

```bash
df -h / /var /tmp 2>/dev/null | grep -v "^Filesystem"
```

Expected output: Filesystem usage percentages
On failure: abort

### Step 2: Clean package manager cache

```bash
yum clean all 2>/dev/null; apt-get clean 2>/dev/null; dnf clean all 2>/dev/null; du -sh /var/cache/yum /var/cache/apt /var/cache/dnf 2>/dev/null; echo "Cache cleaned"
```

Expected output: "Cache cleaned"
On failure: continue

### Step 3: Remove old kernels (keep current + 1 previous)

```bash
if command -v package-cleanup &>/dev/null; then package-cleanup --oldkernels --count=2 -y; elif command -v dnf &>/dev/null; then dnf remove --oldinstallonly --setopt installonly_limit=2 -y; elif command -v apt &>/dev/null; then apt-get autoremove -y; fi; echo "Old kernels cleaned"
```

Expected output: "Old kernels cleaned"
On failure: continue

### Step 4: Clean temporary files older than 7 days

```bash
find /tmp -type f -mtime +7 -not -name ".*" -delete 2>/dev/null; find /var/tmp -type f -mtime +7 -delete 2>/dev/null; echo "Temp files cleaned"
```

Expected output: "Temp files cleaned"
On failure: continue

### Step 5: Rotate and compress large logs

```bash
find /var/log -name "*.log" -size +100M -exec sh -c 'if command -v lsof >/dev/null 2>&1; then lsof "$1" >/dev/null 2>&1 || truncate -s 0 "$1"; fi' _ {} \; 2>/dev/null; logrotate -f /etc/logrotate.conf 2>/dev/null; echo "Logs rotated"
```

Expected output: "Logs rotated"
On failure: continue

### Step 6: Vacuum systemd journal logs

```bash
journalctl --vacuum-size=500M 2>/dev/null; journalctl --vacuum-time=7d 2>/dev/null; echo "Journal vacuumed"
```

Expected output: "Journal vacuumed"
On failure: continue

### Step 7: Verify sufficient space on all relevant mount points (need at least 1GB free each)

```bash
FAIL=0; for mp in / /var /tmp; do FREE_KB=$(df "$mp" 2>/dev/null | tail -1 | awk '{print $4}'); if [ "${FREE_KB:-0}" -lt 1048576 ]; then echo "INSUFFICIENT:${FREE_KB}KB on $mp"; FAIL=1; fi; done; [ "$FAIL" -eq 0 ] && echo "SUFFICIENT: all mount points >1GB free" || exit 1
```

Expected output: "SUFFICIENT: all mount points >1GB free"
On failure: abort

## Validation

```bash
FAIL=0; for mp in / /var /tmp; do USE=$(df "$mp" 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//'); if [ "${USE:-100}" -gt 85 ]; then echo "HIGH:${USE}% on $mp"; FAIL=1; fi; done; [ "$FAIL" -eq 0 ] && echo "OK: all mount points below 85%" || exit 1
```

Expected: OK: all mount points below 85%

## Rollback

No rollback needed — space cleanup is non-destructive to application data. Only package cache, old kernels, temp files, and rotated logs are affected.

## Escalation

If disk cannot be freed below 85%, consider:
- Expanding the EBS volume (`aws ec2 modify-volume --size`)
- Identifying application-specific data growth (databases, uploads)
- Moving /var/log or /tmp to a separate volume
