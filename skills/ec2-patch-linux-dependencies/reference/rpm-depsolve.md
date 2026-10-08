# Plain yum/dnf depsolve conflicts, versionlock, third-party repos

**Signatures:** "Error: Package conflicts", "Depsolve Error", "Problem: conflicting requests",
"nothing provides X needed by Y", "package X conflicts with Y", a security update blocked by a
`versionlock`/`exclude`, or an EPEL/third-party package clashing with a base-OS package.

## Diagnose
```bash
dnf check 2>&1 | head
dnf repoquery --deplist <failing-package> 2>/dev/null | head
dnf versionlock list 2>/dev/null; grep -R exclude= /etc/dnf/dnf.conf /etc/yum.repos.d/ 2>/dev/null
dnf repolist -v 2>&1 | grep -E 'Repo-id|Repo-priority'   # priority/cost misconfig
```

## Fix (least-destructive first)
```bash
dnf clean all; dnf makecache                # rule out stale cache producing false conflicts
dnf history 2>&1 | head                      # incomplete transaction? DNF auto-recovers next run
dnf distro-sync -y --skip-broken 2>&1 | tail # realign to repo versions, skipping unsolvable
# clear a lock that's pinning an old version against the security update:
dnf versionlock delete <package> 2>/dev/null
# adjust repo priority if a third-party repo is winning over base incorrectly (priorities: lower = higher priority)
```

## Escalate aggressiveness only if needed
```bash
dnf distro-sync -y --best --allowerasing 2>&1 | tail   # confirm the removal list before running in prod
```

## Verify
```bash
dnf check 2>&1 && dnf check-update --security 2>&1; RC=$?; [ $RC -eq 0 ] || [ $RC -eq 100 ] && echo "DEPSOLVE OK"
```

## Escalation
- Manual version decision needed → capture `dnf check` + `dnf repolist all` + the failing error.
- Third-party/EPEL is the cause → disable it to confirm, then pin priorities so base wins for overlapping packages.
- False conflicts that make no sense → suspect a corrupt RPM DB or interrupted transaction (recover the DB first, separate skill).
- **Never** resolve with `rpm -i --nodeps` — it leaves a broken graph for the next patch run.
