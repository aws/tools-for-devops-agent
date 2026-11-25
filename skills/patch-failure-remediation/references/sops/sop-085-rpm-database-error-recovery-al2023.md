# SOP-085: RPM Database Error Recovery — Amazon Linux 2023

| Field | Value |
|-------|-------|
| ID | SOP-085 |
| Category | corrupt_rpmdb |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2023, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-08-15 |

## Symptoms

- Patch fails with "rpmdb: BDB0113 Thread/process failed" or "error: rpmdb open failed"
- DNF fails to install/update with "Error: rpmdb open failed"
- SQLite corruption: "database disk image is malformed"
- Stale locks: "waiting for lock on /var/lib/rpm/.rpm.lock"
- Segfault during rpm operations: "Segmentation fault (core dumped)"
- `rpm -qa` returns nothing or partial results (empty package list)
- Transaction failures with "cannot open Packages database in /var/lib/rpm"
- SQLite total loss: "file is not a database" / "cannot open Packages index using sqlite"
- After `rpm --rebuilddb`, the database is empty (`rpm -qa` returns 0 packages) — the on-disk `rpmdb.sqlite` was irrecoverable, so there were no headers left to rebuild from

## Root Cause

RPM database corruption on AL2023 occurs when:

- Instance terminated or rebooted during package transaction
- Disk full (`/var` filesystem at 100%) causing partial writes
- EBS volume detach during write operation
- OOM killer terminated rpm/dnf process mid-transaction
- Concurrent rpm operations (multiple yum/dnf processes racing)
- Filesystem corruption (XFS/ext4 errors on underlying block device)
- AL2023 uses SQLite-based RPM database (`rpmdb.sqlite`) which differs from BerkeleyDB on AL2

## Related Failure Patterns

This SOP is closely related to:
- SOP-004 (Corrupt RPM DB) — general RPM database corruption (BerkeleyDB-focused, AL2/RHEL8)
- SOP-012 (RPB Race Condition) — race conditions are a common cause of DB corruption
- SOP-080 (Boot Partition Full) — disk space issues can trigger corruption

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No other package operations are in progress
- /var/lib/rpm directory exists and is accessible
- Sufficient disk space for backup (at least 200MB free in /var/lib)
- Confirm this is a non-production instance OR obtain change approval
- EBS snapshot taken before recovery (recommended)

## Diagnosis

Determine the database backend and corruption extent:

```bash
file /var/lib/rpm/rpmdb.sqlite 2>/dev/null; rpm --verifydb 2>&1 | head -10; df -h /var; ls -la /var/lib/rpm/
```

Check for running package processes:

```bash
ps aux | grep -E 'rpm|dnf|yum' | grep -v grep
```

## Remediation Steps

### Step 1: Clear stale lock files

```bash
rm -f /var/lib/rpm/.rpm.lock /var/lib/rpm/.dbenv.lock 2>/dev/null; echo "Locks cleared"
```

Expected output: "Locks cleared"
On failure: continue

### Step 2: Remove BerkeleyDB cache files

```bash
rm -f /var/lib/rpm/__db.* 2>/dev/null; rpm -qa | head -5 && echo "DB cache clear resolved issue" || echo "Further recovery needed"
```

Expected output: Package names followed by "DB cache clear resolved issue"
On failure: continue

### Step 3: Backup current RPM database

```bash
cp -a /var/lib/rpm /var/lib/rpm.backup.$(date +%Y%m%d%H%M%S); echo "Backup created"
```

Expected output: "Backup created"
On failure: abort (insufficient space or permissions)

### Step 4: Rebuild RPM database

```bash
rm -f /var/lib/rpm/__db.*; rpm --rebuilddb; echo "Rebuild complete"
```

Expected output: "Rebuild complete"
On failure: continue to Step 5

### Step 5: SQLite database recovery (AL2023 specific)

```bash
if [ -f /var/lib/rpm/rpmdb.sqlite ]; then
  cp /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite.corrupt.$(date +%Y%m%d)
  rm -f /var/lib/rpm/rpmdb.sqlite
  rpm --rebuilddb
  echo "SQLite recovery complete"
else
  echo "No SQLite DB found - skipped"
fi
```

Expected output: "SQLite recovery complete" or "No SQLite DB found - skipped"
On failure: continue to Step 6

### Step 6: Full database rebuild from package headers (last resort)

```bash
rm -f /var/lib/rpm/__db.* /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/.rpm.lock /var/lib/rpm/.dbenv.lock
rpm --rebuilddb
rpm -qa | wc -l | awk '{if ($1 > 0) print "Rebuilt: "$1" packages"; else print "FAIL: empty db"}'
```

Expected output: "Rebuilt: N packages" where N > 300
On failure: abort

### Step 7: Detect empty rebuild and reconstruct inventory from repositories (AL2023 total-loss path)

On AL2023, `rpm --rebuilddb` reconstructs the index **from the headers already inside `rpmdb.sqlite`**. If that file was totally corrupt ("file is not a database"), there are no headers to rebuild from and Steps 4–6 leave an **empty database (0 packages)**. `--rebuilddb` cannot recover this — the inventory must be rebuilt from the repositories instead.

```bash
PKG_COUNT=$(rpm -qa 2>/dev/null | wc -l)
if [ "$PKG_COUNT" -gt 0 ]; then
  echo "DB healthy: $PKG_COUNT packages — repo reconstruction not needed"
else
  echo "Empty rpmdb after rebuild — reconstructing inventory from repositories"
  # Remove all SQLite artifacts incl. WAL/SHM sidecars, then init a fresh, valid DB.
  rm -f /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite-shm /var/lib/rpm/rpmdb.sqlite-wal \
        /var/lib/rpm/__db.* /var/lib/rpm/.rpm.lock /var/lib/rpm/.dbenv.lock 2>/dev/null
  rpm --initdb
  rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-amazon-linux-2023 2>/dev/null || true
  # Repopulate headers from the repos. system-release first so releasever resolves,
  # then reinstall the full set. --skip-broken keeps one bad pkg from aborting all.
  dnf -y --releasever=latest reinstall system-release 2>&1 | tail -5 || \
    dnf -y install system-release 2>&1 | tail -5
  dnf -y reinstall '*' --skip-broken 2>&1 | tail -20
  # Any packages the repos no longer carry won't reinstall; distro-sync realigns them.
  dnf -y distro-sync --skip-broken 2>&1 | tail -20
  echo "Repo-based reconstruction complete: $(rpm -qa | wc -l) packages"
fi
```

Expected output: "DB healthy: N packages…" OR "Repo-based reconstruction complete: N packages" with N > 300
On failure (still 0 packages, or a package is installed on disk but absent from every enabled repo so cannot be reindexed): abort and escalate — the box needs an EBS-snapshot restore.

### Step 8: Verify rebuilt database

```bash
rpm -qa | wc -l
```

Expected output: Non-zero package count (AL2023 typically has 300-600+ packages)
On failure: abort

## Validation

```bash
rpm --verifydb 2>&1; RC=$?; PKG_COUNT=$(rpm -qa | wc -l); dnf check 2>&1; DNF_RC=$?; if [ $PKG_COUNT -gt 0 ] && [ $DNF_RC -eq 0 ]; then echo "OK: $PKG_COUNT packages indexed, dnf healthy"; else echo "FAIL: pkg_count=$PKG_COUNT dnf_rc=$DNF_RC"; fi; exit $RC
```

Expected: "OK: N packages indexed, dnf healthy" with exit code 0

## Rollback

```bash
LATEST_BACKUP=$(ls -td /var/lib/rpm.backup.* 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then rm -rf /var/lib/rpm; mv "$LATEST_BACKUP" /var/lib/rpm; echo "Restored from backup"; else echo "No backup found"; fi
```

## Escalation

Escalate only after Step 7 (repo-based reconstruction) has been attempted and the database is still empty:
- `rpm --rebuilddb` alone cannot recover a totally-corrupt AL2023 `rpmdb.sqlite` ("file is not a database") — it reconstructs from the on-disk headers, which are gone. Step 7's `rpm --initdb` + `dnf reinstall '*'` rebuilds the inventory from the repositories instead; this is the correct path for total loss, not `--rebuilddb`.
- If Step 7 still yields 0 packages (e.g. no repo connectivity, or installed packages absent from all enabled repos so they cannot be reindexed): restore `/var/lib/rpm` from a recent EBS snapshot or AMI.
- If systemic across multiple instances, file AWS Support severity 2 case.
