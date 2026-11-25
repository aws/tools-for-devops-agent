# SOP-011: Resolve RHUI CDS Load Balancer Connectivity Issues

| Field | Value |
|-------|-------|
| ID | SOP-011 |
| Category | rhui_cds_connectivity |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 150 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- RHEL patching fails with "Cannot retrieve repository metadata (repomd.xml)"
- "Could not contact CDS load balancer" in yum/dnf output
- "SSL peer certificate was not OK" for RHUI endpoints
- RHUI client certificate expired errors
- "Error: Failed to download metadata for repo 'rhel-*-rhui-rpms'"
- "sslclientcert: /etc/pki/rhui/product/content-*.pem" errors in repo configuration
- HTTP 401/403 from RHUI content delivery servers
- "Peer's Certificate has expired" or "certificate verify failed"

## Root Cause

RHUI (Red Hat Update Infrastructure) connectivity fails when:

- RHUI client certificates expired — typically 2-year validity from instance launch; expired certs cannot authenticate to the RHUI content delivery network
- RHUI load balancer IPs changed and local DNS cache not refreshed (RHUI uses ELBs that can change IPs)
- Security groups blocking outbound HTTPS to RHUI endpoints (port 443 to regional RHUI infrastructure)
- RHUI configuration pointing to wrong region-specific endpoint after instance migration
- ELB health check fails for CDS (Content Delivery Server) nodes causing temporary 503 errors
- Instance was created from an AMI in a different region — RHUI certs are region-specific
- The `rhui-client` package is outdated and contains stale endpoint configurations

RHUI is the infrastructure AWS provides for RHEL pay-as-you-go instances to access Red Hat repositories without a separate Red Hat subscription. It uses mutual TLS with client certificates stored in /etc/pki/rhui/.

## Related Failure Patterns

- SOP-003 (Network Unreachable) — general network issues that also affect RHUI
- SOP-009 (GPG Key Issues) — RHUI repos have their own signing keys that can also expire

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is a RHEL pay-as-you-go (RHUI-connected) instance (not BYOS — Bring Your Own Subscription)
- Network access to AWS RHUI endpoints

## Diagnosis

Verify instance is RHUI-connected (not subscription-manager registered):

```bash
rpm -qa | grep rhui; subscription-manager status 2>&1 | head -5
```

Check certificate expiry:

```bash
for cert in /etc/pki/rhui/product/*.pem /etc/pki/rhui/content/*.pem; do echo "=== $cert ==="; openssl x509 -in "$cert" -noout -enddate 2>/dev/null; done
```

## Remediation Steps

### Step 1: Check RHUI client certificate validity

```bash
CERT=$(find /etc/pki/rhui -name "*.pem" -type f 2>/dev/null | head -1); if [ -n "$CERT" ]; then openssl x509 -in "$CERT" -noout -dates 2>/dev/null; echo "Cert: $CERT"; else echo "No RHUI cert found"; fi; echo "Cert check done"
```

Expected output: Certificate validity dates
On failure: continue

### Step 2: Test connectivity to RHUI endpoints

```bash
RHUI_HOST=$(grep baseurl /etc/yum.repos.d/redhat-rhui* 2>/dev/null | head -1 | sed 's|.*://||;s|/.*||'); if [ -n "$RHUI_HOST" ]; then curl -sf --connect-timeout 10 "https://${RHUI_HOST}" -o /dev/null && echo "RHUI reachable: $RHUI_HOST" || echo "RHUI unreachable: $RHUI_HOST"; else echo "No RHUI host found in repos"; fi
```

Expected output: "RHUI reachable" or connectivity error
On failure: continue

### Step 3: Reinstall RHUI client package to refresh certificates

```bash
RHUI_PKG=$(rpm -qa | grep -i rhui-client 2>/dev/null | head -1); if [ -n "$RHUI_PKG" ]; then dnf reinstall -y "$RHUI_PKG" 2>/dev/null || yum reinstall -y "$RHUI_PKG" 2>/dev/null; echo "RHUI client reinstalled"; else echo "RHUI client package not found"; fi
```

Expected output: "RHUI client reinstalled"
On failure: go to Step 4

### Step 4: Download and install latest RHUI client from AWS

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); [ -z "$REGION" ] && { echo "ERROR: region unknown from IMDS - aborting"; exit 1; }; BUCKET="https://s3.${REGION}.amazonaws.com/amazon-rhui3-client-config"; KEY=$(curl -sf --connect-timeout 5 --max-time 15 "${BUCKET}?list-type=2&prefix=rhel/rhui-client" 2>/dev/null | grep -oP '(?<=<Key>)rhel/rhui-client[^<]*\.rpm(?=</Key>)' | sort -V | tail -1); if [ -n "$KEY" ]; then URL="${BUCKET}/${KEY}"; echo "Resolved RHUI client from S3: $URL"; if yum install -y "$URL" || dnf install -y "$URL"; then echo "RHUI client updated from S3"; else echo "ERROR: RHUI client install from $URL failed - escalate"; exit 1; fi; else echo "S3 bucket not listable (anonymous ListBucket may be denied) - falling back to reinstalling the AWS RHUI client package from RHUI"; if yum install -y rh-amazon-rhui-client || dnf install -y rh-amazon-rhui-client; then echo "RHUI client reinstalled from RHUI"; else echo "ERROR: could not resolve the S3 object and rh-amazon-rhui-client install failed - escalate (fetch the region-specific rhui-client RPM manually)"; exit 1; fi; fi
```

Expected output: "RHUI client updated from S3" or "RHUI client reinstalled from RHUI"
On failure: abort

### Step 5: Clean and refresh repository metadata

```bash
dnf clean all 2>/dev/null || yum clean all 2>/dev/null; dnf makecache 2>/dev/null || yum makecache 2>/dev/null; echo "Repos refreshed"
```

Expected output: "Repos refreshed"
On failure: abort

## Validation

```bash
OUTPUT=$(dnf repolist 2>/dev/null || yum repolist 2>/dev/null); RC=$?; echo "$OUTPUT" | grep -i rhui | head -5; echo "RHUI_EXIT:$RC"
```

Expected: RHUI repository list with "RHUI_EXIT:0"

Note: capture the repolist exit code into `RC` before piping. Writing
`dnf repolist || yum repolist | grep ... | head` would (a) only filter the
`yum` fallback through grep due to `|` binding tighter than `||`, and (b) make
`$?` report `head`'s exit code rather than repolist's.

## Rollback

```bash
echo "No rollback required - RHUI client reinstall refreshes certificates safely"
```

## Escalation

If RHUI connectivity cannot be restored:
- Verify the instance is in a region that has RHUI infrastructure
- Check if the RHUI S3 bucket for the region exists: `aws s3 ls s3://amazon-rhui3-client-config/rhel/`
- For instances migrated between regions, the RHUI client package must be reinstalled from the target region's S3 bucket
- If the instance was converted from BYOS to PAYG, ensure the subscription-manager registration is removed first: `subscription-manager unregister`
- Contact AWS Support if the regional RHUI infrastructure appears down (rare but possible during maintenance)
