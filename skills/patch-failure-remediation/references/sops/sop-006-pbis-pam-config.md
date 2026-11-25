# SOP-006: Repair PBIS PAM Configuration Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-006 |
| Category | pbis_pam_config |
| Severity | High |
| Risk Level | High |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9, Ubuntu 20.04, Ubuntu 22.04 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails during pre/post scripts involving authentication checks
- PBIS (PowerBroker Identity Services) errors in patch logs
- PAM authentication failures after patching attempts
- "pam_lsass.so" or "pam_lwidentity.so" missing errors
- SSH access lost after partial patch operation
- "Module is unknown" errors in /var/log/secure referencing PBIS PAM modules
- Domain users unable to authenticate after patching

## Root Cause

PBIS PAM configuration breaks when:

- Patching updates pam packages (pam, pam_krb5, sssd-common) which overwrite PBIS custom PAM config files in /etc/pam.d/
- PBIS service (lwsmd) is not running during PAM reconfiguration triggered by package scriptlets
- Symlinks to PBIS PAM modules (typically in /opt/pbis/lib64/) become stale after library updates
- authconfig or authselect runs during patching and resets PBIS entries to defaults (common on RHEL 8+)
- SELinux relabeling removes contexts from PBIS PAM module files

This is a HIGH RISK SOP because incorrect PAM configuration can lock out all users from the instance. Always ensure SSM access remains functional as a recovery path.

## Related Failure Patterns

- SOP-001 (Dependency Conflicts) — pam package conflicts can trigger this
- SOP-012 (RPB Race Condition) — if PBIS reconfiguration races with patch scriptlets

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online) — this is critical as PAM breakage can lock out SSH
- PBIS packages are installed (pbis-open or likewise-open)
- Backup of PAM configuration exists or can be regenerated

## Diagnosis

Check if PBIS modules are present on disk:

```bash
ls -la /opt/pbis/lib64/security/pam_lsass.so 2>/dev/null; ls -la /opt/likewise/lib64/security/ 2>/dev/null
```

Check current PAM configuration for PBIS entries:

```bash
grep -r "pam_lsass\|pam_lwidentity\|pbis\|likewise" /etc/pam.d/ 2>/dev/null
```

## Remediation Steps

### Step 1: Check PBIS service status

```bash
systemctl status lwsmd 2>/dev/null || /opt/pbis/bin/lwsm-status 2>/dev/null; echo "PBIS status check done"
```

Expected output: Service status followed by "PBIS status check done"
On failure: continue

### Step 2: Restart PBIS services

```bash
systemctl restart lwsmd 2>/dev/null || /opt/pbis/bin/lwsm restart lwreg 2>/dev/null; sleep 3; /opt/pbis/bin/lwsm list 2>/dev/null; echo "PBIS restarted"
```

Expected output: "PBIS restarted"
On failure: continue

### Step 3: Backup current PAM configuration

```bash
cp -a /etc/pam.d /etc/pam.d.backup.$(date +%Y%m%d%H%M%S); echo "PAM backup created"
```

Expected output: "PAM backup created"
On failure: abort (this backup is critical for rollback)

### Step 4: Reconfigure PBIS PAM integration

```bash
if [ -x /opt/pbis/bin/config ]; then /opt/pbis/bin/config --dump 2>/dev/null; /opt/pbis/bin/domainjoin-cli configure --enable pam 2>/dev/null; echo "PBIS PAM reconfigured"; else echo "PBIS binary not found"; exit 1; fi
```

Expected output: "PBIS PAM reconfigured"
On failure: abort

### Step 5: Verify PAM configuration includes PBIS modules

```bash
grep -l "pam_lsass\|pam_lwidentity" /etc/pam.d/* 2>/dev/null | head -5; echo "PAM PBIS verification done"
```

Expected output: File paths containing PBIS PAM entries
On failure: abort

### Step 6: Verify SSH PAM stack is functional

```bash
if command -v pamtester >/dev/null; then timeout 15 pamtester sshd "$(whoami)" authenticate </dev/null 2>&1; else echo "pamtester not available — checking config manually"; fi; grep -E "^(auth|account|session)" /etc/pam.d/sshd | head -10; echo "SSH PAM check done"
```

Expected output: "SSH PAM check done"
On failure: continue

## Validation

```bash
timeout 15 /opt/pbis/bin/lsa get-status; RC=$?; id "$(whoami)" 2>/dev/null; if [ $RC -eq 0 ]; then echo "PBIS LSA status OK: $RC"; else echo "PBIS LSA status check failed or timed out: $RC"; fi
```

`lsa authenticate-user` prompts for a password and would block indefinitely with no TTY, and chaining `id` after it makes `$?` report `id`'s exit rather than the auth result. Use the non-blocking `lsa get-status` under `timeout 15` and report *its* exit code.

Expected: LSA provider status information with "PBIS LSA status OK: 0"

## Rollback

```bash
LATEST_BACKUP=$(ls -td /etc/pam.d.backup.* 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then rm -rf /etc/pam.d; mv "$LATEST_BACKUP" /etc/pam.d; echo "PAM config restored"; else echo "No backup found"; fi
systemctl restart lwsmd 2>/dev/null
```

## Escalation

If PAM cannot be restored and SSH is locked out:
- SSM Session Manager remains the recovery path
- Check if the instance has a serial console connection configured
- Consider restoring /etc/pam.d from a known-good AMI snapshot
- Domain rejoin may be needed: `/opt/pbis/bin/domainjoin-cli join <DOMAIN> <ADMIN_USER>`
