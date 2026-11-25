# SOP-045: Resolve Multilib/Architecture Package Conflicts

| Field | Value |
|-------|-------|
| ID | SOP-045 |
| Category | multilib_arch_conflict |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Error: Protected multilib versions" during yum/dnf update
- "package X.i686 is already installed but X.x86_64 is being updated"
- "Multilib version problems found" blocking transaction
- "Error: Package: X.i686 requires libY but none of the providers can be installed"
- "cannot install both X.i686 and X.x86_64" from dependency resolver
- 32-bit packages blocking 64-bit security updates
- "Protected multilib versions: X.x86_64 != X.i686"

## Root Cause

Multilib conflicts occur when:

- 32-bit (i686) and 64-bit (x86_64) versions of same package are installed at different versions
- Security update only available for x86_64 but i686 version holds it back
- Third-party application installed 32-bit compatibility libraries that now conflict with base updates
- Oracle database or other enterprise software requires i686 packages that drift from x86_64 versions
- Partial update previously upgraded x86_64 but failed to upgrade matching i686 package
- Package manager cannot find i686 version matching the new x86_64 version in enabled repos

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — multilib is a specific dependency conflict type
- SOP-043 (File Conflicts) — multilib packages can have file ownership conflicts

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of whether 32-bit packages are needed for applications

## Diagnosis

Check installed multilib packages:

```bash
rpm -qa --qf '%{NAME}.%{ARCH}\n' | sort | awk -F. '{name=$1; for(i=2;i<NF;i++) name=name"."$i; arch=$NF; a[name]=a[name]" "arch} END {for(n in a) if(a[n] ~ /i686/ && a[n] ~ /x86_64/) print n": "a[n]}' | head -20
```

## Remediation Steps

### Step 1: Identify multilib version mismatches

```bash
MISMATCHES=$(rpm -qa --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' | sort | awk -F'.' '{arch=$NF; sub(/\.[^.]*$/,""); pkg=$0; a[pkg]=a[pkg]" "arch} END {for(p in a) if(a[p] ~ /i686/ && a[p] ~ /x86_64/) print "MATCH: "p}'); PROBLEMS=$(dnf check-update 2>&1 | grep -i "multilib\|protected"); echo "Mismatches:"; echo "${MISMATCHES:-none}"; echo "---"; echo "Problems:"; echo "${PROBLEMS:-none}"
```

Expected output: List of multilib issues
On failure: continue

### Step 2: Sync multilib packages to same version

```bash
if command -v dnf &>/dev/null; then dnf distro-sync -y --allowerasing 2>&1 | tail -10; echo "Distro-sync exit: ${PIPESTATUS[0]}"; elif command -v yum &>/dev/null; then yum distro-sync -y 2>&1 | tail -10; echo "Distro-sync exit: ${PIPESTATUS[0]}"; fi
```

Expected output: Exit code 0
On failure: continue

### Step 3: Identify unneeded 32-bit packages (manual review recommended)

```bash
UNNEEDED_I686=$(rpm -qa --qf '%{NAME}.%{ARCH}\n' | grep "\.i686$" | while read pkg; do NAME=$(echo "$pkg" | sed 's/\.i686$//'); if ! rpm -q --whatrequires "$pkg" 2>/dev/null | grep -qv "no package"; then echo "$pkg"; fi; done | head -10); if [ -n "$UNNEEDED_I686" ]; then echo "Potentially removable i686 packages (manual review recommended):"; echo "$UNNEEDED_I686"; else echo "No unneeded i686 packages found"; fi
```

Expected output: List of candidate packages or "No unneeded i686 packages found"
On failure: continue

### Step 4: Synchronize the specific multilib package pairs (distro-sync changes package versions)

```bash
PROBLEM_PKG=$(dnf check-update 2>&1 | grep -i "multilib" | awk '{print $1}' | head -3); if [ -n "$PROBLEM_PKG" ]; then for pkg in $PROBLEM_PKG; do BASE=$(echo "$pkg" | sed 's/\.\(x86_64\|i686\)$//'); dnf distro-sync -y "${BASE}.x86_64" "${BASE}.i686" 2>&1 | tail -3; done; echo "Multilib pair synchronized"; else echo "No multilib problem packages"; fi
```

Expected output: "Multilib pair synchronized" or "No multilib problem packages"
On failure: continue

### Step 5: Verify no multilib issues remain

```bash
dnf check 2>&1 | grep -ic "multilib\|duplicate" | awk '{if ($1==0) print "MULTILIB OK"; else print "ISSUES REMAIN: "$1}'
```

Expected output: "MULTILIB OK"
On failure: abort

## Validation

```bash
dnf check-update 2>&1 | grep -qi "multilib\|protected" && echo "MULTILIB ISSUES REMAIN" || echo "MULTILIB CONFLICTS RESOLVED"
```

Expected: "MULTILIB CONFLICTS RESOLVED"

## Rollback

```bash
echo "Distro-sync and package removal can be reversed with:"
echo "  dnf history undo last"
echo "If 32-bit packages were removed and are needed, reinstall with:"
echo "  dnf install <package>.i686"
```

## Escalation

If multilib conflicts cannot be resolved:
- Check if 32-bit packages are required by an application: `rpm -q --whatrequires <package>.i686`
- Use `--best --allowerasing` with dnf to allow aggressive resolution
- Remove the specific blocking i686 package and see if application still works
- For Oracle DB environments: verify Oracle prerequisites documentation for required i686 packages
- As last resort: `rpm -e --nodeps <package>.i686` then `dnf distro-sync`
