# dpkg recovery (journal corruption vs status corruption — different fixes)

**Signatures:** `dpkg was interrupted, you must manually run 'dpkg --configure -a'`,
parse error `near line N ... end of file during value of field` (status corruption),
`dpkg status database is locked`, half-installed/half-configured packages, APT `E: dpkg was interrupted`.

Always back up first: `cp /var/lib/dpkg/status /var/lib/dpkg/status.bak`.

## Case A: corrupt journal files in /var/lib/dpkg/updates/
The updates/ dir holds pending, uncommitted state changes. Corrupt entries block ALL dpkg ops.
```bash
ls -la /var/lib/dpkg/updates/; file /var/lib/dpkg/updates/* 2>/dev/null
rm -f /var/lib/dpkg/updates/*      # discards incomplete, never-committed transactions
dpkg --configure -a 2>&1; echo "configure exit: $?"
apt-get check 2>&1 && echo "APT OK"
```

## Case B: corrupt /var/lib/dpkg/status (parse error)
`status-old` is written by dpkg on each successful status update — normally present. Restore it:
```bash
test -s /var/lib/dpkg/status-old && cp /var/lib/dpkg/status-old /var/lib/dpkg/status || echo "STATUS_OLD_MISSING"
dpkg --configure -a --force-confdef 2>&1; echo "configure exit: $?"
apt-get install -f -y 2>&1
apt-get check 2>&1 && echo "APT OK"
```

## Verify
```bash
dpkg --audit 2>&1
dpkg-query -l 2>/dev/null | grep -E '^(iF|iU|rH|hH|pH)' | wc -l   # expect 0 broken
apt-get check 2>&1 && echo "DPKG and APT OK"
```

## Rollback / escalation
- If restoring status-old made things worse: `cp /var/lib/dpkg/status.bak /var/lib/dpkg/status` (returns to the broken-but-original state, preserves evidence).
- `status-old` absent/empty AND status unparseable → escalate; may need snapshot restore. Capture `tail -20 status.bak`, `dpkg --audit`, `ls -lh /var/lib/dpkg/`.
- Broken third-party APT sources often co-occur (DNS unresolvable) — remove the offending `.list` under `/etc/apt/sources.list.d/` then `apt-get update`; review before deleting (removed sources have no rollback).
