# SOP-012: Resolve RPB Race Condition Package Conflicts

| Field | Value |
|-------|-------|
| ID | SOP-012 |
| Category | rpb_race_condition |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, RHEL 8, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 150 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "package already installed" but different version
- "Transaction check error: file from install conflicts with file from package"
- Concurrent patching operations leave partial state
- "Unable to get exclusive lock on /var/lib/rpm/.rpm.lock"
- RPM scriptlet failures during simultaneous package operations
- "Existing lock: pid N" in yum/dnf output
- "Failed to obtain lock" with "another copy is running as pid N"
- SSM Patch Manager reports "InProgress" for extended periods then times out

## Root Cause

Race condition conflicts occur when:

- Multiple patch baselines execute simultaneously on the same instance (e.g., both a custom baseline and default baseline triggered)
- SSM agent retries patch operation while previous is still running (timeout/network blip causes agent to restart the command)
- System package manager background services (PackageKit, dnf-makecache.timer) interfere with SSM-initiated patching
- Automated updates (yum-cron, dnf-automatic) run during the same patch window
- RPB (Run Patch Baseline) retries create conflicting transactions when the previous run left locks but exited
- cron jobs running `yum update` or `dnf upgrade` overlap with maintenance window execution

This is a common issue in environments where multiple automation tools (SSM, Ansible, Chef, cron) all manage packages.

## Related Failure Patterns

- SOP-004 (Corrupt RPM DB) — race conditions are a primary cause of database corruption
- SOP-001 (Dependency Conflicts) — partial transactions from races leave inconsistent package state
- SOP-014 (Ubuntu Lock) — Ubuntu/Debian equivalent of this problem

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No active SSH sessions running package operations

## Diagnosis

Identify what is holding the lock:

```bash
fuser -v /var/lib/rpm/.rpm.lock 2>/dev/null; ps aux | grep -E 'yum|dnf|rpm|packagekit|apt' | grep -v grep
```

Check if multiple SSM commands are running:

```bash
ps aux | grep -i "amazon-ssm-agent\|ssm-document-worker" | grep -v grep | wc -l
```

## Remediation Steps

### Step 1: Identify and kill conflicting package manager processes

```bash
PIDS=$(pgrep -f '(^|/)(yum|dnf|apt-get|rpm|packagekitd?)( |$)' 2>/dev/null | grep -vw "$$"); if [ -n "$PIDS" ]; then echo "Conflicting PIDs: $PIDS"; kill -15 $PIDS 2>/dev/null; sleep 30; STILL=$(pgrep -f '(^|/)(yum|dnf|apt-get|rpm|packagekitd?)( |$)' 2>/dev/null | grep -vw "$$"); if [ -n "$STILL" ]; then echo "ERROR: package operations still running after 30s SIGTERM grace: $STILL - NOT sending SIGKILL (kill -9 on rpm/dnf/yum/apt risks RPM DB corruption); escalate to a human"; exit 1; else echo "Processes terminated"; fi; else echo "No conflicting processes"; fi
```

Expected output: "No conflicting processes" or "Processes terminated"
On failure (package operations still running after the 30s SIGTERM grace): this step intentionally exits 1 and stops here rather than sending SIGKILL — `kill -9` on rpm/dnf/yum/apt risks RPM DB corruption. Escalate to a human; do not continue to the following steps.

### Step 2: Remove stale lock files

```bash
rm -f /var/lib/rpm/.rpm.lock /var/run/yum.pid /var/cache/dnf/metadata_lock.pid 2>/dev/null; rm -f /var/lib/dpkg/lock* /var/cache/apt/archives/lock 2>/dev/null; echo "Locks removed"
```

Expected output: "Locks removed"
On failure: continue

### Step 3: Disable background package services temporarily

```bash
systemctl stop packagekit 2>/dev/null; systemctl stop dnf-makecache.timer 2>/dev/null; systemctl stop yum-cron 2>/dev/null; systemctl stop dnf-automatic.timer 2>/dev/null; systemctl stop unattended-upgrades 2>/dev/null; echo "Background services stopped"
```

Expected output: "Background services stopped"
On failure: continue

### Step 4: Clean up incomplete transactions

```bash
yum-complete-transaction --cleanup-only 2>/dev/null; dnf history list 2>/dev/null | head -5; BK=/var/lib/rpm.backup.$(date +%Y%m%d%H%M%S); cp -a /var/lib/rpm "$BK" || { echo "ERROR: rpmdb backup failed (e.g. insufficient space) - NOT running rpm --rebuilddb without a recovery point; escalate"; exit 1; }; rpm --rebuilddb; echo "Transactions cleaned (rpmdb backed up to $BK)"
```

Expected output: "Transactions cleaned (rpmdb backed up to ...)"
On failure: if the rpmdb backup fails, this step exits 1 and stops (it will not run `rpm --rebuilddb` without a recovery point) — escalate rather than continue. Any other non-zero result: continue.

DNF auto-recovers incomplete transactions on the next invocation. Blindly running `dnf history undo last` would revert a legitimate completed operation if the race condition only affected lock state without corrupting a transaction.

### Step 5: Verify package manager is usable

```bash
yum check 2>/dev/null || dnf check 2>/dev/null || dpkg --audit 2>/dev/null; echo "Package manager check: $?"
```

Expected output: "Package manager check: 0"
On failure: abort

## Validation

```bash
yum check-update 2>/dev/null || dnf check-update 2>/dev/null || apt-get -s upgrade 2>/dev/null; RC=$?; [ $RC -le 100 ] && echo "PACKAGE MANAGER OK" || echo "PACKAGE MANAGER ISSUES"
```

Expected: "PACKAGE MANAGER OK"

## Rollback

```bash
systemctl start packagekit 2>/dev/null; systemctl start dnf-makecache.timer 2>/dev/null; systemctl start yum-cron 2>/dev/null; systemctl start dnf-automatic.timer 2>/dev/null; echo "Background services re-enabled"
```

## Prevention

To prevent race conditions from recurring:
- Disable `dnf-automatic.timer` and `yum-cron` on instances managed by SSM Patch Manager
- Configure maintenance windows to not overlap with cron-based package updates
- Use SSM State Manager to ensure only one patch baseline targets each instance
- Set `metadata_timer_sync=0` in dnf.conf to prevent background metadata refresh during patch windows

## Escalation

If the package manager remains unusable after cleanup:
- Check if RPM database is corrupted (SOP-004)
- Verify no other automation (Ansible, Chef, Puppet) is running package operations
- Review SSM command history for overlapping executions: `aws ssm list-commands --instance-id <id> --filters Key=Status,Values=InProgress`
