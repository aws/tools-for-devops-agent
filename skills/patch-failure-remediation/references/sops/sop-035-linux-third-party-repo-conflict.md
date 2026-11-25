# SOP-035: Resolve Third-Party Repository Conflicts During Patching

| Field | Value |
|-------|-------|
| ID | SOP-035 |
| Category | third_party_repo_conflict |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Error: Package X from repo Y requires Z, but none of the providers can be installed"
- Conflicting package versions between OS base repos and third-party repos (EPEL, Remi, IUS, PGDG, Docker, etc.)
- "Problem: package X-version.3rdparty conflicts with X provided by X-version.base"
- "The following packages have unmet dependencies" referencing PPA or third-party sources
- "cannot install both X-1.0 and X-2.0" where versions come from different repos
- Priority/cost settings causing wrong repo to be preferred
- "Packages excluded due to repository priority protections"

## Root Cause

Third-party repository conflicts occur when:

- EPEL, Remi, or other third-party repos provide packages that overlap with base OS packages at different versions
- Repository priority (priority= in .repo files) not configured, causing higher-version third-party packages to override base packages
- Docker/Kubernetes repos provide conflicting containerd, runc, or other system packages
- PostgreSQL PGDG repo provides system libraries that conflict with base
- Node.js/PHP third-party repos conflict with OS-provided versions
- Ubuntu PPAs provide packages that break apt dependency resolution
- SLES PackageHub providing conflicting packages with base modules

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — third-party repos are the most common cause
- SOP-030 (Excluded Packages) — exclusions are often applied to work around third-party conflicts

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of which third-party repos are intentionally configured

## Diagnosis

Identify all configured repositories and their priorities:

```bash
if command -v dnf &>/dev/null; then dnf repolist -v 2>&1 | grep -E "Repo-id|Repo-name|Repo-priority" | paste - - -; elif command -v apt &>/dev/null; then apt-cache policy 2>&1 | head -30; elif command -v zypper &>/dev/null; then zypper repos -p 2>&1; fi; echo "---"; dnf provides /usr/bin/containerd 2>/dev/null | head -10
```

## Remediation Steps

### Step 1: Identify conflicting repos

```bash
if command -v dnf &>/dev/null; then dnf repolist --all 2>&1 | grep -v "^$"; echo "---"; dnf check-update 2>&1 | grep -i "error\|conflict\|problem" | head -10; elif command -v apt-get &>/dev/null; then apt-get update 2>&1; apt-get -s upgrade 2>&1 | grep -i "conflict\|break\|held" | head -10; elif command -v zypper &>/dev/null; then zypper repos -d 2>&1; fi; echo "Repos identified"
```

Expected output: List of repositories and conflicts
On failure: continue

### Step 2: Disable problematic third-party repos temporarily

```bash
DISABLED_FILE="/tmp/sop035_disabled_repos.txt"; > "$DISABLED_FILE"; if command -v dnf &>/dev/null; then THIRD_PARTY=$(dnf repolist --enabled 2>/dev/null | grep -iv "baseos\|appstream\|base\|updates\|extras\|oracle\|rhui\|amzn" | awk '{print $1}' | grep -v "^repo"); for repo in $THIRD_PARTY; do dnf config-manager --set-disabled "$repo" 2>/dev/null && echo "$repo" >> "$DISABLED_FILE" && echo "Disabled: $repo"; done; elif command -v apt-get &>/dev/null; then find /etc/apt/sources.list.d/ -name "*.list" -not -name "*.disabled" | while read f; do if ! grep -qi "ubuntu\|debian\|canonical" "$f"; then mv "$f" "${f}.disabled" && echo "$f" >> "$DISABLED_FILE" && echo "Disabled: $f"; fi; done; fi; echo "Third-party repos disabled ($(wc -l < "$DISABLED_FILE") tracked)"
```

Expected output: List of disabled repos
On failure: continue

### Step 3: Attempt update with only base repos

```bash
if command -v dnf &>/dev/null; then dnf check-update 2>&1 | tail -5; echo "Check exit: ${PIPESTATUS[0]}"; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 && apt-get -s upgrade 2>&1 | tail -5; echo "Check exit: ${PIPESTATUS[0]}"; elif command -v zypper &>/dev/null; then zypper refresh 2>&1 && zypper list-updates 2>&1 | tail -5; echo "Check exit: ${PIPESTATUS[0]}"; fi
```

Expected output: Clean update check
On failure: continue

### Step 4: Verify dependency resolution is clean

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1; echo "DNF check exit: $?"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1; echo "APT check exit: $?"; elif command -v zypper &>/dev/null; then zypper verify 2>&1; echo "Zypper verify exit: $?"; fi
```

Expected output: Exit code 0
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check-update 2>&1 >/dev/null; RC=$?; [ $RC -eq 0 ] || [ $RC -eq 100 ] && echo "REPO CONFLICTS RESOLVED" || echo "STILL CONFLICTING: $RC"; elif command -v apt-get &>/dev/null; then if apt-get -s upgrade 2>&1 | grep -qiE "conflict|broken|held"; then echo "STILL CONFLICTING"; else echo "REPO CONFLICTS RESOLVED"; fi; fi
```

Expected: "REPO CONFLICTS RESOLVED"

## Rollback

```bash
DISABLED_FILE="/tmp/sop035_disabled_repos.txt"; if [ -f "$DISABLED_FILE" ]; then if command -v dnf &>/dev/null; then while read -r repo; do dnf config-manager --set-enabled "$repo" 2>/dev/null; done < "$DISABLED_FILE"; echo "Tracked repos re-enabled"; fi; if command -v apt-get &>/dev/null; then while read -r f; do mv "${f}.disabled" "$f" 2>/dev/null; done < "$DISABLED_FILE"; apt-get update 2>&1; echo "Tracked repos re-enabled"; fi; rm -f "$DISABLED_FILE"; else echo "No tracked repos file found"; fi
```

## Escalation

If conflicts cannot be resolved by priority alone:
- Use `dnf module` commands to switch conflicting module streams on RHEL 8/9
- Pin specific package versions from third-party repos: `dnf versionlock add <package>`
- Create exclude= directives in the third-party .repo file for conflicting base packages
- For Docker/containerd conflicts: use Docker's official repo and exclude containerd from base repos
- Consider using `dnf swap` to replace conflicting packages atomically
