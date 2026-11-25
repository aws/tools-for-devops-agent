# SOP-004: Resolve Corrupt RPM Database Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-004 |
| Category | corrupt_rpmdb |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, CentOS 7, Oracle Linux 8, Oracle Linux 9, SLES 12, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "rpmdb: BDB0113 Thread/process failed" or "error: db5 error"
- "rpmdb open failed" errors during patching
- YUM/DNF unable to list installed packages (`rpm -qa` returns errors or partial results)
- "Corruption" or "db_verify" errors in patch logs
- "Header V3 RSA/SHA256 Signature, key ID ... NOKEY" appearing alongside database errors
- "error: rpmdb: damaged header instance"
- Transaction failures with "cannot open Packages database in /var/lib/rpm"

## Root Cause

RPM database corruption occurs when:

- Previous package operation was interrupted (power loss, OOM kill, forced termination via `kill -9`)
- Disk I/O errors during write operations to /var/lib/rpm (failing EBS volume, filesystem errors)
- Concurrent access to RPM database by multiple processes (race condition between yum-cron and SSM patching)
- Filesystem ran out of space during database update (partial writes corrupt BerkeleyDB files)
- NFS-mounted /var with latency spikes causing lock contention
- AL2 uses BerkeleyDB (BDB) backend which is more susceptible; AL2023/RHEL9 use sqlite backend which is more resilient

## Related Failure Patterns

This SOP is often a prerequisite for:
- SOP-001 (Dependency Conflicts) — a corrupted DB can report false conflicts
- SOP-012 (RPB Race Condition) — race conditions are a common cause of DB corruption

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No other package operations are in progress
- /var/lib/rpm directory exists and is accessible
- Sufficient disk space for backup (at least 200MB free in /var/lib)

## Diagnosis

Determine the database backend and corruption extent:

```bash
file /var/lib/rpm/Packages 2>/dev/null; rpm --verifydb 2>&1 | head -10; ls -la /var/lib/rpm/__db.* 2>/dev/null
```

Check if the instance uses BerkeleyDB or sqlite:

```bash
rpm -qa --dbpath /var/lib/rpm 2>&1 | head -1
```

## Remediation Steps

### Step 1: Verify RPM database corruption

```bash
OUTPUT=$(rpm --verifydb 2>&1); RC=$?; echo "$OUTPUT" | head -20; echo "VERIFY_EXIT:$RC"
```

Expected output: Error messages or "VERIFY_EXIT:0"
On failure: continue (corruption confirmed)

Note: capture `rpm --verifydb`'s exit code into `RC` before piping to `head`,
otherwise `$?` reports `head`'s status (almost always 0) and VERIFY_EXIT would
never reflect actual corruption.

### Step 2: Kill any processes holding locks on RPM database

```bash
rm -f /var/lib/rpm/.dbenv.lock /var/lib/rpm/.rpm.lock 2>/dev/null; echo "Locks cleared"
```

Expected output: "Locks cleared"
On failure: continue

### Step 3: Backup current RPM database

```bash
cp -a /var/lib/rpm /var/lib/rpm.backup.$(date +%Y%m%d%H%M%S); echo "Backup created"
```

Expected output: "Backup created"
On failure: abort (insufficient space or permissions)

### Step 4: Rebuild RPM database (backend-aware)

The recovery differs by rpmdb backend. AL2/RHEL7/CentOS7/OL7/SLES12 use
**BerkeleyDB** (`Packages` + `__db.*`); AL2023/RHEL9/OL9/SLES15 use **SQLite**
(`rpmdb.sqlite`). Detect the backend and rebuild accordingly — a BerkeleyDB-only
`rm __db.*` will NOT recover a corrupt `rpmdb.sqlite`.

```bash
if [ -f /var/lib/rpm/rpmdb.sqlite ]; then
  # SQLite backend (AL2023/RHEL9/OL9/SLES15): move the corrupt sqlite db aside
  # and rebuild the index from the on-disk package headers.
  cp -a /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite.corrupt.$(date +%Y%m%d%H%M%S) 2>/dev/null
  rm -f /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite-shm /var/lib/rpm/rpmdb.sqlite-wal
  rpm --rebuilddb; echo "Rebuild complete (sqlite backend)"
else
  # BerkeleyDB backend (AL2/RHEL7/CentOS7/OL7/SLES12): drop the cached env files
  # (__db.*), then rebuild the index from the Packages file.
  rm -f /var/lib/rpm/__db.*; rpm --rebuilddb; echo "Rebuild complete (berkeleydb backend)"
fi
```

Expected output: "Rebuild complete (sqlite backend)" or "Rebuild complete (berkeleydb backend)"
On failure: abort

This picks the correct recovery per backend: for SQLite it moves the corrupt
`rpmdb.sqlite` (and its `-shm`/`-wal` sidecars) aside and rebuilds the index from the
package headers; for BerkeleyDB it removes the cached environment files (`__db.*`),
which hold lock and memory-pool state, then rebuilds from the `Packages` file. On AL2023,
use this SOP (or SOP-085) for rpmdb recovery.

### Step 5: Clear zypper cache (SLES only)

```bash
if command -v zypper &>/dev/null; then zypper clean -a 2>&1; echo "Zypper cache cleared"; else echo "Not SLES - skipped"; fi
```

Expected output: "Zypper cache cleared" or "Not SLES - skipped"
On failure: continue

### Step 6: Verify rebuilt database

```bash
rpm -qa | wc -l
```

Expected output: Non-zero package count (typical instances have 300-1500 packages)
On failure: abort

## Validation

```bash
rpm --verifydb 2>&1; RC=$?; rpm -qa | wc -l | awk '{if ($1 > 0) print "OK: "$1" packages indexed"; else print "FAIL: empty db"}'; exit $RC
```

Expected: "OK: N packages indexed" with exit code 0

## Rollback

```bash
LATEST_BACKUP=$(ls -td /var/lib/rpm.backup.* 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then rm -rf /var/lib/rpm; mv "$LATEST_BACKUP" /var/lib/rpm; echo "Restored from backup"; else echo "No backup found"; fi
```

## Escalation

If `rpm --rebuilddb` itself fails:
- The Packages file may be irrecoverably corrupt
- Consider restoring /var/lib/rpm from a recent AMI or snapshot
- As a last resort, reinstall all packages: `rpm -qa --qf '%{NAME}\n' > /tmp/pkg-list.txt` (if readable), then reinstall from that list after restoring an empty database
