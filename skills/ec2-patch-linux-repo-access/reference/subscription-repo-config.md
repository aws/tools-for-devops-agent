# Subscription & repo-config recovery (subscription-manager, SUSE, Oracle Linux)

**Signatures:** "not registered with an entitlement server", "no valid subscriptions",
SUSE "System credentials not found"/"Registration expired", Oracle "Cannot retrieve metalink for
repository ol8_baseos_latest" / "Cannot find a valid baseurl", stale `.repo` files after a version change.

## RHEL BYOS (subscription-manager)
```bash
subscription-manager status 2>&1
subscription-manager refresh 2>&1
# if registration is lapsed/broken (e.g. cloned instance identity):
# subscription-manager register --activationkey=<key> --org=<org>   # needs org creds
subscription-manager repos --list-enabled 2>&1 | head
dnf clean all; dnf makecache
```

## SLES (SUSE cloud registration)
```bash
[ -f /etc/SUSEConnect ] && (registercloudguest --force-new 2>&1 || { SUSEConnect --cleanup; SUSEConnect; })
zypper refresh 2>&1 && echo "SUSE repos OK"
```

## Oracle Linux (yum server / ULN)
```bash
OL_VER=$(rpm -q --qf '%{VERSION}' oraclelinux-release 2>/dev/null | cut -d. -f1)
curl -sf --connect-timeout 10 https://yum.oracle.com/ >/dev/null && echo reachable || echo UNREACHABLE
dnf reinstall -y "oraclelinux-release-el${OL_VER}" 2>&1 || dnf reinstall -y oraclelinux-release 2>&1
rpm --import https://yum.oracle.com/RPM-GPG-KEY-oracle-ol${OL_VER} 2>/dev/null || rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-oracle* 2>/dev/null
dnf clean all; rm -rf /var/cache/dnf/*; dnf makecache
```

## Verify
```bash
dnf repolist 2>&1 && dnf makecache 2>&1 >/dev/null && echo "REPO ACCESS OK"   # or zypper refresh
```

## Escalation
- Private subnet with no path to yum.oracle.com / SCC / CDN → needs a proxy or internal mirror.
- subscription tied to original instance identity (cloned host) → re-register, don't just refresh.
- Oracle ULN subscribers → `uln-channel --list` and verify subscription.
