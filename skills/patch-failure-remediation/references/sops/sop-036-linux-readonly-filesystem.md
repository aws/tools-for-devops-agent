# SOP-036: Resolve Filesystem Read-Only Condition Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-036 |
| Category | readonly_filesystem |
| Severity | Critical |
| Risk Level | High |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | Yes |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Read-only file system" errors during package install
- "E: Unable to write to /var/cache/apt/" or "E: Unable to lock the administration directory"
- "error: open of /var/lib/rpm/__db.000 failed: Read-only file system"
- `touch /tmp/test` returns "Read-only file system"
- "cannot create temp file for here-document: Read-only file system"
- Kernel messages: "EXT4-fs error: remounting filesystem read-only"
- "XFS: Metadata I/O error" followed by read-only remount

## Root Cause

Filesystem remounted read-only when:

- EBS volume experiencing I/O errors (impaired volume, hardware issue)
- Filesystem corruption detected by ext4/XFS journaling — kernel remounts RO to prevent further damage
- Disk quota exceeded causing write failures interpreted as FS errors
- Instance store volume failure (ephemeral storage)
- NVMe timeout causing device to become unavailable
- dm-crypt/LUKS encrypted volume key expired or crypto failure
- Filesystem full condition combined with journal exhaustion triggers RO remount
- Kernel bug causing false positive corruption detection

## Related Failure Patterns

- SOP-002 (Disk Full) — disk full can trigger read-only remount
- SOP-004 (Corrupt RPM DB) — RO filesystem prevents RPM writes, and the forced RO may corrupt in-flight writes

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of the volume architecture (EBS vs instance store)

## Diagnosis

Check filesystem mount states and kernel messages:

```bash
mount | grep -E "rw|ro" | grep -v "proc\|sys\|cgroup"; echo "---"; dmesg -T 2>/dev/null | grep -iE "read.only|i/o error|remount|ext4.*error|xfs.*error" | tail -20; echo "---"; cat /proc/mounts | grep -E "/ |/var |/tmp " | awk '{print $2, $4}'
```

## Remediation Steps

### Step 1: Identify which filesystems are read-only

```bash
RO_FS=$(mount | grep -E '[(,]ro[,)]' | grep -v "proc\|sys\|cgroup\|devpts\|tmpfs\|squashfs"); if [ -n "$RO_FS" ]; then echo "READ-ONLY FILESYSTEMS:"; echo "$RO_FS"; else echo "All filesystems are read-write"; fi
```

Expected output: List of RO filesystems or "All filesystems are read-write"
On failure: continue

### Step 2: Check for I/O errors indicating hardware/volume issues

```bash
dmesg -T 2>/dev/null | grep -iE "i/o error|medium error|hardware error|nvme.*timeout" | tail -10; echo "---"; cat /sys/block/*/device/state 2>/dev/null; echo "IO check done"
```

Expected output: I/O error information
On failure: continue

### Step 3: Attempt remount as read-write (only if no I/O errors)

```bash
IO_ERRORS=$(dmesg -T 2>/dev/null | grep -ciE "i/o error|medium error|hardware error|nvme.*timeout"); FS_CORRUPT=$(dmesg -T 2>/dev/null | grep -ciE "ext4.*error|xfs.*corrupt|xfs.*error|metadata corruption|corrupt.*metadata|needs journal recovery"); if [ "$IO_ERRORS" -gt 0 ]; then echo "SKIP REMOUNT: $IO_ERRORS I/O error(s) detected — escalate to fsck/reboot"; elif [ "$FS_CORRUPT" -gt 0 ]; then echo "SKIP REMOUNT: $FS_CORRUPT filesystem/metadata corruption message(s) detected — the kernel set RO to protect the FS; do NOT remount rw. Run fsck (unmounted) or escalate per the Escalation section."; else REMOUNTED=0; for mp in / /var /tmp; do OPTS=$(findmnt -rno OPTIONS "$mp" 2>/dev/null || awk -v m="$mp" '$2==m{print $4}' /proc/mounts 2>/dev/null); if echo "$OPTS" | grep -q '^ro,\|^ro$'; then mount -o remount,rw $mp 2>&1 && echo "Remounted RW: $mp" && REMOUNTED=$((REMOUNTED+1)) || echo "FAILED to remount: $mp"; fi; done; [ $REMOUNTED -gt 0 ] && echo "Remounted $REMOUNTED filesystems" || echo "No remounts needed"; fi
```

Expected output: "Remounted N filesystems", "No remounts needed", or "SKIP REMOUNT" if I/O errors present
On failure: continue

### Step 4: Run filesystem check if remount failed

```bash
RO_DEVS=$(mount | grep -E '[(,]ro[,)]' | grep -v "proc\|sys\|cgroup\|tmpfs" | awk '{print $1}'); if [ -n "$RO_DEVS" ]; then for dev in $RO_DEVS; do echo "Cannot fsck mounted filesystem $dev - requires reboot into rescue mode"; done; echo "REBOOT REQUIRED for filesystem repair"; else echo "All filesystems writable"; fi
```

Expected output: Status of filesystem repair needs
On failure: continue

### Step 5: Verify write capability on critical paths

```bash
FAIL=0; for dir in /var/lib/rpm /var/lib/dpkg /var/cache /tmp; do if [ -d "$dir" ]; then touch "$dir/.write_test" 2>/dev/null && rm -f "$dir/.write_test" && echo "Writable: $dir" || { echo "NOT WRITABLE: $dir"; FAIL=1; }; fi; done; [ $FAIL -eq 0 ] && echo "ALL PATHS WRITABLE" || exit 1
```

Expected output: "ALL PATHS WRITABLE"
On failure: abort

## Validation

```bash
FAIL=0; for mp in / /var /tmp; do FLAGS=$(findmnt -rno OPTIONS "$mp" 2>/dev/null | head -1 | cut -d, -f1); [ -z "$FLAGS" ] && FLAGS=$(awk -v m="$mp" '$2==m{print $4}' /proc/mounts 2>/dev/null | head -1 | cut -d, -f1); if [ "$FLAGS" = "ro" ]; then echo "STILL RO: $mp"; FAIL=1; fi; done; [ $FAIL -eq 0 ] && echo "FILESYSTEMS OK - ALL RW" || echo "FILESYSTEMS STILL READ-ONLY"
```

Expected: "FILESYSTEMS OK - ALL RW"

## Rollback

```bash
echo "No rollback applicable - read-only is a protective state that must be resolved"
```

## Escalation

If filesystem cannot be remounted read-write:
- Check EBS volume status in AWS Console: `aws ec2 describe-volume-status --volume-ids <vol-id>`
- If volume shows "impaired": create snapshot, create new volume from snapshot, detach old, attach new
- If filesystem corruption: stop instance, detach volume, attach to recovery instance, run `fsck -y`
- For XFS: `xfs_repair -n <device>` (read-only check first), then `xfs_repair <device>` on unmounted volume
- For ext4: `e2fsck -fy <device>` on unmounted volume
- Consider replacing the instance from AMI if the root volume is irrecoverable
