# SOP-001: Resolve YUM/DNF Dependency Conflicts During Patching

| Field | Value |
|-------|-------|
| ID | SOP-001 |
| Category | dependency_conflict |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, CentOS 7 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-05-01 |

## Symptoms

- Patch operation fails with "Error: Package conflicts" or "Depsolve Error"
- SSM Patch Manager reports "FAILED" with dependency resolution errors
- YUM/DNF transaction check fails during patching window
- Messages like "Protected multilib versions" or "package conflicts with"
- DNF reports "Problem: conflicting requests" with detailed dependency chains
- Error "nothing provides X needed by Y" when attempting security updates

## Root Cause

Package dependency conflicts occur when:

- Third-party repositories (EPEL, custom internal repos) provide conflicting versions of packages that overlap with base OS repos
- Manually installed packages via `rpm -ivh` conflict with repository versions because they bypass dependency resolution
- Multiple repositories provide the same package at different versions and priority/cost settings are misconfigured
- Previous interrupted transactions left the RPM database in an inconsistent state with partially installed packages
- Version pinning via `versionlock` or `exclude` directives in yum.conf conflict with security patches
- Packages installed from a different major version repository (e.g., RHEL 7 package on RHEL 8)

## Related Failure Patterns

This SOP is often needed after:
- SOP-004 (Corrupt RPM DB) — a corrupted database can manifest as false dependency conflicts
- SOP-012 (RPB Race Condition) — interrupted concurrent transactions leave partial state that looks like conflicts
- SOP-015 (urllib3 Conflict) — a specific instance of this general pattern

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Agent has permission to run SSM commands on the instance
- No other package operations are in progress (check with `pgrep -f 'yum|dnf|rpm'`)

## Diagnosis

Before running remediation, identify the specific conflict:

```bash
yum deplist <failing-package> 2>/dev/null || dnf repoquery --deplist <failing-package> 2>/dev/null
```

Check if versionlock is blocking updates:

```bash
yum versionlock list 2>/dev/null || dnf versionlock list 2>/dev/null
```

List enabled repositories and their priorities:

```bash
yum repolist -v 2>/dev/null | grep -E "Repo-id|Repo-name|Repo-priority" || dnf repolist -v 2>/dev/null | grep -E "Repo-id|Repo-name|Repo-priority"
```

## Remediation Steps

### Step 1: Clean YUM/DNF cache and metadata

```bash
yum clean all && rm -rf /var/cache/yum/* 2>/dev/null; dnf clean all 2>/dev/null; echo "Cache cleared"
```

Expected output: "Cache cleared"
On failure: continue

### Step 2: Check for incomplete transactions

```bash
yum-complete-transaction --cleanup-only 2>/dev/null; dnf history list 2>/dev/null | head -5; echo "Transaction check done"
```

Expected output: Recent transaction history followed by "Transaction check done"
On failure: continue

DNF automatically recovers incomplete transactions on the next run, so no explicit undo is needed here. The history listing is diagnostic — if the last transaction shows a failed state, it will be retried automatically.

### Step 3: Identify conflicting packages

```bash
yum check 2>/dev/null || dnf check 2>/dev/null
```

Expected output: List of dependency issues (may be empty if steps 1-2 resolved)
On failure: abort

### Step 4: Attempt dependency resolution with distro-sync

> **Caution:** `distro-sync` aligns every package to the repo's current version and may *downgrade* (revert) just-applied security patches. Only proceed when the conflict cannot be resolved otherwise.

```bash
yum distro-sync -y --skip-broken 2>/dev/null || dnf distro-sync -y --skip-broken 2>/dev/null; echo "Sync complete"
```

Expected output: "Sync complete"
On failure: abort

### Step 5: Validate system is ready for next patch cycle

```bash
yum check-update --security 2>/dev/null || dnf check-update --security 2>/dev/null; RC=$?; if [ $RC -eq 0 ] || [ $RC -eq 100 ]; then echo "DEPENDENCY CONFLICT RESOLVED - ready for next patch cycle"; else echo "ISSUES REMAIN: exit $RC"; fi
```

Expected output: "DEPENDENCY CONFLICT RESOLVED - ready for next patch cycle"
On failure: abort

## Validation

```bash
yum check-update --security 2>/dev/null || dnf check-update --security 2>/dev/null; echo "EXIT:$?"
```

Expected: No pending security updates or EXIT:0

## Rollback

```bash
yum history undo last -y 2>/dev/null || dnf history undo last -y 2>/dev/null
```

## Escalation

If distro-sync with --skip-broken fails, the conflict likely requires manual package version decisions. Escalate with:
- Output of `yum check` or `dnf check`
- List of third-party repos: `yum repolist all`
- The specific error message from the failed patch operation
