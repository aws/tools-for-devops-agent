# Inode exhaustion, disk pressure, and OOM during patching

## Inode exhaustion ("No space left on device" but df -h shows free space)
The tell is `df -i` at ~100% — millions of small files consumed inodes.
```bash
df -i / /var /tmp
for d in /tmp /var/spool /var/cache /var/lib/php /var/log /var/mail /var/lib/docker; do [ -d "$d" ] && echo "$(timeout 10 find "$d" -xdev -type f 2>/dev/null | wc -l) $d"; done | sort -rn | head
# clean the usual small-file accumulators (non-destructive to app data):
find /tmp -type f -mtime +3 -delete 2>/dev/null
find /var/lib/php/sessions -type f -mtime +1 -delete 2>/dev/null
find /var/spool/postfix/maildrop -type f -mtime +1 -delete 2>/dev/null
dnf clean all 2>/dev/null || apt-get clean 2>/dev/null
find /var/log -name '*.gz' -mtime +30 -delete 2>/dev/null
df -i / | awk 'NR==2{print "inode use: "$5}'
```
Postfix queue is the culprit → `postsuper -d ALL`. Docker → `docker system prune -f`.

## Disk full (bytes) — see also SOP for /boot-specific (kernel skill)
```bash
df -h / /var; du -xh / 2>/dev/null | sort -rh | head -20
```

## OOM kill during patching
```bash
dmesg -T 2>/dev/null | grep -i 'killed process\|out of memory\|oom-killer' | tail
free -m
# free memory or add a temporary swapfile for the patch window:
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo "temp swap on"
```

## Verify
```bash
df -i / | awk 'NR==2{print "inode "$5}'; df -h / | awk 'NR==2{print "disk "$5}'; free -m | awk '/Mem:/{print "mem free "$4"MB"}'
```

## Escalation
- Recurring inode exhaustion → fix the app's file cleanup/rotation, or move the hot dir to its own volume / XFS.
- Recurring OOM on a small instance → size up, or a persistent swapfile; investigate the memory hog.
