# SOP-047: Resolve Oracle Linux Yum Server / ULN Repository Access Issues

| Field | Value |
|-------|-------|
| ID | SOP-047 |
| Category | oracle_linux_repo_access |
| Severity | High |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Oracle Linux 8, Oracle Linux 9 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Cannot retrieve metalink for repository: ol8_baseos_latest" 
- "Error: Failed to download metadata for repo 'ol8_UEK'"
- "Repository 'ol8_appstream' is invalid" or "repomd.xml not found"
- Connection timeout to yum.oracle.com or public-yum.oracle.com
- ULN (Unbreakable Linux Network) subscription errors
- "Cannot find a valid baseurl for repo: ol8_baseos_latest"
- Oracle Linux release file missing or corrupted
- "Error: GPG check FAILED" for Oracle Linux packages

## Root Cause

Oracle Linux repository access failures when:

- Oracle Linux yum server URLs changed or DNS not resolving yum.oracle.com
- oraclelinux-release package outdated with old repo URLs
- ULN subscription expired or credentials invalid (for ULN-subscribed instances)
- Instance in private subnet without access to Oracle's public yum servers
- oracle-epel-release or oraclelinux-developer-release providing conflicting repos
- GPG keys not imported for Oracle Linux signing key rotation
- /etc/yum.repos.d/ contains stale .repo files from a previous Oracle Linux version

## Related Failure Patterns

- SOP-003 (Network Unreachable) — connectivity to yum.oracle.com
- SOP-028 (Stale Metadata Cache) — stale Oracle Linux metadata
- SOP-037 (Oracle Kernel Conflict) — repo issues affect kernel stream availability

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is running Oracle Linux 8 or 9

## Diagnosis

Check Oracle Linux repo configuration and connectivity:

```bash
cat /etc/oracle-release 2>/dev/null; echo "---"; ls /etc/yum.repos.d/oracle-linux*.repo 2>/dev/null; echo "---"; dnf repolist --all 2>&1 | head -20; echo "---"; curl -sf --connect-timeout 5 https://yum.oracle.com/ >/dev/null && echo "yum.oracle.com: reachable" || echo "yum.oracle.com: UNREACHABLE"
```

## Remediation Steps

### Step 1: Verify Oracle Linux release and repo packages

```bash
rpm -qa | grep -E "oraclelinux-release|oracle-epel" | sort; echo "---"; cat /etc/oracle-release; echo "---"; OL_VER=$(rpm -q --qf '%{VERSION}' oraclelinux-release 2>/dev/null | cut -d. -f1); echo "Oracle Linux major version: $OL_VER"
```

Expected output: Release package info and version
On failure: continue

### Step 2: Test connectivity to Oracle yum servers

```bash
curl -sf --connect-timeout 10 https://yum.oracle.com/repo/OracleLinux/OL$(rpm -q --qf '%{VERSION}' oraclelinux-release 2>/dev/null | cut -d. -f1)/baseos/latest/x86_64/repodata/repomd.xml >/dev/null && echo "Oracle repo: REACHABLE" || echo "Oracle repo: UNREACHABLE"
```

Expected output: "Oracle repo: REACHABLE"
On failure: continue (may need proxy or different URL)

### Step 3: Reinstall Oracle Linux release package to fix repo configs

```bash
OL_VER=$(rpm -q --qf '%{VERSION}' oraclelinux-release 2>/dev/null | cut -d. -f1); if [ -n "$OL_VER" ]; then dnf reinstall -y oraclelinux-release-el${OL_VER} 2>&1 || dnf reinstall -y oraclelinux-release 2>&1; echo "Release package reinstalled"; else echo "Cannot determine OL version"; fi
```

Expected output: "Release package reinstalled"
On failure: continue

### Step 4: Import Oracle Linux GPG keys

```bash
rpm --import https://yum.oracle.com/RPM-GPG-KEY-oracle-ol8 2>/dev/null; rpm --import https://yum.oracle.com/RPM-GPG-KEY-oracle-ol9 2>/dev/null; rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-oracle* 2>/dev/null; echo "GPG keys imported"
```

Expected output: "GPG keys imported"
On failure: continue

### Step 5: Clean and rebuild metadata cache

```bash
dnf clean all 2>&1; rm -rf /var/cache/dnf/* 2>/dev/null; dnf makecache 2>&1 | tail -5; echo "Cache rebuild exit: $?"
```

Expected output: "Cache rebuild exit: 0"
On failure: abort

### Step 6: Verify repos are functional

```bash
dnf repolist 2>&1; echo "---"; dnf check-update -q 2>&1 | wc -l | awk '{print "Available updates: "$1}'; echo "REPO ACCESS OK"
```

Expected output: "REPO ACCESS OK"
On failure: abort

## Validation

```bash
dnf repolist 2>&1 | grep -c "ol" | awk '{print "Oracle repos enabled: "$1}'; dnf makecache 2>&1 >/dev/null && echo "ORACLE LINUX REPOS OK" || echo "REPO ISSUES REMAIN"
```

Expected: "ORACLE LINUX REPOS OK"

## Rollback

```bash
echo "Repo config reinstall and GPG import are non-destructive - no rollback needed"
```

## Escalation

If Oracle Linux repos remain inaccessible:
- Check if instance needs proxy to reach yum.oracle.com (private subnet)
- Verify DNS resolves yum.oracle.com: `nslookup yum.oracle.com`
- For ULN subscribers: re-register with `uln-channel --list` and verify subscription
- Download and manually install latest oraclelinux-release RPM from Oracle's website
- If public yum is unreachable, consider mirroring Oracle repos internally or using a yum proxy
- Check if WAF or firewall is blocking yum.oracle.com domain
