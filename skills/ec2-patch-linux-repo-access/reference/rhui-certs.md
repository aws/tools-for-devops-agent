# RHUI client certificate / RHUI repo access (RHEL PAYG)

**Signatures:** "Cannot retrieve repository metadata (repomd.xml)" for `rhel-*-rhui-rpms`,
"Could not contact CDS load balancer", "SSL peer certificate was not OK", HTTP 401/403 from RHUI,
"Peer's Certificate has expired", `sslclientcert: /etc/pki/rhui/product/content-*.pem` errors,
and sometimes a misleading "GPG check FAILED" on RHUI repos.

RHUI is the AWS-provided update infrastructure for RHEL pay-as-you-go instances; it uses mutual TLS
with client certs in `/etc/pki/rhui/`. **Certs are region-specific (~2-year validity).**

## Diagnose
```bash
rpm -qa | grep rhui                                  # confirm RHUI (vs subscription-manager/BYOS)
for c in /etc/pki/rhui/product/*.pem /etc/pki/rhui/content/*.pem; do [ -f "$c" ] && echo "$c" && openssl x509 -in "$c" -noout -dates; done
```

## Fix: reinstall the RHUI client from the INSTANCE'S OWN region
```bash
RHUI_PKG=$(rpm -qa | grep -i rhui-client | head -1)
dnf reinstall -y "$RHUI_PKG" 2>/dev/null || yum reinstall -y "$RHUI_PKG" 2>/dev/null
# if the package is gone/outdated, pull the current one from the region's S3 bucket:
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region || echo us-east-1)
dnf install -y https://s3.${REGION}.amazonaws.com/amazon-rhui3-client-config/rhel/rhui-client-*.rpm 2>/dev/null
dnf clean all; dnf makecache
```

## Verify
```bash
dnf repolist 2>&1 | grep -i rhui; RC=$?; echo "repolist_exit=$RC"
```

## Escalation
- Instance migrated/copied between regions → the RHUI cert is for the wrong region; reinstall from the CURRENT region's S3 bucket (not the origin's).
- Converted BYOS→PAYG → remove the stale subscription-manager registration first (`subscription-manager unregister`).
- Regional RHUI infra down (rare) → AWS Support.
- **Do not** work around by setting `sslverify=false` permanently.
