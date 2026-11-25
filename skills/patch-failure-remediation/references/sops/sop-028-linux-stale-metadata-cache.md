# SOP-028: Resolve Stale YUM/DNF Metadata Cache Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-028 |
| Category | stale_metadata_cache |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "Metadata file does not match checksum"
- "Cannot retrieve metalink for repository" errors
- "repomd.xml does not match metalink" during patching
- "Failed to synchronize cache for repo" in DNF output
- "Error: Failed to download metadata for repo" followed by "Cannot prepare internal mirrorlist"
- Stale repodata causes "package not found" for packages that should exist

## Root Cause

Stale metadata cache occurs when:

- Local metadata cache expires but cannot be refreshed due to transient network issues
- Repository mirror synced while metadata was being downloaded (partial/mismatched repomd.xml)
- /var/cache/yum or /var/cache/dnf contains corrupt or half-written metadata files
- Metalink endpoints return different mirror than cached data was fetched from
- Time skew on instance causes cache validity checks to fail
- Oracle Linux yum-cron or dnf-automatic corrupted cache during background refresh

## Related Failure Patterns

- SOP-003 (Network Unreachable) — network issues are a common cause of partial metadata downloads
- SOP-011 (RHUI CDS) — RHUI metadata refresh failures are a subset of this issue

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Network connectivity to repositories is functional

## Diagnosis

Check cache age and integrity:

```bash
ls -la /var/cache/dnf/*/repodata/ 2>/dev/null || ls -la /var/cache/yum/*/base/ 2>/dev/null; echo "---"; date; echo "---"; dnf repolist -v 2>&1 | grep -E "Expire|Last" | head -10
```

## Remediation Steps

### Step 1: Check current cache status and age

```bash
if command -v dnf &>/dev/null; then dnf repolist -v 2>&1 | grep -E "Repo-expire|Repo-filename" | head -10; elif command -v yum &>/dev/null; then yum repolist -v 2>&1 | grep -E "Repo-expire|Repo-filename" | head -10; fi; echo "Cache status checked"
```

Expected output: Repository expiration information
On failure: continue

### Step 2: Clean all metadata cache

```bash
if command -v dnf &>/dev/null; then dnf clean all 2>&1; rm -rf /var/cache/dnf/* 2>/dev/null; elif command -v yum &>/dev/null; then yum clean all 2>&1; rm -rf /var/cache/yum/* 2>/dev/null; fi; echo "Cache cleaned"
```

Expected output: "Cache cleaned"
On failure: continue

### Step 3: Sync system clock to prevent time-skew issues

```bash
if command -v chronyc &>/dev/null; then chronyc makestep 2>&1; elif command -v ntpdate &>/dev/null; then ntpdate -u 169.254.169.123 2>&1; fi; date; echo "Clock synced"
```

Expected output: Current date and "Clock synced"
On failure: continue

### Step 4: Rebuild metadata cache

```bash
if command -v dnf &>/dev/null; then dnf makecache 2>&1; echo "DNF cache exit: $?"; elif command -v yum &>/dev/null; then yum makecache 2>&1; echo "YUM cache exit: $?"; fi
```

Expected output: "DNF cache exit: 0" or "YUM cache exit: 0"
On failure: abort

### Step 5: Verify package listing works

```bash
if command -v dnf &>/dev/null; then dnf check-update -q 2>&1 | wc -l | awk '{print "Available updates: "$1}'; elif command -v yum &>/dev/null; then yum check-update -q 2>&1 | wc -l | awk '{print "Available updates: "$1}'; fi
```

Expected output: "Available updates: N"
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf repolist 2>&1 && echo "METADATA OK"; elif command -v yum &>/dev/null; then yum repolist 2>&1 && echo "METADATA OK"; fi
```

Expected: Repository list with package counts followed by "METADATA OK"

## Rollback

```bash
echo "No rollback needed - metadata cache rebuild is safe and non-destructive"
```

## Escalation

If metadata cannot be rebuilt:
- Verify all configured repos are reachable: `dnf repolist -v 2>&1 | grep -E "Repo-baseurl|Repo-metalink"`
- Disable broken repos temporarily: `dnf config-manager --set-disabled <repo-name>`
- Check for expired RHUI or Oracle Linux certificates in /etc/pki/
- For Oracle Linux: verify /etc/yum.repos.d/oracle-linux-ol*.repo URLs are correct for the region
