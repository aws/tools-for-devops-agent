# GPG keys & TLS / CA-bundle recovery

**Signatures:** "NOKEY", "NO_PUBKEY", "The GPG keys listed for the repository are not correct",
"GPG check FAILED", "Header V4 RSA/SHA256 Signature, key ID ...: NOKEY", "SSL certificate problem:
certificate has expired", "unable to get local issuer certificate", "certificate verify failed".

**First rule out a wrong clock and (on RHUI) an expired client cert** — both surface as cert/GPG errors.
`date`; check RHUI cert enddate (see rhui-certs.md) before chasing signing keys.

## GPG keys (RPM)
```bash
rpm -qa gpg-pubkey* --qf '%{NAME}-%{VERSION}\t%{SUMMARY}\n'
for K in /etc/pki/rpm-gpg/RPM-GPG-KEY-*; do rpm --import "$K" 2>/dev/null; done
# Amazon Linux key rotation: reinstalling system-release restores current keys
dnf reinstall -y system-release 2>/dev/null || true
dnf clean metadata; dnf makecache
```

## GPG keys (APT)
```bash
MISSING=$(apt-get update 2>&1 | grep NO_PUBKEY | awk '{print $NF}' | sort -u)
[ -n "$MISSING" ] && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys $MISSING 2>/dev/null
apt-get update
```

## TLS / CA bundle (stale local trust rejecting valid certs)
```bash
command -v update-ca-trust >/dev/null && { update-ca-trust force-enable; update-ca-trust extract; }        # RPM
command -v update-ca-certificates >/dev/null && update-ca-certificates 2>&1                                  # DEB/SUSE
```

## Verify
```bash
dnf makecache 2>&1 | grep -iE 'gpg|ssl|error' || echo "no gpg/ssl errors"; echo "exit=$?"
```

## Escalation
- Vendor rotated a signing key without shipping it in the rpm-gpg package → obtain the current key from the vendor; temporary scoped `gpgcheck=0` only, then re-enable.
- Genuinely expired *server* cert (not local CA) → vendor/endpoint issue, not fixable on the host.
