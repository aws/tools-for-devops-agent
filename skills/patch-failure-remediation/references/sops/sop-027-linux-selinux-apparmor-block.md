# SOP-027: Resolve SELinux/AppArmor Blocking Package Installation

| Field | Value |
|-------|-------|
| ID | SOP-027 |
| Category | selinux_apparmor_block |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "SELinux is preventing" or "avc: denied" messages in audit log
- Package scriptlet fails due to SELinux context mismatch
- "setfiles: /etc/selinux/targeted/contexts/files/file_contexts: No such file or directory"
- AppArmor denials blocking package post-install scripts on Ubuntu
- "error: %post scriptlet failed, exit status 1" with SELinux denial in audit.log
- "restorecon: unable to set security context" during package install

## Root Cause

Security policy frameworks blocking patching when:

- SELinux in enforcing mode denies file operations during package scriptlets
- SELinux policy package is outdated relative to the packages being installed
- File contexts database is corrupt or incomplete after prior interrupted labeling
- AppArmor profiles deny operations that package post-install scripts require
- Custom SELinux policies conflict with new package file paths
- selinux-policy-targeted package itself needs updating first but cannot due to circular dependency

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — SELinux policy package conflicts with application packages
- SOP-004 (Corrupt RPM DB) — corrupt RPM DB may prevent selinux-policy from updating

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Check current SELinux/AppArmor state and recent denials:

```bash
getenforce 2>/dev/null || aa-status 2>/dev/null | head -5; echo "---"; ausearch -m AVC -ts recent 2>/dev/null | tail -10; journalctl -u apparmor --no-pager -n 10 2>/dev/null
```

## Remediation Steps

### Step 1: Determine security framework and current state

```bash
if command -v getenforce &>/dev/null; then echo "SELinux: $(getenforce)"; sestatus 2>/dev/null | head -5; elif command -v aa-status &>/dev/null; then echo "AppArmor active"; aa-status 2>/dev/null | head -5; else echo "No MAC framework detected"; fi
```

Expected output: Security framework status
On failure: continue

### Step 2: Fix SELinux file contexts if corrupted (RPM-based systems)

```bash
if command -v restorecon &>/dev/null; then restorecon -Rv /var/lib/rpm /var/lib/dpkg /usr/lib /usr/bin 2>&1 | tail -5; echo "Contexts restored"; else echo "restorecon not available"; fi
```

Expected output: "Contexts restored"
On failure: continue

### Step 3: Update SELinux policy packages (RPM-based systems)

```bash
if command -v setenforce &>/dev/null; then ORIG=$(getenforce); ( trap 'setenforce "$ORIG" 2>/dev/null; echo "SELinux restored to: $(getenforce) (original: $ORIG)"' EXIT; if [ "$ORIG" = "Enforcing" ]; then setenforce 0 && echo "Temporarily permissive for policy update (was $ORIG)"; else echo "SELinux mode is $ORIG - not changing"; fi; yum update -y selinux-policy selinux-policy-targeted 2>&1 | tail -5 ); echo "SELinux mode: $(getenforce)"; else echo "SELinux not available"; fi
```

Expected output: "SELinux restored to: Enforcing"
On failure: continue

### Step 4: Fix AppArmor denial for specific profile (Debian-based systems)

```bash
if command -v aa-status &>/dev/null; then PROFILE=$(journalctl -u apparmor --no-pager -n 50 2>/dev/null | grep -oP 'apparmor="DENIED".*profile="\K[^"]+' | sort -u | head -1); if [ -n "$PROFILE" ]; then aa-complain "$PROFILE" 2>/dev/null; echo "Set complain: $PROFILE"; else echo "No specific denied profile found"; fi; else echo "AppArmor not available"; fi
```

Expected output: Profile name set to complain or "AppArmor not available"
On failure: continue

### Step 5: Validate denial is resolved and system is ready for next patch cycle

```bash
if command -v setenforce &>/dev/null; then echo "SELinux: $(getenforce)"; DENIALS=$(ausearch -m AVC -ts recent 2>/dev/null | grep -c denied); echo "Recent SELinux denials: $DENIALS"; [ "$DENIALS" -eq 0 ] && echo "No active denials"; fi; if command -v aa-status &>/dev/null; then AA_DENIALS=$(journalctl -k --no-pager -n 200 2>/dev/null | grep -c 'apparmor="DENIED"'); echo "Recent AppArmor denials: $AA_DENIALS"; fi; if command -v apt-get &>/dev/null; then apt-get -s upgrade 2>&1 | tail -5; fi; if command -v dnf &>/dev/null; then dnf check-update -q 2>&1 | head -5; elif command -v yum &>/dev/null; then yum check-update -q 2>&1 | head -5; fi; if [ "${DENIALS:-0}" -eq 0 ] && [ "${AA_DENIALS:-0}" -eq 0 ]; then echo "SELINUX/APPARMOR BLOCK RESOLVED - ready for next patch cycle"; else echo "DENIALS REMAIN: SELinux=${DENIALS:-0} AppArmor=${AA_DENIALS:-0}"; fi
```

Expected output: "No active denials" and "SELINUX/APPARMOR BLOCK RESOLVED - ready for next patch cycle"
On failure: abort

### Step 6: Restore AppArmor enforce mode for modified profile

```bash
if command -v aa-enforce &>/dev/null; then PROFILE=$(journalctl -u apparmor --no-pager -n 50 2>/dev/null | grep -oP 'apparmor="DENIED".*profile="\K[^"]+' | sort -u | head -1); if [ -n "$PROFILE" ]; then aa-enforce "$PROFILE" 2>/dev/null; echo "Restored enforce: $PROFILE"; else echo "No specific denied profile identified - NOT running 'aa-enforce /etc/apparmor.d/*' (that would re-enforce every profile, including ones deliberately left in complain mode). Re-enforce only the profile that was set to complain in Step 4, e.g. aa-enforce <profile>"; fi; fi
```

Expected output: "Restored enforce: ..." or the note to re-enforce only the specific profile
On failure: continue

## Validation

```bash
if command -v getenforce &>/dev/null; then echo "SELinux: $(getenforce)"; DENIALS=$(ausearch -m AVC -ts recent 2>/dev/null | grep -c denied); echo "Recent SELinux denials: $DENIALS"; fi; if command -v aa-status &>/dev/null; then aa-status 2>/dev/null | grep -c "enforce mode" | awk '{print "Profiles in enforce: "$1}'; AA_DENIALS=$(journalctl -k --no-pager -n 200 2>/dev/null | grep -c 'apparmor="DENIED"'); echo "Recent AppArmor denials: $AA_DENIALS"; fi; if [ "${DENIALS:-0}" -eq 0 ] && [ "${AA_DENIALS:-0}" -eq 0 ]; then echo "Security policy OK"; else echo "DENIALS REMAIN: SELinux=${DENIALS:-0} AppArmor=${AA_DENIALS:-0}"; fi
```

Expected: "Security policy OK" with no new denials

## Rollback

```bash
if command -v setenforce &>/dev/null; then setenforce 1; echo "SELinux re-enforced: $(getenforce)"; fi
if command -v aa-enforce &>/dev/null; then aa-enforce /etc/apparmor.d/* 2>/dev/null; echo "AppArmor re-enforced"; fi
```

## Escalation

If SELinux/AppArmor continues blocking patches:
- Generate a custom policy module: `ausearch -m AVC -ts today | audit2allow -M patch_fix && semodule -i patch_fix.pp`
- Update the SELinux policy package first: `yum update -y selinux-policy selinux-policy-targeted`
- For persistent AppArmor issues: create a local override in /etc/apparmor.d/local/
- Consider whether the security policy needs permanent adjustment for the software being patched
