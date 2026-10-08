---
name: ec2-patch-linux-repo-access
description: >-
  Use this skill when a Linux EC2 instance's patching is blocked by a repository
  access or authentication failure — the package database is fine but the instance
  cannot reach, authenticate to, or validate its repositories: RHUI
  client-certificate expiry, lapsed subscription-manager/SUSE registration, Oracle
  Linux yum/ULN access, expired repo TLS certificates, rotated or missing GPG keys,
  proxy misconfiguration, stale metadata, or NTP/time-skew. Use it when a patch run
  fails with "Failed to download metadata for repo", "Cannot retrieve repository
  metadata (repomd.xml)", "SSL certificate problem: certificate has expired",
  "NOKEY"/"NO_PUBKEY", "GPG check FAILED", "not registered with an entitlement
  server", or RHUI/ULN errors — even when the user only says the repos are
  unreachable. The fix depends on the auth mechanism: a RHUI cert is
  region-specific and reinstalled from a regional S3 bucket, and a "GPG failure" is
  often really an expired RHUI client cert. Apply it to diagnose and recover it.
license: Apache-2.0
metadata:
  version: "1.0.0"
  author: "sulbri"
  aws-devops-agent-skills.agent-types: "Chat tasks, Incident RCA"
  aws-devops-agent-skills.aws-services: "Amazon EC2, AWS Systems Manager, AWS Systems Manager Patch Manager"
  aws-devops-agent-skills.technical-domains: "Linux, Patching"
  domains: "EC2, SSM, Patch Manager, RHUI, yum, dnf, apt, zypper, GPG, TLS"
  platforms: "Linux"
  supported-os: "Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, CentOS 7, SLES 12, SLES 15, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04"
  operation-type: "read-and-mutate"
---

# Recover Linux repository access blocking patching

## When this applies
A yum/dnf/apt/zypper patch operation fails because the instance cannot reach,
authenticate to, or validate its repositories (metadata download, TLS cert, GPG,
subscription/RHUI). The package database itself is intact and the instance is
Online in SSM. If the failure is a corrupt package DB or a dependency conflict,
that is a different skill.

## The key insight: identify the access fault — the symptoms overlap and mislead
A single surface error ("metadata download failed", "GPG check FAILED", "SSL
certificate has expired") can have several different root causes, and the fix
differs by auth mechanism:
- **RHUI client cert expired** (RHEL PAYG): certs in `/etc/pki/rhui/` are
  **region-specific** (~2-year validity). Reinstall the `rhui-client` package
  **from the instance's region S3 bucket** — a cert from another region will not
  authenticate. A "GPG check FAILED" on RHUI repos is frequently really this.
- **subscription-manager / SUSE registration lapsed** (BYOS RHEL / SLES): refresh
  the entitlement (`subscription-manager refresh`) or SUSE cloud registration.
- **Oracle Linux yum/ULN access**: reinstall `oraclelinux-release-elN` to refresh
  repo configs + import the OL GPG keys.
- **Expired repo TLS cert / stale CA bundle**: `update-ca-trust` / `update-ca-certificates`.
- **Rotated/missing GPG key**: import the current key (reinstall `system-release` on AL).
- **Proxy misconfiguration / stale metadata / time skew**: fix the proxy, `clean all`+`makecache`, or correct NTP (a wrong clock fails cert/metadata validation).

## Diagnosis first
- [ ] Step 1: Classify the access fault before changing anything:
  ```bash
  cat /etc/os-release | grep -E '^(ID|VERSION_ID)='
  ls -la /etc/pki/rhui 2>/dev/null && for c in /etc/pki/rhui/product/*.pem /etc/pki/rhui/content/*.pem; do [ -f "$c" ] && openssl x509 -enddate -noout -in "$c"; done
  command -v subscription-manager >/dev/null && subscription-manager status 2>&1 | head
  [ -f /etc/oracle-release ] && cat /etc/oracle-release
  date; timedatectl 2>/dev/null | grep -i 'synchron\|time'   # clock/skew
  dnf repolist -v 2>&1 | grep -iE 'gpg|error|ssl|metalink|repomd' | head
  ```
- [ ] Step 2: Route to the fault (load the matching reference for exact commands):
  - RHUI cert / RHUI repo failure → read [rhui certs](reference/rhui-certs.md).
  - subscription/SUSE/Oracle ULN or repo config → read [subscription and repo config](reference/subscription-repo-config.md).
  - GPG key / TLS cert / CA bundle → read [gpg and tls](reference/gpg-and-tls.md).
  - proxy / stale metadata / time skew → read [connectivity and cache](reference/connectivity-and-cache.md).

## Ordered recovery (fix the cause, then refresh)
- [ ] Step 3: **Correct the clock first if skewed** — a wrong system time fails TLS cert and metadata-signature validation and makes every other symptom worse.
- [ ] Step 4: **Restore the right authentication** for the mechanism in use (region-correct RHUI client reinstall / subscription refresh / OL release reinstall), and import any rotated GPG keys.
- [ ] Step 5: **Update the CA trust bundle** if an "SSL certificate problem/expired" points at a stale local CA store rather than a genuinely expired server cert.
- [ ] Step 6: **Clean and rebuild metadata** (`dnf clean all` + `makecache`, `apt-get update`, `zypper refresh`) — only after the auth/cert fix, or you just re-cache the failure.
- [ ] Step 7: **Verify** repolist/makecache succeeds with no gpg/ssl/metadata errors.

## Validation (check your own work before reporting success)
- [ ] The specific access fault was identified (not just "repo error") and the mechanism-correct fix applied.
- [ ] For RHUI: the reinstalled client came from the **instance's own region** S3 bucket; cert enddate is now in the future.
- [ ] `dnf makecache` / `apt-get update` / `zypper refresh` completes with exit 0 and no `gpg`/`ssl`/`repomd`/`metalink` errors.
- [ ] The originally failing patch scan re-run no longer errors on repository access.
If any check fails, re-diagnose the mechanism rather than disabling `gpgcheck` or `sslverify` to force it through.

## Gotchas
- **RHUI certs are region-specific.** An instance launched from an AMI copied to another region has the wrong RHUI cert — reinstall `rhui-client` from the **current** region's S3 bucket, not the origin's.
- **A "GPG check FAILED" on RHUI repos is often an expired RHUI client cert**, not a missing signing key — check the RHUI cert enddate before chasing GPG keys.
- **Do not permanently set `gpgcheck=0` or `sslverify=false` to force patching** — that disables integrity/authenticity checks. Use it only as a temporary, scoped workaround and re-enable immediately.
- **A wrong system clock masquerades as an expired-certificate error** — check `date`/`timedatectl` before concluding a cert is expired.
- **`dnf clean all` + `makecache` without fixing the auth/cert cause just re-downloads the same failure** — fix the cause first.
- **subscription-manager registration can be tied to the original instance identity** — a cloned instance may need re-registration, not just a refresh.
