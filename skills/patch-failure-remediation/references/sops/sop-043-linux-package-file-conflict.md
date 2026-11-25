# SOP-043: Resolve RPM/DEB Package File Conflicts During Patching

| Field | Value |
|-------|-------|
| ID | SOP-043 |
| Category | package_file_conflict |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "file /usr/lib64/X from install of Y conflicts with file from package Z"
- "Transaction check error: file X conflicts between attempted installs"
- "Trying to overwrite '/usr/X', which is also in package Y"
- "dpkg: error processing archive: trying to overwrite shared path"
- "File conflict: /usr/lib/X is from both package-A and package-B"
- "cannot install the best candidate for the job" due to file ownership conflicts
- Packages from different repos own the same file at different versions

## Root Cause

Package file conflicts occur when:

- Two packages claim ownership of the same file (packaging error or repo mismatch)
- Locally modified files conflict with new package version attempting to install
- Third-party package installed files into paths owned by base OS packages
- Package was replaced/renamed but old version not properly marked as obsoleting the new one
- Multilib (i686 vs x86_64) packages conflict on shared file paths
- Manual file creation or symlinks in paths managed by packages
- Docker/container runtime packages from different sources (OS repo vs Docker repo)

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — file conflicts are a subset of dependency resolution
- SOP-035 (Third-Party Repo Conflict) — third-party repos commonly cause file conflicts
- SOP-032 (Incomplete Transaction) — partial installs leave conflicting file state

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Identify conflicting files and owning packages:

```bash
# Check which package owns a conflicting file (replace path from error message)
rpm -qf /usr/lib64/libexample.so 2>/dev/null; dpkg -S /usr/lib/example 2>/dev/null; echo "---"; rpm -Va --nofiles 2>/dev/null | grep "^missing\|^..5" | head -10
```

## Remediation Steps

### Step 1: Identify file conflicts from last failed transaction

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 | grep -i "conflict\|duplicate" | head -20; elif command -v apt-get &>/dev/null; then dpkg --audit 2>&1; apt-get check 2>&1 | head -20; fi; echo "Conflicts identified"
```

Expected output: List of conflicts
On failure: continue

### Step 2: Find duplicate/conflicting file ownership (RPM-based)

```bash
if command -v rpm &>/dev/null; then DUPES=$(rpm -qa --qf '%{NAME}\n' | sort | uniq -d); if [ -n "$DUPES" ]; then echo "Duplicate packages:"; echo "$DUPES"; else echo "No duplicate packages"; fi; package-cleanup --problems 2>/dev/null | head -10; fi; echo "Ownership check done"
```

Expected output: Duplicate package information
On failure: continue

### Step 3: Remove duplicate packages (RPM-based)

```bash
if command -v dnf &>/dev/null; then dnf remove --duplicates -y 2>&1 | tail -5; echo "Duplicates removed"; elif command -v package-cleanup &>/dev/null; then package-cleanup --cleandupes -y 2>&1 | tail -5; echo "Duplicates removed"; else echo "Not RPM-based or no cleanup tool"; fi
```

Expected output: "Duplicates removed"
On failure: continue

### Step 4: Force overwrite for Debian-based file conflicts

```bash
if command -v dpkg &>/dev/null; then BROKEN=$(dpkg -l | grep "^iF\|^iU" | awk '{print $2}'); if [ -n "$BROKEN" ]; then for pkg in $BROKEN; do dpkg --force-overwrite --configure "$pkg" 2>&1; done; echo "Force-configure done"; else echo "No broken packages"; fi; fi
```

Expected output: "No broken packages" or "Force-configure done"
On failure: continue

### Step 5: Reinstall conflicting packages to fix file ownership

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 | grep "duplicate" | awk '{print $NF}' | head -5 | while read pkg; do dnf reinstall -y "$pkg" 2>/dev/null; done; echo "Reinstall attempted"; elif command -v apt-get &>/dev/null; then apt-get install -f -y 2>&1 | tail -5; echo "APT fix attempted"; elif command -v zypper &>/dev/null; then zypper verify --non-interactive 2>&1 | tail -5; echo "Zypper verify done"; fi
```

Expected output: Reinstall/fix results
On failure: continue

### Step 6: Verify no file conflicts remain

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1; echo "DNF check exit: $?"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1; echo "APT check exit: $?"; elif command -v zypper &>/dev/null; then zypper verify 2>&1; echo "Zypper verify exit: $?"; fi
```

Expected output: Exit code 0
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 | grep -ic "conflict\|duplicate" | awk '{if ($1==0) print "FILE CONFLICTS RESOLVED"; else print "CONFLICTS REMAIN: "$1}'; elif command -v apt-get &>/dev/null; then apt-get check 2>&1 && echo "FILE CONFLICTS RESOLVED"; fi
```

Expected: "FILE CONFLICTS RESOLVED"

## Rollback

```bash
echo "File conflict resolution (reinstall/remove-duplicates) is generally safe"
echo "If a needed package was removed, reinstall with: dnf install <package> or apt-get install <package>"
```

## Escalation

If file conflicts persist:
- Use `rpm -e --nodeps <older-duplicate>` to remove the conflicting version, then reinstall
- For Debian: `dpkg --force-overwrite -i /var/cache/apt/archives/<package>.deb`
- Identify the source repo of each conflicting package: `dnf info <package>` or `apt-cache policy <package>`
- If both packages are needed, one may need to be from a different repo or version
- For multilib conflicts: `dnf remove <package>.i686` if 32-bit is not needed
