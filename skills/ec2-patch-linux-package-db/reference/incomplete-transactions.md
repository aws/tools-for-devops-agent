# Incomplete / interrupted package transactions

**Signatures:** "There are unfinished transactions remaining", DNF history shows "Incomplete",
"RPMDB altered outside of dnf", half-installed/half-configured packages, transaction timed out
mid-install (maintenance window too short), instance rebooted/OOM-killed during a transaction.

Back up the DB first (see rpm-db-recovery / dpkg-recovery). Confirm no package process is running.

## RPM (dnf/yum)
```bash
dnf history list --last 5 2>&1
test -f /var/lib/dnf/transaction && echo "pending DNF transaction"
# complete/realign the transaction:
dnf -y distro-sync 2>&1 | tail -10; echo "distro-sync exit: ${PIPESTATUS[0]}"
# yum path:
command -v yum-complete-transaction >/dev/null && yum-complete-transaction --cleanup-only 2>&1
# remove duplicates left by a partial install:
dnf remove --duplicates -y 2>&1 | tail -5 || package-cleanup --cleandupes -y 2>&1 | tail -5
dnf check 2>&1; echo "dnf check exit: $?"
```

## Debian/Ubuntu (dpkg/apt)
```bash
dpkg --configure -a 2>&1
apt-get install -f -y 2>&1
apt-get check 2>&1 && echo "APT OK"
```

## SUSE (zypper)
```bash
zypper --non-interactive verify 2>&1
zypper --non-interactive dist-upgrade --dry-run 2>&1 | tail -5
```

## Verify
```bash
dnf check 2>&1 && echo "TRANSACTION STATE OK"   # or apt-get check / zypper verify
```

## Rollback / escalation
- Undo last transaction (RPM): `dnf history undo <id>` (list ids: `dnf history list --last 3`).
- Recurring mid-transaction interruptions → increase the SSM maintenance-window timeout; check for OOM (`dmesg | grep -i oom`).
- Interrupted transactions are a leading cause of DB corruption — if the DB itself is corrupt, recover it first (rpm-db-recovery / dpkg-recovery) then re-run this.
