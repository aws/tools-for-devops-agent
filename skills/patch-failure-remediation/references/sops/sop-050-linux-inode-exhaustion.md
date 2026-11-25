# SOP-050: Resolve Inode Exhaustion Blocking Package Installation

| Field | Value |
|-------|-------|
| ID | SOP-050 |
| Category | inode_exhaustion |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "No space left on device" despite df showing available disk space
- "Cannot create file: No space left on device" during package extraction
- Package installation fails creating temp files or extracting RPM/DEB contents
- "dpkg: error: unable to create new file" with disk space available
- "error: unpacking of archive failed: cpio: open" in RPM output
- df -i shows filesystem at 100% inode usage
- Small files (session files, cache entries, mail queue) consumed all inodes

## Root Cause

Inode exhaustion occurs when:

- Millions of small files (PHP sessions, mail queue, tmp files, log fragments) consume all inodes
- /var/spool/postfix or /var/spool/mail filled with undelivered messages
- Application creates one-file-per-session without cleanup
- Container layers and overlay filesystem metadata exhaust inodes
- /tmp filled with many small pid/lock/session files
- Package manager cache has many small metadata files
- Linux kernel creates entries in /proc or /sys that count against inode limits on small filesystems

## Related Failure Patterns

- SOP-002 (Disk Full) — similar symptoms but different root cause
- SOP-036 (Read-Only Filesystem) — inode exhaustion can trigger errors that look like RO fs

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Check inode usage across filesystems:

```bash
df -iP / /var /tmp 2>/dev/null; echo "---"; for dir in /tmp /var/spool /var/cache /var/lib/php; do echo "$dir: $(find "$dir" -type f 2>/dev/null | wc -l) files"; done
```

## Remediation Steps

### Step 1: Identify inode usage

```bash
df -iP / /var /tmp 2>/dev/null | awk 'NR>1 {if ($5+0 > 90) print "HIGH INODE USAGE: "$5" on "$6}'; echo "---"; df -iP | awk 'NR>1 && $5+0 >= 95 {print "CRITICAL: "$6" at "$5}'
```

Expected output: Inode usage per filesystem
On failure: continue

### Step 2: Find directories with most files

```bash
for dir in /tmp /var/spool /var/cache /var/lib/php /var/log /var/tmp /var/mail /var/lib/docker /var/lib/containerd; do [ -d "$dir" ] && echo "$(timeout 10 find "$dir" -xdev -type f 2>/dev/null | wc -l) $dir"; done | sort -rn | head -10
```

Expected output: Top directories by file count
On failure: continue

### Step 3: Clean known small-file accumulators

> Note: The `/var/spool/postfix/maildrop` cleanup removes queued outbound mail older than 1 day — this is real application data, not just cache. Only proceed if losing undelivered queued mail is acceptable; the guard below skips it unless inode pressure is actually on the filesystem holding the queue.

```bash
find /tmp -type f -mtime +3 -delete 2>/dev/null; MAILDROP_IUSE=$(df -iP /var/spool/postfix/maildrop 2>/dev/null | awk 'NR==2{print $5+0}'); if [ "${MAILDROP_IUSE:-0}" -ge 90 ]; then echo "WARNING: removing queued mail older than 1 day from /var/spool/postfix/maildrop (application data)"; find /var/spool/postfix/maildrop -type f -mtime +1 -delete 2>/dev/null; else echo "Skipping maildrop cleanup (inode pressure below threshold)"; fi; find /var/spool/mail -type f -size 0 -delete 2>/dev/null; find /var/lib/php/sessions -type f -mtime +1 -delete 2>/dev/null; find /var/cache/man -type f -mtime +30 -delete 2>/dev/null; echo "Common small files cleaned"
```

Expected output: "Common small files cleaned"
On failure: continue

### Step 4: Clean package manager cache files

```bash
if command -v dnf &>/dev/null; then dnf clean all 2>&1; rm -rf /var/cache/dnf/*/packages/* 2>/dev/null; elif command -v apt-get &>/dev/null; then apt-get clean 2>&1; rm -rf /var/cache/apt/archives/partial/* 2>/dev/null; elif command -v zypper &>/dev/null; then zypper clean -a 2>&1; fi; echo "Package cache cleaned"
```

Expected output: "Package cache cleaned"
On failure: continue

### Step 5: Remove old log files

```bash
find /var/log -name "*.gz" -mtime +30 -delete 2>/dev/null; find /var/log -name "*.[0-9]" -mtime +14 -delete 2>/dev/null; find /var/log -name "*.old" -delete 2>/dev/null; echo "Old logs cleaned"
```

Expected output: "Old logs cleaned"
On failure: continue

### Step 6: Verify inode availability

```bash
IUSE=$(df -iP / | awk 'NR==2{print $5}' | sed 's/%//'); if [ "${IUSE:-100}" -lt 90 ]; then echo "INODES OK: ${IUSE}% used"; else echo "INODES STILL HIGH: ${IUSE}% used"; exit 1; fi
```

Expected output: "INODES OK"
On failure: abort

## Validation

```bash
df -iP / /var /tmp 2>/dev/null | awk 'NR>1 {pct=$5+0; if (pct>90) {fail=1; print "HIGH: "$6" at "$5}} END {if (!fail) print "INODE USAGE OK"}'
```

Expected: "INODE USAGE OK"

## Rollback

```bash
echo "Most cleanup targets temp/cache/old files, but note: Step 3 may have removed old queued outbound mail (>1 day) from /var/spool/postfix/maildrop - this is application data and cannot be recovered by rollback"
```

## Escalation

If inodes cannot be freed:
- Identify the application creating excessive small files and fix its cleanup/rotation
- For persistent issues: resize filesystem or create separate volume for high-inode directories
- Consider XFS which handles large numbers of files better than ext4 with default inode ratio
- For Docker: `docker system prune -f` to clean unused layers and containers
- If /var/spool/postfix is the culprit: `postsuper -d ALL` to purge mail queue
