# SOP-038: Resolve Systemd Service Restart Failures After Patching

| Field | Value |
|-------|-------|
| ID | SOP-038 |
| Category | systemd_service_restart_failure |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Package installs successfully but service fails to restart in %post scriptlet
- "Job for <service>.service failed because the control process exited with error code"
- "systemctl restart <service>" fails in package post-install hooks
- "A dependency job for <service>.service failed"
- Services left in "failed" state after patching completes
- "Failed to start <service>: Unit is masked"
- "Cannot reload daemon: Connection refused" — systemd itself needs daemon-reload
- Application downtime after successful patch due to failed service restarts

## Root Cause

Service restart failures after patching when:

- Updated configuration files have syntax errors (package dropped new config that conflicts with local customizations)
- Service dependencies not yet restarted (e.g., sshd depends on crypto-policies which was updated)
- Systemd unit files updated but daemon-reload not triggered between package installs
- Service was masked (disabled intentionally) but package %post assumes it should restart
- Resource limits (LimitNOFILE, memory limits) in unit files cause immediate crash on start
- Port already in use by the old process that didn't terminate cleanly
- New binary requires a library that was updated but not yet loaded (needs ldconfig)

## Related Failure Patterns

- SOP-029 (Package Scriptlet Failure) — service restart is the most common scriptlet failure
- SOP-027 (SELinux/AppArmor Block) — security policies can prevent service starts

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Check for failed services and their logs:

```bash
systemctl --failed 2>/dev/null; echo "---"; for svc in $(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}'); do echo "=== $svc ==="; journalctl -u "$svc" --no-pager -n 5 2>/dev/null; done
```

## Remediation Steps

### Step 1: Identify failed services

```bash
FAILED=$(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}'); if [ -n "$FAILED" ]; then echo "Failed services:"; echo "$FAILED"; else echo "No failed services"; fi
```

Expected output: List of failed services or "No failed services"
On failure: continue

### Step 2: Reload systemd daemon state

```bash
systemctl daemon-reload 2>&1; ldconfig 2>&1; echo "Daemon and ldconfig reloaded"
```

Expected output: "Daemon and ldconfig reloaded"
On failure: continue

### Step 3: Attempt restart of failed services

```bash
FIXED=0; STILL_FAILED=0; for svc in $(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}'); do systemctl reset-failed "$svc" 2>/dev/null; if systemctl is-enabled "$svc" 2>/dev/null | grep -q "enabled\|static"; then systemctl restart "$svc" 2>/dev/null && FIXED=$((FIXED+1)) || STILL_FAILED=$((STILL_FAILED+1)); fi; done; echo "Fixed: $FIXED, Still failed: $STILL_FAILED"
```

Expected output: "Fixed: N, Still failed: 0"
On failure: continue

### Step 4: Check and fix configuration file issues

```bash
STILL_BROKEN=$(systemctl --failed --plain --no-legend 2>/dev/null | awk '{print $1}'); for svc in $STILL_BROKEN; do UNIT_NAME=$(echo "$svc" | sed 's/\.service//'); echo "=== $svc ==="; echo "Config test:"; case "$UNIT_NAME" in nginx) if command -v nginx >/dev/null; then nginx -t 2>&1; else echo "nginx binary not found - skipping config test"; fi;; sshd|ssh) if command -v sshd >/dev/null; then sshd -t 2>&1; else echo "sshd binary not found - skipping config test"; fi;; httpd) if command -v httpd >/dev/null; then httpd -t 2>&1; else echo "httpd binary not found - skipping config test"; fi;; apache2) if command -v apache2ctl >/dev/null; then apache2ctl configtest 2>&1; else echo "apache2ctl not found - skipping config test"; fi;; named|bind9) if command -v named-checkconf >/dev/null; then named-checkconf 2>&1; else echo "named-checkconf not found - skipping config test"; fi;; *) echo "No known config-test command for '$UNIT_NAME' - skipping (never execute the unit name as a binary)";; esac; done; echo "Config check done"
```

Expected output: Configuration validation results
On failure: continue

### Step 5: Handle rpmnew/rpmsave config conflicts

```bash
CONFLICTS=$(find /etc -name "*.rpmnew" -o -name "*.dpkg-dist" 2>/dev/null | head -10); if [ -n "$CONFLICTS" ]; then echo "Config conflicts found:"; echo "$CONFLICTS"; echo "Review needed - not auto-merging"; else echo "No config conflicts"; fi
```

Expected output: List of config conflicts or "No config conflicts"
On failure: continue

### Step 6: Final verification of service states

```bash
FAILED_COUNT=$(systemctl --failed --plain --no-legend 2>/dev/null | wc -l); if [ "$FAILED_COUNT" -eq 0 ]; then echo "ALL SERVICES HEALTHY"; else echo "REMAINING FAILURES: $FAILED_COUNT"; systemctl --failed 2>/dev/null; exit 1; fi
```

Expected output: "ALL SERVICES HEALTHY"
On failure: abort

## Validation

```bash
FAILED=$(systemctl --failed --plain --no-legend 2>/dev/null | wc -l); echo "Failed services: $FAILED"; [ "$FAILED" -eq 0 ] && echo "SERVICES OK" || echo "SERVICES NEED ATTENTION"
```

Expected: "SERVICES OK"

## Rollback

```bash
echo "Service restart issues typically require specific investigation per service."
echo "Check: journalctl -u <service> for details"
echo "For config conflicts: restore .rpmsave or .rpmnew as appropriate"
```

## Escalation

If services remain in failed state:
- Check journalctl logs for the specific failure reason: `journalctl -xeu <service>`
- Compare configuration with package defaults: `diff /etc/<app>/<config> /etc/<app>/<config>.rpmnew`
- If service is masked: `systemctl unmask <service>` (verify it should be running first)
- For port conflicts: `ss -tlnp | grep <port>` to find what's holding the port
- For library issues: `ldd /usr/sbin/<binary>` to check for missing shared libraries
- Consider if the service restart can be deferred to the next maintenance reboot
