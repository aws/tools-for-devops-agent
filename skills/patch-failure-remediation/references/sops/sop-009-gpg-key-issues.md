# SOP-009: Resolve GPG Key Issues Blocking Package Verification

| Field | Value |
|-------|-------|
| ID | SOP-009 |
| Category | gpg_key_missing |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, CentOS 7, Ubuntu 20.04, Ubuntu 22.04 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "GPG key retrieval failed" or "Public key not installed"
- "NOKEY" errors during package verification
- "The GPG keys listed for the repository are not correct"
- APT "NO_PUBKEY" errors on Ubuntu/Debian systems
- "warning: /var/cache/dnf/.../packages/X.rpm: Header V4 RSA/SHA256 Signature, key ID ...: NOKEY"
- "GPG check FAILED" causing transaction abortion
- "Couldn't open file /etc/pki/rpm-gpg/RPM-GPG-KEY-*"

## Root Cause

GPG key issues occur when:

- Repository GPG keys expired or were rotated by the vendor (Amazon, Red Hat, EPEL maintainers)
- GPG keyring corrupted or key files deleted from /etc/pki/rpm-gpg/ during cleanup operations
- New repository added (e.g., EPEL, third-party) without importing its signing key
- gpgcheck=1 enabled in repo config but key not in RPM keyring (common after reinstalling repo config packages)
- Network issues preventing key download from keyserver during automated import
- Ubuntu apt-key deprecation — keys in /etc/apt/trusted.gpg.d/ not properly formatted for newer apt versions
- Key rotation by Amazon (happens periodically for AL2023 repos)

## Related Failure Patterns

- SOP-003 (Network Unreachable) — if the key retrieval URL is unreachable, the error can look like a GPG issue
- SOP-011 (RHUI CDS) — RHUI client certificate issues can manifest as GPG failures

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Network access to repository endpoints or key servers

## Diagnosis

List all keys currently in the RPM keyring:

```bash
rpm -qa gpg-pubkey* --qf '%{NAME}-%{VERSION}-%{RELEASE}\t%{SUMMARY}\n'
```

Check which repo is failing:

```bash
yum repolist -v 2>&1 | grep -B2 -A2 -i "gpg\|error" | head -20
```

## Remediation Steps

### Step 1: Identify which repository has key issues

```bash
yum repolist -v 2>&1 | grep -i "gpg\|key\|error" || dnf repolist -v 2>&1 | grep -i "gpg\|key\|error" || apt-key list 2>&1 | grep -i "expired"; echo "Key diagnosis done"
```

Expected output: Repository/key information
On failure: continue

### Step 2: Import Amazon Linux / RHEL GPG keys

```bash
for KEY in /etc/pki/rpm-gpg/RPM-GPG-KEY-*; do rpm --import "$KEY" 2>/dev/null; done; echo "RPM keys imported: $(rpm -qa gpg-pubkey* | wc -l) keys in keyring"
```

Expected output: "RPM keys imported: N keys in keyring"
On failure: continue

### Step 3: Fix Ubuntu/Debian key issues (if applicable)

```bash
if command -v apt-key &>/dev/null; then KEYS=$(apt-get update 2>&1 | grep NO_PUBKEY | awk '{print $NF}' | sort -u | tr '\n' ' '); if [ -n "${KEYS// /}" ]; then timeout 30 apt-key adv --keyserver keyserver.ubuntu.com --recv-keys $KEYS 2>/dev/null; apt-get update 2>/dev/null; echo "APT keys fixed"; else echo "No NO_PUBKEY keys reported - nothing to import"; fi; else echo "Not APT-based"; fi
```

Expected output: "APT keys fixed", "No NO_PUBKEY keys reported - nothing to import", or "Not APT-based"
On failure: continue

Note: only invoke `apt-key adv --recv-keys` when NO_PUBKEY keys were actually reported (an empty key list would otherwise import nothing or hang), and the keyserver fetch is bounded with `timeout 30`. `apt-key` is deprecated and modern apt (Debian 11+/Ubuntu 22.04+) may ignore keys added this way; the durable fix is to install the key as a de-armored file under `/etc/apt/trusted.gpg.d/` (or reference it via `signed-by=` in the repo's `.list`/`.sources` entry).

### Step 4: Clean and refresh repository metadata

```bash
yum clean metadata 2>/dev/null; dnf clean metadata 2>/dev/null; yum makecache 2>/dev/null || dnf makecache 2>/dev/null || apt-get update 2>/dev/null; echo "Metadata refreshed"
```

Expected output: "Metadata refreshed"
On failure: abort

### Step 5: Verify package verification works

```bash
if command -v dnf &>/dev/null; then OUTPUT=$(dnf check-update 2>&1); RC=$?; elif command -v yum &>/dev/null; then OUTPUT=$(yum check-update 2>&1); RC=$?; elif command -v apt-get &>/dev/null; then OUTPUT=$(apt-get update 2>&1); RC=$?; else OUTPUT=""; RC=1; fi; echo "$OUTPUT" | grep -i "gpg\|key\|error" | head -5; [ $RC -le 100 ] && echo "GPG verification OK" || echo "GPG issues remain"
```

Expected output: "GPG verification OK"
On failure: abort

Note: `yum`/`dnf check-update` return exit code 100 when updates are available — a success case here — so we accept `RC <= 100`. `apt-get update` returns 0 on success. The explicit `command -v` detection avoids running `yum` on Debian/Ubuntu (where it is absent and would return 127, a false "GPG issues remain").

## Validation

```bash
yum makecache 2>/dev/null || dnf makecache 2>/dev/null || apt-get update 2>/dev/null; echo "REPO_EXIT:$?"
```

Expected: "REPO_EXIT:0"

## Rollback

```bash
echo "No rollback required - GPG key imports are additive and safe"
```

## Escalation

If the correct GPG key cannot be found or imported:
- The repository vendor may have rotated keys without updating the rpm-gpg package
- As a temporary workaround (not recommended for production), set `gpgcheck=0` in the specific repo file, patch, then re-enable
- For Amazon Linux repos, reinstall the `system-release` package which contains the current GPG keys
- Contact the third-party repo maintainer if their key has expired
