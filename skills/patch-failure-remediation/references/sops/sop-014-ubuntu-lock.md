# SOP-014: Resolve Ubuntu/Debian Package Lock Issues During Patching

| Field | Value |
|-------|-------|
| ID | SOP-014 |
| Category | ubuntu_lock |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Debian 11, Debian 12 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "Could not get lock /var/lib/dpkg/lock-frontend"
- "E: Unable to acquire the dpkg frontend lock"
- "dpkg was interrupted, you must manually run 'dpkg --configure -a'"
- Unattended-upgrades holding lock during patch window
- "another process has locked the administration directory"
- "Waiting for cache lock: Could not get lock /var/lib/apt/lists/lock"
- SSM Patch Manager times out waiting for apt lock release
- "E: dpkg was interrupted, you must manually run 'dpkg --configure -a' to correct the problem"

## Root Cause

Ubuntu/Debian package lock issues caused by:

- unattended-upgrades service running concurrently with SSM patch operation — this is the most common cause; unattended-upgrades has its own schedule that often overlaps with maintenance windows
- apt-daily.timer triggered during patching window (runs twice daily by default)
- Previous dpkg operation interrupted leaving lock files and dpkg in an inconsistent state
- Zombie apt/dpkg processes holding locks after parent process crashed
- Snap auto-refresh (snapd.refresh.timer) running during patch operation and blocking dpkg
- Cloud-init running apt operations on instance start that overlap with immediate patch requests
- Ubuntu Pro/ESM services refreshing in the background

## Related Failure Patterns

- SOP-012 (RPB Race Condition) — RPM-based equivalent of this problem
- SOP-001 (Dependency Conflicts) — interrupted dpkg state can lead to broken dependencies

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available via SSM

## Diagnosis

Determine what holds the lock and for how long:

```bash
lsof /var/lib/dpkg/lock-frontend 2>/dev/null; ps aux | grep -E 'apt|dpkg|unattended' | grep -v grep; stat /var/lib/dpkg/lock-frontend 2>/dev/null | grep Modify
```

Check unattended-upgrades state:

```bash
cat /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null | tail -10
```

## Remediation Steps

### Step 1: Identify processes holding package locks

```bash
fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock /var/cache/apt/archives/lock 2>/dev/null; lsof /var/lib/dpkg/lock-frontend 2>/dev/null; echo "Lock holders identified"
```

Expected output: PIDs of lock holders or empty
On failure: continue

### Step 2: Wait for and terminate lock-holding processes

```bash
PIDS=$(fuser /var/lib/dpkg/lock-frontend 2>/dev/null); if [ -n "$PIDS" ]; then echo "Waiting 30s for processes: $PIDS"; sleep 30; PIDS=$(fuser /var/lib/dpkg/lock-frontend 2>/dev/null); if [ -n "$PIDS" ]; then kill -15 $PIDS 2>/dev/null; sleep 5; kill -9 $PIDS 2>/dev/null; echo "Processes killed"; fi; else echo "No lock holders"; fi
```

Expected output: "No lock holders" or "Processes killed"
On failure: continue

We wait 30 seconds first because unattended-upgrades may be in the middle of a transaction that should complete rather than be killed mid-write.

### Step 3: Remove stale lock files

```bash
rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/cache/apt/archives/lock /var/lib/apt/lists/lock 2>/dev/null; echo "Lock files removed"
```

Expected output: "Lock files removed"
On failure: continue

### Step 4: Fix interrupted dpkg state

```bash
dpkg --configure -a 2>&1; echo "DPKG configure exit: $?"
```

Expected output: "DPKG configure exit: 0"
On failure: abort

### Step 5: Disable unattended-upgrades temporarily and stop apt timers

```bash
systemctl stop unattended-upgrades 2>/dev/null; systemctl stop apt-daily.timer 2>/dev/null; systemctl stop apt-daily-upgrade.timer 2>/dev/null; systemctl stop snapd.refresh.timer 2>/dev/null; echo "Auto-update services stopped"
```

Expected output: "Auto-update services stopped"
On failure: continue

### Step 6: Verify package manager is usable

```bash
apt-get update -qq 2>&1; echo "APT_EXIT:$?"
```

Expected output: "APT_EXIT:0"
On failure: abort

### Step 7: Re-enable auto-update services

```bash
systemctl start apt-daily.timer 2>/dev/null; systemctl start apt-daily-upgrade.timer 2>/dev/null; systemctl start snapd.refresh.timer 2>/dev/null; systemctl start unattended-upgrades 2>/dev/null; echo "Auto-update services re-enabled"
```

Expected output: "Auto-update services re-enabled"
On failure: continue

This restores the services disabled in Step 5 on the success path. If remediation aborts before this step, the Rollback section re-enables them instead.

## Validation

```bash
apt-get check 2>&1 && apt-get -s upgrade 2>&1 | tail -3 && echo "APT OK"
```

Expected: "APT OK"

## Rollback

```bash
systemctl start unattended-upgrades 2>/dev/null; systemctl start apt-daily.timer 2>/dev/null; systemctl start apt-daily-upgrade.timer 2>/dev/null; systemctl start snapd.refresh.timer 2>/dev/null; echo "Auto-update services re-enabled"
```

## Prevention

To prevent lock contention from recurring:
- Configure unattended-upgrades to not run during SSM maintenance windows by adding `Unattended-Upgrade::Allowed-Days` or scheduling maintenance windows outside the apt-daily timer schedule
- Set `APT::Periodic::Unattended-Upgrade "0"` in /etc/apt/apt.conf.d/20auto-upgrades if SSM fully manages patching
- Adjust apt-daily.timer to run at non-conflicting times: `systemctl edit apt-daily.timer`

## Escalation

If dpkg remains in a broken state after `dpkg --configure -a`:
- Try `apt-get install -f` to fix broken dependencies
- Check /var/log/dpkg.log for what was being installed when the interruption occurred
- For severely broken dpkg state: `mv /var/lib/dpkg/info /var/lib/dpkg/info.bak && mkdir /var/lib/dpkg/info && apt-get -f install && mv /var/lib/dpkg/info.bak/* /var/lib/dpkg/info/`
