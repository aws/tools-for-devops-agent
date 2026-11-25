# SOP-013: Resolve SUSE Repository Refresh Issues During Patching

| Field | Value |
|-------|-------|
| ID | SOP-013 |
| Category | suse_repo_refresh |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | SLES 12, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "Error building the cache" on SLES instances
- "Problem retrieving the repository index file" for SUSE repos
- zypper refresh errors with timeout or authentication failures
- "Metadata transfer failed" or "Repository not found" in patch logs
- SUSEConnect registration errors blocking repo access
- "Repository is invalid" or "Valid metadata not found at specified URL"
- "System is not registered" when running zypper commands
- "ERROR: Registration server returned '401 - Unauthorized'"

## Root Cause

SUSE repository refresh failures caused by:

- SUSEConnect registration expired or invalid — SLES on AWS uses per-instance cloud registration that can expire or become invalid after instance stop/start
- SUSE RMT (Repository Mirroring Tool) server unreachable — the regional SUSE cloud infrastructure uses SMT/RMT servers hosted within AWS
- Repository credentials expired in /etc/zypp/credentials.d/ — credentials file contains tokens with limited validity
- Zypper cache corrupted after interrupted refresh (stale metadata in /var/cache/zypp/)
- AWS SUSE update infrastructure endpoints unreachable due to network or DNS issues
- Instance migrated between regions without re-registering with the target region's SUSE infrastructure
- `registercloudguest` service failed during boot, leaving registration incomplete

## Related Failure Patterns

- SOP-003 (Network Unreachable) — general connectivity issues affecting all repos including SUSE
- SOP-009 (GPG Key Issues) — SUSE repos also use GPG signing that can expire

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is a SUSE Linux Enterprise Server (SLES) system
- Network access to SUSE update infrastructure (smt-*.susecloud.net)

## Diagnosis

Check registration and module status:

```bash
SUSEConnect --status-text 2>&1; echo "---"; cat /etc/SUSEConnect 2>/dev/null; echo "---"; systemctl status guestregister.service 2>/dev/null | head -5
```

Check credential files:

```bash
ls -la /etc/zypp/credentials.d/ 2>/dev/null; cat /etc/zypp/credentials.d/SCCcredentials 2>/dev/null | head -2
```

## Remediation Steps

### Step 1: Check current registration status

```bash
SUSEConnect --status 2>&1 | head -20; echo "Registration check done"
```

Expected output: Registration status JSON
On failure: continue

### Step 2: Clean zypper cache

```bash
zypper clean -a; rm -rf /var/cache/zypp/* 2>/dev/null; echo "Zypper cache cleaned"
```

Expected output: "Zypper cache cleaned"
On failure: continue

### Step 3: Re-register with SUSE update infrastructure

```bash
if [ -f /etc/SUSEConnect ]; then SUSEConnect --cleanup 2>/dev/null; REGCODE=$(grep regcode /etc/SUSEConnect 2>/dev/null | cut -d: -f2 | tr -d ' '); if [ -n "$REGCODE" ]; then SUSEConnect -r "$REGCODE" 2>/dev/null; echo "Re-registration attempted"; else echo "No regcode found - skipping re-registration (leaving existing PAYG registration intact)"; fi; else echo "No SUSEConnect config"; fi
```

Expected output: "Re-registration attempted"
On failure: continue

### Step 4: Refresh repository metadata

```bash
zypper --non-interactive refresh -f 2>&1; echo "Refresh exit: $?"
```

Expected output: "Refresh exit: 0"
On failure: go to Step 5

### Step 5: Manually fix repository URLs for AWS SUSE infrastructure

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); registercloudguest --force-new 2>/dev/null || { [ -n "$REGION" ] && SUSEConnect --url "https://smt-${REGION}.susecloud.net" 2>/dev/null || { echo "ERROR: registercloudguest failed and region unknown from IMDS (cannot build the regional SMT URL) - aborting"; exit 1; }; }; zypper --non-interactive refresh; echo "Cloud registration fixed"
```

Expected output: "Cloud registration fixed"
On failure: abort

## Validation

```bash
zypper --non-interactive refresh && zypper lr -E 2>/dev/null | grep -c '^[[:space:]]*[0-9]' | awk '{print "Enabled repos: "$1}' && echo "SUSE REPOS OK"
```

Expected: "Enabled repos: N" followed by "SUSE REPOS OK"

## Rollback

```bash
echo "No rollback required - registration refresh is safe"
```

## Escalation

If registration cannot be restored:
- Verify the instance is in a region with SUSE cloud infrastructure
- Check if the `cloud-regionsrv-client` package is installed and current
- Verify `/etc/regionserverclnt.cfg` points to the correct region server
- For BYOS instances, ensure the registration code is valid via SUSE Customer Center
- Try force-registering: `registercloudguest --force-new --smt-fp <fingerprint>`
- Contact AWS Support if the regional SMT/RMT infrastructure appears unavailable
