# SOP-039: Resolve DNF/YUM Module Stream Conflicts on RHEL 8/9

| Field | Value |
|-------|-------|
| ID | SOP-039 |
| Category | module_stream_conflict |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Modular dependency problems" in DNF output
- "package X is filtered out by modular filtering"
- "Error: No available modular metadata for modular package X"
- "Module <name>:<stream> profiles: <profiles> are not available"
- "Cannot install package X because it conflicts with module stream"
- "Problem: module stream is enabled but packages are not installed"
- "Modular dependency problem: nothing provides module(platform:elX)" 
- Security patches for modular packages cannot be applied due to stream pinning

## Root Cause

Module stream conflicts occur when:

- A module stream was enabled but its packages were installed outside the module framework
- Multiple streams of the same module cannot coexist (e.g., PHP 7.4 vs PHP 8.0)
- Module stream was enabled in a previous RHEL minor release and packages evolved incompatibly
- Third-party repos provide packages that satisfy module dependencies incorrectly
- Module metadata in repo is corrupted or outdated
- `dnf module reset` was done but dependent packages remain from the old stream
- Oracle Linux provides different module availability than standard RHEL

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — modular filtering is a dependency resolution issue
- SOP-030 (Excluded Packages) — modular filtering effectively excludes packages
- SOP-035 (Third-Party Repo Conflict) — third-party repos can break module resolution

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is running RHEL 8/9, Oracle Linux 8/9, or Amazon Linux 2023

## Diagnosis

Check module state:

```bash
dnf module list --enabled 2>&1; echo "---"; dnf module list --disabled 2>&1 | head -20; echo "---"; dnf module list --installed 2>&1
```

## Remediation Steps

### Step 1: List current module states

```bash
echo "=== Enabled modules ==="; dnf module list --enabled 2>&1; echo "=== Installed module profiles ==="; dnf module list --installed 2>&1; echo "Module state checked"
```

Expected output: Module state listing
On failure: continue

### Step 2: Identify the conflicting module

```bash
CONFLICTS=$(dnf check-update 2>&1 | grep -i "modular\|filtered\|module"); if [ -n "$CONFLICTS" ]; then echo "Module conflicts:"; echo "$CONFLICTS"; else echo "No modular conflicts detected"; fi; echo "---"; dnf module provides $(dnf check-update 2>&1 | grep "filtered" | awk '{print $1}' | head -3) 2>/dev/null
```

Expected output: Conflicting module information
On failure: continue

### Step 3: Reset problematic module streams

```bash
PROBLEM_MODULES=$(dnf check-update 2>&1 | grep -oP 'module\(\K[^:)]+' | sort -u | head -5); if [ -n "$PROBLEM_MODULES" ]; then for mod in $PROBLEM_MODULES; do dnf module reset "$mod" -y 2>&1; echo "Reset module: $mod"; done; else echo "No modules to reset - attempting full module reset check"; dnf module list --enabled 2>&1 | awk 'NR>2 && NF>0 {print $1}' | sort -u | while read mod; do echo "Enabled: $mod"; done; fi
```

Expected output: Module reset confirmations
On failure: continue

### Step 4: Re-enable correct module streams

```bash
dnf module list --installed 2>&1 | awk 'NR>2 && $NF ~ /i/ {print $1":"$2}' | while read mod_stream; do dnf module enable "$mod_stream" -y 2>&1; echo "Re-enabled: $mod_stream"; done; echo "Module streams restored"
```

Expected output: "Module streams restored"
On failure: continue

### Step 5: Verify dependency resolution

```bash
dnf check 2>&1; echo "DNF check exit: $?"; echo "---"; dnf check-update 2>&1 | grep -ic "filtered\|modular" | awk '{print "Remaining modular issues: "$1}'
```

Expected output: "DNF check exit: 0" with 0 remaining modular issues
On failure: abort

## Validation

```bash
dnf check-update 2>&1 | grep -qi "modular\|filtered" && echo "MODULAR ISSUES REMAIN" || echo "MODULE STREAMS OK"; dnf check 2>&1 && echo "DNF STATE OK"
```

Expected: "MODULE STREAMS OK" and "DNF STATE OK"

## Rollback

```bash
echo "Module reset is generally safe - modules can be re-enabled with:"
echo "  dnf module enable <module>:<stream>"
echo "  dnf module install <module>:<stream>/<profile>"
dnf module list --enabled 2>&1
```

## Escalation

If module conflicts cannot be resolved:
- List all available streams: `dnf module list --all <module>`
- Force switch stream: `dnf module switch-to <module>:<stream> -y`
- For deeply conflicting state: `dnf module reset <module> && dnf distro-sync`
- Check if a third-party repo is providing modular metadata that conflicts
- On Oracle Linux, verify that the ol*_appstream repo is the correct version for the OS release
- Consider `dnf --allowerasing module switch-to` for forced stream transitions
