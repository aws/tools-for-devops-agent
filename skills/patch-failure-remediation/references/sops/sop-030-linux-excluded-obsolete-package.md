# SOP-030: Resolve Obsolete/Excluded Package Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-030 |
| Category | excluded_obsolete_package |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2, Amazon Linux 2023, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch reports packages as "excluded" or "obsoleted" preventing updates
- "Package <name> is obsoleted by <name>, but obsoleting package does not provide for requirements"
- "Packages skipped: N excluded" in patch output with needed security fixes in the excluded set
- yum.conf or dnf.conf exclude= directives blocking critical patches
- "package <name> is filtered out by modular filtering" on RHEL 8/9
- "No match for argument: <package>" when package has been superseded
- versionlock plugin preventing security patches from applying

## Root Cause

Package exclusion/obsolescence blocking patches when:

- Administrator-configured exclude= lines in yum.conf/dnf.conf blocking kernel or critical packages
- versionlock plugin (/etc/yum/pluginconf.d/versionlock.list or /etc/dnf/plugins/versionlock.list) pinning vulnerable versions
- RHEL/Oracle Linux module streams causing modular filtering conflicts
- Package renamed/obsoleted between minor releases but dependency solver cannot resolve the transition
- SLES package locks (zypper locks) preventing updates
- Third-party repos providing older versions that conflict with the obsoleted package transition

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — exclusions often create dependency chains that cannot resolve
- SOP-015 (urllib3 Conflict) — versionlock is sometimes used as a workaround that later blocks patches

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Knowledge of why packages were excluded (business justification for the lock/exclude)

## Diagnosis

Check for exclusions and version locks:

```bash
grep -r "^exclude" /etc/yum.conf /etc/dnf/dnf.conf /etc/yum.repos.d/ 2>/dev/null; echo "---"; cat /etc/dnf/plugins/versionlock.list 2>/dev/null || cat /etc/yum/pluginconf.d/versionlock.list 2>/dev/null; echo "---"; dnf module list --enabled 2>/dev/null | head -10; zypper locks 2>/dev/null
```

## Remediation Steps

### Step 1: Identify excluded packages

```bash
if command -v dnf &>/dev/null; then grep -rh "^exclude" /etc/dnf/dnf.conf /etc/yum.repos.d/*.repo 2>/dev/null; dnf config-manager --dump 2>/dev/null | grep exclude; elif command -v yum &>/dev/null; then grep -rh "^exclude" /etc/yum.conf /etc/yum.repos.d/*.repo 2>/dev/null; elif command -v zypper &>/dev/null; then zypper locks 2>/dev/null; fi; echo "Exclusions identified"
```

Expected output: List of exclusions
On failure: continue

### Step 2: Check for versionlock entries

```bash
if command -v dnf &>/dev/null; then dnf versionlock list 2>&1; elif command -v yum &>/dev/null; then yum versionlock list 2>&1; fi; echo "Versionlock check done"
```

Expected output: List of locked packages or empty
On failure: continue

### Step 3: Temporarily clear versionlock for patching

```bash
if command -v dnf &>/dev/null; then cp /etc/dnf/plugins/versionlock.list /etc/dnf/plugins/versionlock.list.bak 2>/dev/null; dnf versionlock clear 2>&1; echo "Versionlock cleared"; elif command -v yum &>/dev/null; then cp /etc/yum/pluginconf.d/versionlock.list /etc/yum/pluginconf.d/versionlock.list.bak 2>/dev/null; yum versionlock clear 2>&1; echo "Versionlock cleared"; elif command -v zypper &>/dev/null; then zypper locks > /tmp/zypper_locks_backup.txt 2>/dev/null; zypper rl '*' 2>/dev/null; echo "Zypper locks cleared"; fi
```

Expected output: "Versionlock cleared" or "Zypper locks cleared"
On failure: continue

### Step 4: Resolve modular filtering issues (RHEL 8/9)

```bash
if command -v dnf &>/dev/null; then PROBLEM=$(dnf check-update 2>&1 | grep "modular filtering"); if [ -n "$PROBLEM" ]; then dnf module reset $(echo "$PROBLEM" | awk '{print $1}' | head -3 | tr '\n' ' ') 2>&1; echo "Module reset done"; else echo "No modular filtering issues"; fi; fi
```

Expected output: "No modular filtering issues" or "Module reset done"
On failure: continue

### Step 5: Verify updates are now available

```bash
if command -v dnf &>/dev/null; then dnf check-update --security 2>&1 | tail -10; echo "Check exit: $?"; elif command -v zypper &>/dev/null; then zypper list-patches --category security 2>&1 | tail -10; echo "Check exit: $?"; fi
```

Expected output: List of available updates
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check-update 2>&1; RC=$?; [ $RC -eq 100 ] && echo "UPDATES AVAILABLE - EXCLUSIONS CLEARED" || echo "UP TO DATE OR ERROR: $RC"; elif command -v zypper &>/dev/null; then zypper list-updates 2>&1 && echo "ZYPPER UPDATES OK"; fi
```

Expected: "UPDATES AVAILABLE - EXCLUSIONS CLEARED" (exit code 100 means updates available)

## Rollback

```bash
if [ -f /etc/dnf/plugins/versionlock.list.bak ]; then cp /etc/dnf/plugins/versionlock.list.bak /etc/dnf/plugins/versionlock.list; echo "Versionlock restored"; fi
if [ -f /etc/yum/pluginconf.d/versionlock.list.bak ]; then cp /etc/yum/pluginconf.d/versionlock.list.bak /etc/yum/pluginconf.d/versionlock.list; echo "Versionlock restored"; fi
if [ -f /tmp/zypper_locks_backup.txt ]; then awk '/^#|^$/{next} {print $3}' /tmp/zypper_locks_backup.txt | while read pkg; do zypper al "$pkg" 2>/dev/null; done; echo "Zypper locks restored"; fi
```

## Escalation

If packages remain excluded after clearing locks:
- Check if exclude is set at the repo level in individual .repo files
- For modular filtering: `dnf module list --all` to understand available streams
- For Oracle Linux: check if ksplice or UEK repos conflict with base RHCK packages
- SLES: verify SUSEConnect module subscriptions include the necessary repos
- Consider if the exclusion was set intentionally for application compatibility — consult change history
