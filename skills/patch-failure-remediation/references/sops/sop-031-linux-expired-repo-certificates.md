# SOP-031: Resolve Expired Repository Certificates/Subscriptions

| Field | Value |
|-------|-------|
| ID | SOP-031 |
| Category | expired_repo_certificate |
| Severity | High |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, SLES 12, SLES 15, Ubuntu 20.04, Ubuntu 22.04 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "SSL certificate problem: certificate has expired" during repo access
- "Peer's Certificate has expired" in YUM/DNF output
- "RHSM: Red Hat Subscription Manager reports no valid subscriptions"
- "This system is not registered with an entitlement server"
- "Repository does not have a valid format" due to expired certificate authentication
- SLES "System credentials not found" or "Registration expired"
- Ubuntu "Certificate verification failed: The certificate is NOT trusted" for PPA repos
- "curl: (60) SSL certificate problem: unable to get local issuer certificate"

## Root Cause

Repository certificate/subscription expiration caused by:

- RHUI client certificate expired (stored in /etc/pki/rhui/) — these have a limited validity period
- Red Hat subscription-manager registration lapsed
- SUSE cloud registration credentials expired in /etc/zypp/credentials.d/
- Oracle Linux yum server certificates expired
- System CA trust bundle outdated, rejecting valid new certificates
- Instance stopped for extended period causing cloud registration to lapse
- Third-party repo SSL certificates expired
- Let's Encrypt root CA changeover breaking older ca-certificates packages

## Related Failure Patterns

- SOP-011 (RHUI CDS) — RHUI cert expiry is a common subset
- SOP-013 (SUSE Repo Refresh) — SUSE credential expiry is covered here
- SOP-003 (Network Unreachable) — SSL failures can appear as connectivity issues

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Network path to certificate/registration endpoints is available

## Diagnosis

Check certificate expiry dates:

```bash
for cert in /etc/pki/rhui/product/*.pem /etc/pki/rhui/content/*.pem /etc/pki/entitlement/*.pem; do [ -f "$cert" ] && echo "$cert: $(openssl x509 -enddate -noout -in $cert 2>/dev/null)"; done 2>/dev/null; echo "---"; openssl s_client -connect cdn.redhat.com:443 -servername cdn.redhat.com </dev/null 2>/dev/null | openssl x509 -noout -dates 2>/dev/null; echo "---"; cat /etc/zypp/credentials.d/SCCcredentials 2>/dev/null
```

## Remediation Steps

### Step 1: Identify the certificate/subscription issue

```bash
if [ -d /etc/pki/rhui ]; then echo "RHUI system"; for f in /etc/pki/rhui/product/*.pem /etc/pki/rhui/content/*.pem; do [ -f "$f" ] && openssl x509 -enddate -noout -in "$f" 2>/dev/null && echo "  $f"; done; elif command -v subscription-manager &>/dev/null; then subscription-manager status 2>&1; elif [ -f /etc/SUSEConnect ]; then SUSEConnect --status-text 2>&1; else echo "Checking CA trust"; fi; echo "Cert check done"
```

Expected output: Certificate expiration information
On failure: continue

### Step 2: Update CA certificates bundle

```bash
if command -v update-ca-trust &>/dev/null; then update-ca-trust force-enable; update-ca-trust extract; echo "CA trust updated (RPM)"; elif command -v update-ca-certificates &>/dev/null; then update-ca-certificates 2>&1; echo "CA trust updated (DEB/SUSE)"; fi
```

Expected output: "CA trust updated"
On failure: continue

### Step 3: Reinstall RHUI client certificates (RHEL on AWS)

```bash
if [ -d /etc/pki/rhui ]; then RHUI_PKG=$(rpm -qa | grep -i rhui); if [ -n "$RHUI_PKG" ]; then yum reinstall -y $RHUI_PKG 2>&1 || dnf reinstall -y $RHUI_PKG 2>&1; echo "RHUI client reinstalled"; else echo "No RHUI package found"; fi; else echo "Not a RHUI system"; fi
```

Expected output: "RHUI client reinstalled" or "Not a RHUI system"
On failure: continue

### Step 4: Re-register subscription (RHEL subscription-manager)

```bash
if command -v subscription-manager &>/dev/null; then subscription-manager refresh 2>&1; echo "Subscription refreshed"; else echo "No subscription-manager"; fi
```

Expected output: "Subscription refreshed" or "No subscription-manager"
On failure: continue

### Step 5: Re-register SUSE cloud credentials

```bash
if [ -f /etc/SUSEConnect ]; then registercloudguest --force-new 2>&1 || (SUSEConnect --cleanup && SUSEConnect 2>&1); echo "SUSE registration refreshed"; else echo "Not SUSE"; fi
```

Expected output: "SUSE registration refreshed" or "Not SUSE"
On failure: continue

### Step 6: Verify repository access

```bash
if command -v dnf &>/dev/null; then dnf repolist 2>&1 && echo "REPO ACCESS OK"; elif command -v yum &>/dev/null; then yum repolist 2>&1 && echo "REPO ACCESS OK"; elif command -v zypper &>/dev/null; then zypper refresh 2>&1 && echo "REPO ACCESS OK"; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 && echo "REPO ACCESS OK"; fi
```

Expected output: "REPO ACCESS OK"
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf makecache 2>&1 && echo "CERTS VALID"; elif command -v zypper &>/dev/null; then zypper refresh 2>&1 && echo "CERTS VALID"; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 && echo "CERTS VALID"; fi
```

Expected: "CERTS VALID"

## Rollback

```bash
echo "Certificate updates and registration refresh are non-destructive - no rollback needed"
```

## Escalation

If certificates cannot be renewed:
- For RHUI: download the latest RHUI config RPM from the AWS RHEL documentation
- For Oracle Linux: `yum install -y oraclelinux-release-el8` to refresh repo configs
- For SLES: verify cloud-regionsrv-client is current and /etc/regionserverclnt.cfg is correct
- For subscription-manager: may need new activation key or org credentials
- Check if instance was cloned/copied — subscriptions may be tied to the original instance identity
