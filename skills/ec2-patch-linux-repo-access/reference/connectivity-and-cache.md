# Proxy / stale metadata cache / time skew

**Signatures:** "Cannot retrieve metalink for repository", "Failed to download metadata for repo",
"Could not resolve host", connection timeouts to mirrors, repo works from one host but not another
behind a proxy, "repomd.xml ... does not match" (stale cache), cert/metadata errors that are really
a wrong clock.

## Time skew (do this first — a wrong clock fails cert & metadata-signature validation)
```bash
date; timedatectl 2>/dev/null | grep -iE 'synchron|time'
# resync:
timedatectl set-ntp true 2>/dev/null; chronyc makestep 2>/dev/null || (systemctl restart chronyd 2>/dev/null; systemctl restart systemd-timesyncd 2>/dev/null)
date
```

## Proxy misconfiguration
```bash
# check configured proxy vs what actually works
grep -R proxy /etc/dnf/dnf.conf /etc/yum.conf /etc/apt/apt.conf.d/ 2>/dev/null
env | grep -i proxy
# a stale/incorrect proxy line in dnf.conf/apt proxy config blocks all metadata fetch — correct or remove it
```

## Stale metadata cache
```bash
dnf clean all 2>/dev/null || yum clean all 2>/dev/null; rm -rf /var/cache/dnf/* /var/cache/yum/* 2>/dev/null
dnf makecache 2>/dev/null || yum makecache 2>/dev/null || apt-get update
```

## Verify
```bash
dnf makecache 2>&1 >/dev/null && echo "REPO ACCESS OK"   # or apt-get update / zypper refresh
```

## Escalation
- Host in a private subnet with no NAT/endpoint path to the mirrors → needs a proxy, NAT, or internal mirror (network design, not a host fix).
- DNS not resolving the mirror (`nslookup <mirror>`) → fix resolver/VPC DNS.
- Recurring skew → check the instance's NTP source reachability and the chrony/timesyncd config.
