# RPM database recovery (backend-correct: SQLite vs BerkeleyDB)

**Signatures:** `rpmdb: BDB0113`, `error: db5 error`, `rpmdb open failed`,
`database disk image is malformed`, `file is not a database`, `cannot open Packages database
in /var/lib/rpm`, segfault during rpm, `rpm -qa` empty/partial.

**Detect the backend first:**
```bash
ls -la /var/lib/rpm/rpmdb.sqlite   # present -> SQLite (AL2023/RHEL9/OL9/SLES15)
ls -la /var/lib/rpm/Packages /var/lib/rpm/__db.*   # present -> BerkeleyDB (AL2/RHEL7-8/CentOS7/OL7/SLES12)
```
Always back up first: `cp -a /var/lib/rpm /var/lib/rpm.backup.$(date +%s)`. Clear stale locks:
`rm -f /var/lib/rpm/.rpm.lock /var/lib/rpm/.dbenv.lock`.

## BerkeleyDB backend
```bash
rm -f /var/lib/rpm/__db.*      # cached env (locks/mempool), safe to drop
rpm --rebuilddb
rpm -qa | wc -l                # expect a sane non-zero count
```

## SQLite backend — stale/index corruption (headers still intact)
```bash
cp -a /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite.corrupt.$(date +%s)
rm -f /var/lib/rpm/rpmdb.sqlite /var/lib/rpm/rpmdb.sqlite-shm /var/lib/rpm/rpmdb.sqlite-wal
rpm --rebuilddb
rpm -qa | wc -l
```

## SQLite backend — TOTAL loss ("file is not a database"): rebuild from repos
`rpm --rebuilddb` rebuilds from on-disk headers; if the sqlite file is totally corrupt there are
NONE, and you get an EMPTY db (0 packages). Reconstruct the inventory from the repositories instead:
```bash
PKG_COUNT=$(rpm -qa 2>/dev/null | wc -l)
if [ "$PKG_COUNT" -eq 0 ]; then
  rm -f /var/lib/rpm/rpmdb.sqlite* /var/lib/rpm/__db.* /var/lib/rpm/.rpm.lock /var/lib/rpm/.dbenv.lock
  rpm --initdb
  rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-amazon-linux-2023 2>/dev/null || true
  dnf -y --releasever=latest reinstall system-release 2>&1 | tail -5 || dnf -y install system-release 2>&1 | tail -5
  dnf -y reinstall '*' --skip-broken 2>&1 | tail -20
  dnf -y distro-sync --skip-broken 2>&1 | tail -20
  echo "reconstructed: $(rpm -qa | wc -l) packages"
fi
```

## Verify
```bash
rpm --verifydb 2>&1; RC=$?; rpm -qa | wc -l; dnf check 2>&1; echo "verifydb_exit=$RC"
```

## Escalation
- Still 0 packages after repo reconstruction (no repo connectivity, or installed pkgs absent from all
  enabled repos) → restore `/var/lib/rpm` from a recent EBS snapshot/AMI.
- `Packages` (BDB) irrecoverably corrupt → restore from snapshot; last resort reinstall from a saved list.
