# SOP-040: Resolve APT Broken Dependencies on Ubuntu/Debian

| Field | Value |
|-------|-------|
| ID | SOP-040 |
| Category | apt_broken_dependencies |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Debian 11, Debian 12 |
| Requires Reboot | No |
| Estimated Duration | 150 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "The following packages have unmet dependencies" during apt upgrade
- "Depends: libX (>= version) but version is to be installed"
- "E: Broken packages" when running apt-get install or upgrade
- "Held broken packages" preventing upgrade completion
- "You might want to run 'apt --fix-broken install'"
- "dpkg: dependency problems prevent configuration of <package>"
- Packages pinned at old versions that block cascading security updates
- "The following packages have been kept back" for critical security patches

## Root Cause

Broken APT dependencies occur when:

- Partial upgrade was interrupted leaving some packages upgraded and others at old versions
- PPA or third-party repo provides package version incompatible with base Ubuntu/Debian
- Apt pinning (/etc/apt/preferences.d/) prevents required dependency from upgrading
- Package was manually installed with dpkg --force-depends breaking dependency chain
- Ubuntu release upgrade (do-release-upgrade) was incomplete
- Snap packages providing libraries that conflict with deb versions
- Repository mirror lag — some mirrors have new packages while dependencies still point to old versions

## Related Failure Patterns

- SOP-014 (Ubuntu Lock) — lock issues can lead to interrupted upgrades causing broken deps
- SOP-025 (Corrupt dpkg) — broken dpkg journal compounds dependency issues
- SOP-035 (Third-Party Repo Conflict) — PPAs commonly cause broken dependencies

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available
- No other apt/dpkg operations in progress

## Diagnosis

Check dependency state:

```bash
apt-get check 2>&1; echo "---"; dpkg --audit 2>&1; echo "---"; apt-mark showhold 2>&1; echo "---"; cat /etc/apt/preferences.d/* 2>/dev/null
```

## Remediation Steps

### Step 1: Identify broken packages

```bash
BROKEN=$(dpkg -l | grep -E "^iU|^iF|^iH|^rc" | awk '{print $2}'); if [ -n "$BROKEN" ]; then echo "Broken/incomplete packages:"; echo "$BROKEN"; else echo "No broken packages in dpkg state"; fi; echo "---"; apt-get check 2>&1 | head -20
```

Expected output: List of broken packages or clean state
On failure: continue

### Step 2: Attempt automatic fix

```bash
apt-get install -f -y 2>&1; echo "Fix-broken exit: $?"
```

Expected output: "Fix-broken exit: 0"
On failure: continue

### Step 3: Configure unconfigured packages

```bash
dpkg --configure -a 2>&1; echo "Configure exit: $?"
```

Expected output: "Configure exit: 0"
On failure: continue

### Step 4: Remove held packages that block updates

```bash
HELD_FILE=/var/tmp/sop040-held.txt; : > "$HELD_FILE"; HELD=$(apt-mark showhold 2>/dev/null); if [ -n "$HELD" ]; then echo "Held packages: $HELD"; apt-get update -qq 2>/dev/null; UPG=$(apt list --upgradable 2>/dev/null | awk -F/ '/\//{print $1}'); BLOCKING=$(comm -12 <(printf '%s\n' $HELD | sort -u) <(printf '%s\n' $UPG | sort -u)); if [ -n "$BLOCKING" ]; then printf '%s\n' $BLOCKING > "$HELD_FILE"; echo "Held packages withholding an available upgrade: $BLOCKING (recorded in $HELD_FILE for Rollback re-hold)"; apt-mark unhold $BLOCKING 2>&1; echo "Holds removed (were blocking updates)"; else echo "No held package has a pending upgrade - holds are not blocking updates; leaving them intact (holds are often intentional)"; fi; else echo "No held packages"; fi
```

Expected output: "No held packages", "Holds removed (were blocking updates)", or "No held package has a pending upgrade - ... leaving them intact"
On failure: continue

### Step 5: Fix partially installed packages

> **CAUTION:** The `dpkg --remove --force-remove-reinstreq` fallback below force-removes a package that failed to reinstall, even if it is still required by the system or other packages. This can leave dependents unsatisfied and remove functionality. It runs only when a normal reinstall fails; review the removed package before proceeding and reinstall it once the repo/dependency issue is resolved.

```bash
PARTIAL=$(dpkg -l | grep "^iF\|^iU" | awk '{print $2}'); if [ -n "$PARTIAL" ]; then for pkg in $PARTIAL; do apt-get install --reinstall -y "$pkg" 2>&1 || dpkg --remove --force-remove-reinstreq "$pkg" 2>&1; done; echo "Partial packages fixed"; else echo "No partial packages"; fi
```

Expected output: "No partial packages" or "Partial packages fixed"
On failure: continue

### Step 6: Update package lists and verify

```bash
apt-get update 2>&1; apt-get check 2>&1; echo "APT state exit: $?"
```

Expected output: "APT state exit: 0"
On failure: abort

### Step 7: Simulate upgrade to confirm no broken deps remain

```bash
apt-get -s upgrade 2>&1 | tail -10; echo "Simulate exit: ${PIPESTATUS[0]}"
```

Expected output: "Simulate exit: 0"
On failure: abort

## Validation

```bash
apt-get check 2>&1 || { echo "STILL BROKEN: apt-get check failed"; exit 1; }; AUDIT_ISSUES=$(dpkg --audit 2>&1 | grep -c "." || true); if [ "$AUDIT_ISSUES" -gt 0 ]; then echo "STILL BROKEN: $AUDIT_ISSUES issues"; exit 1; fi; echo "APT DEPENDENCIES OK"
```

Expected: "APT DEPENDENCIES OK"

## Rollback

```bash
HELD_FILE=/var/tmp/sop040-held.txt; if [ -s "$HELD_FILE" ]; then apt-mark hold $(cat "$HELD_FILE") 2>/dev/null; echo "Package holds restored from $HELD_FILE"; else echo "No persisted holds to restore"; fi
echo "For deeper rollback, check /var/log/apt/history.log for recent transactions"
```

## Escalation

If broken dependencies cannot be resolved:
- Try `apt-get dist-upgrade -y` which is more aggressive at resolving dependencies (may remove packages)
- Check /etc/apt/preferences.d/ for pinning rules blocking upgrades
- Identify the root package causing the cascade: `apt-cache depends --installed <package>`
- For severe cases: `dpkg --force-remove-reinstreq --remove <broken-package>` then reinstall
- If a PPA is the cause: `ppa-purge <ppa-name>` to revert to official packages
- Consider `apt-get install <package>=<version>` to force a specific compatible version
