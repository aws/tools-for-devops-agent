# Multilib / architecture conflicts (i686 vs x86_64)

**Signatures:** "Error: Protected multilib versions", "package X.i686 is already installed but
X.x86_64 is being updated", "Multilib version problems found", "cannot install both X.i686 and
X.x86_64", 32-bit packages holding back 64-bit security updates.

**Cause:** the 32-bit (i686) and 64-bit (x86_64) copies of a package are at different versions; the
resolver refuses to leave them mismatched (protected multilib).

## Diagnose (find mismatched pairs)
```bash
rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' | sort | \
  awk -F'.' '{arch=$NF; sub(/\.[^.]*$/,""); a[$0]=a[$0]" "arch} END{for(p in a) if(a[p]~/i686/&&a[p]~/x86_64/) print p": "a[p]}'
dnf check-update 2>&1 | grep -iE 'multilib|protected'
```

## Fix — sync the PAIR to one version (don't upgrade one arch alone)
```bash
dnf distro-sync -y 2>&1 | tail -10          # realigns both arches to the same version
# or target the specific pair:
dnf distro-sync -y <name>.x86_64 <name>.i686
```

## If the i686 copy isn't needed, remove it — after checking nothing requires it
```bash
rpm -q --whatrequires <name>.i686           # confirm no dependents first
dnf remove <name>.i686 -y                    # then distro-sync
```

## Verify
```bash
dnf check-update 2>&1 | grep -qi 'multilib\|protected' && echo "MULTILIB ISSUES REMAIN" || echo "MULTILIB OK"
```

## Escalation
- Oracle DB and some enterprise apps require specific i686 packages — check vendor prereqs before removing any.
- Aggressive resolution: `dnf --best --allowerasing distro-sync` (confirm the removal list).
- Last resort: `rpm -e --nodeps <name>.i686` then `dnf distro-sync` — only if you've confirmed the 32-bit copy is unused.
