# Read-only filesystem / EBS I/O errors

**Signatures:** "Read-only file system" on package install, "error: open of /var/lib/rpm/... failed:
Read-only file system", `touch` fails RO, kernel "EXT4-fs error: remounting filesystem read-only"
or "XFS: Metadata I/O error". A read-only remount is usually the kernel **protecting** the FS after
detecting I/O errors or corruption.

## Diagnose — check for I/O errors BEFORE any remount
```bash
mount | grep ' ro,' | grep -vE 'proc|sys|cgroup|tmpfs|squashfs'
dmesg -T 2>/dev/null | grep -iE 'i/o error|medium error|hardware error|nvme.*timeout|remount|xfs.*error|ext4.*error' | tail -20
cat /sys/block/*/device/state 2>/dev/null
```

## If NO I/O errors: safe to remount rw
```bash
for mp in / /var /tmp; do mount | grep " $mp " | grep -q ' ro,' && mount -o remount,rw "$mp" && echo "remounted rw $mp"; done
for d in /var/lib/rpm /var/lib/dpkg /var/cache /tmp; do touch "$d/.w" 2>/dev/null && rm -f "$d/.w" && echo "writable $d" || echo "NOT writable $d"; done
```

## If I/O errors present: do NOT remount — treat as a volume problem
- A mounted FS can't be fsck'd; repair requires unmount/rescue.
- `aws ec2 describe-volume-status --volume-ids <vol-id>` — if "impaired": snapshot → new volume from snapshot → detach old → attach new.
- Or stop instance → detach root → attach to rescue instance → `xfs_repair <dev>` (or `e2fsck -fy <dev>`) on the UNmounted device → reattach.
- Root volume irrecoverable → rebuild from AMI.

## Verify
```bash
for mp in / /var /tmp; do mount | grep " $mp " | grep -q ' ro,' && echo "STILL RO $mp"; done; echo "check done"
```
