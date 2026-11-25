# SOP-029: Resolve Package Scriptlet Failures During Patching

| Field | Value |
|-------|-------|
| ID | SOP-029 |
| Category | scriptlet_failure |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 150 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "error: %pre scriptlet failed, exit status 1"
- "error: %post scriptlet failed, exit status N" during package upgrade
- "subprocess new pre-installation script returned error exit status 1" on Debian/Ubuntu
- "dpkg: error processing package <name> (--configure): subprocess installed post-installation script returned error"
- Package left in half-installed/half-configured state
- "Running scriptlet: <package> ... FAILED" in DNF transaction output
- "warning: %postun(pkg-version) scriptlet failed, exit status 1"

## Root Cause

Package scriptlet failures occur when:

- Pre/post install scripts depend on services that are stopped or unavailable
- Scriptlet calls a binary that has been removed or replaced by a prior update in the same transaction
- Insufficient permissions or missing directories expected by the scriptlet
- Systemd service reload/restart in %post fails because the service has configuration errors
- ldconfig in %post fails due to corrupt cache or missing libraries
- Scriptlet assumes interactive terminal (stdin) which SSM does not provide
- Oracle Linux ksplice-related scripts fail when ksplice service is not active

## Related Failure Patterns

- SOP-027 (SELinux/AppArmor Block) — security policies can cause scriptlet failures
- SOP-002 (Disk Full) — scriptlets fail if they cannot write to disk
- SOP-010 (Python Missing) — many scriptlets depend on Python

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Identify the failing package and scriptlet:

```bash
rpm -qa --last 2>/dev/null | head -10; echo "---"; grep -i "scriptlet failed" /var/log/dnf.log /var/log/yum.log 2>/dev/null | tail -10; grep "subprocess.*script returned error" /var/log/dpkg.log 2>/dev/null | tail -10
```

## Remediation Steps

### Step 1: Identify packages in broken state

```bash
if command -v rpm &>/dev/null; then rpm -Va --nofiles --nodigest 2>&1 | grep -E "^missing|^.M" | head -20; echo "RPM verify done"; elif command -v dpkg &>/dev/null; then dpkg --audit 2>&1; echo "DPKG audit done"; fi
```

Expected output: List of packages with issues
On failure: continue

### Step 2: Fix broken package state (RPM-based)

```bash
PKGS=$(rpm -qa --qf '%{NAME}\n' | while read pkg; do rpm -V "$pkg" 2>&1 | grep -qE "missing|^.M" && echo "$pkg"; done | head -5); if [ -z "$PKGS" ]; then echo "No broken packages"; elif command -v dnf &>/dev/null; then dnf -y reinstall $PKGS 2>&1; echo "Reinstall exit: $?"; elif command -v yum &>/dev/null; then yum -y reinstall $PKGS 2>&1; echo "Reinstall exit: $?"; else echo "Not RPM-based"; fi
```

Expected output: "Reinstall exit: 0"
On failure: continue

### Step 3: Fix broken package state (Debian-based)

```bash
if command -v dpkg &>/dev/null; then dpkg --configure -a 2>&1; apt-get install -f -y 2>&1; echo "APT fix exit: $?"; else echo "Not Debian-based"; fi
```

Expected output: "APT fix exit: 0"
On failure: continue

### Step 4: Force scriptlet skip for persistently failing packages (RPM-based)

> **NOTE:** `--setopt=tsflags=noscripts` reinstalls the package files but skips the `%post`/`%pre` scriptlets. Those scriptlets often register/enable/restart services, create users, or run `ldconfig`, so the package can be left with services unconfigured or not running. Use only as a last resort, then manually perform the equivalent post-install steps (e.g. `systemctl daemon-reload`, enable/restart the service) and verify the service state.

```bash
if command -v dnf &>/dev/null; then BROKEN=$(rpm -qa --qf '%{NAME}\n' | while read pkg; do rpm -V "$pkg" 2>&1 | grep -q "missing" && echo "$pkg"; done | head -3); if [ -n "$BROKEN" ]; then dnf -y reinstall --setopt=tsflags=noscripts $BROKEN 2>&1; echo "Reinstall (noscripts) exit: $?"; else echo "No broken packages"; fi; fi
```

Expected output: "No broken packages" or "Reinstall (noscripts) exit: 0"
On failure: continue

### Step 5: Refresh ldconfig and systemd state

```bash
ldconfig 2>&1; systemctl daemon-reload 2>&1; echo "System state refreshed"
```

Expected output: "System state refreshed"
On failure: continue

### Step 6: Verify package manager can complete transactions

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1; echo "DNF check exit: $?"; elif command -v yum &>/dev/null; then yum check 2>&1; echo "YUM check exit: $?"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1; echo "APT check exit: $?"; fi
```

Expected output: Exit code 0
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 && echo "PACKAGE STATE OK"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1 && dpkg --audit 2>&1 && echo "PACKAGE STATE OK"; elif command -v zypper &>/dev/null; then zypper verify 2>&1 && echo "PACKAGE STATE OK"; fi
```

Expected: "PACKAGE STATE OK"

## Rollback

```bash
echo "Rollback depends on specific package - check /var/log/dnf.log or /var/log/dpkg.log for the transaction to reverse"
if command -v dnf &>/dev/null; then dnf history list --last 5 2>&1; fi
```

## Escalation

If scriptlet failures persist:
- Extract and examine the failing scriptlet: `rpm -q --scripts <package-name>`
- For Debian: `cat /var/lib/dpkg/info/<package>.postinst`
- Run the scriptlet manually with debug: `bash -x /var/lib/dpkg/info/<package>.postinst configure`
- Consider `--nopost` or `--nopre` flags for RPM to skip specific scriptlets
- For systemd-related scriptlet failures, fix the service configuration first, then re-run `dnf reinstall <package>`
