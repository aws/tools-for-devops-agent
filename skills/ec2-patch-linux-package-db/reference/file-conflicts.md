# RPM/DEB package file conflicts

**Signatures:** "file /usr/... from install of X conflicts with file from package Y",
"Transaction check error: file X conflicts between attempted installs",
"trying to overwrite '/usr/...', which is also in package Y", multilib (i686 vs x86_64) file conflicts,
third-party-repo package owning a base-OS path.

## Diagnose ownership
```bash
rpm -qf /path/from/error 2>/dev/null      # which RPM owns it
dpkg -S /path/from/error 2>/dev/null       # which DEB owns it
rpm -qa --qf '%{NAME}\n' | sort | uniq -d  # duplicate-name packages (RPM)
```

## RPM-based
```bash
dnf remove --duplicates -y 2>&1 | tail -5 || package-cleanup --cleandupes -y 2>&1 | tail -5
# reinstall the owning package to restore correct file ownership:
dnf reinstall -y <package> 2>/dev/null
dnf check 2>&1; echo "dnf check exit: $?"
```

## Debian/Ubuntu
```bash
# for packages left half-installed by a file clash:
dpkg --force-overwrite --configure <package> 2>&1
apt-get install -f -y 2>&1
apt-get check 2>&1 && echo "APT OK"
```

## Verify
```bash
dnf check 2>&1 | grep -ic 'conflict\|duplicate'   # expect 0    (or apt-get check)
```

## Escalation
- Remove the older duplicate explicitly: `rpm -e --nodeps <older-duplicate>` then reinstall.
- Multilib not needed: `dnf remove <package>.i686`.
- If both conflicting packages are genuinely required, one must come from a different repo/version — inspect with `dnf info <package>` / `apt-cache policy <package>`.
- File conflicts are often a symptom of a third-party-repo conflict (separate domain) — if it recurs, review the offending repo.
