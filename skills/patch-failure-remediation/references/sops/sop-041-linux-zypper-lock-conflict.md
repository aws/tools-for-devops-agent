# SOP-041: Resolve Zypper Lock/Conflict Issues on SUSE During Patching

| Field | Value |
|-------|-------|
| ID | SOP-041 |
| Category | zypper_lock_conflict |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | SLES 12, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "System management is locked by the application with pid N"
- "Another zypper is running" blocking patch operation
- "Solution X: do not install patch Y" with no resolution available
- "Patch Z conflicts with installed package" during zypper patch
- "Problem: nothing provides X needed by Y" in SLES patch output
- "File conflicts between packages" in zypper transaction
- "Package is locked" preventing security updates
- zypper returns "No update candidate" for packages that have known patches

## Root Cause

SUSE zypper conflicts occur when:

- Another zypper or packagekit process holds the lock (/var/run/zypp.pid)
- Package locks (zypper locks) prevent patching of specific packages
- SUSE module/extension not activated provides missing dependencies
- Patch conflicts between multiple patches that cannot be applied together
- Pattern (meta-package) requirements conflict with individual package versions
- Vendor change required (package from SUSE vs third-party) not auto-approved
- Orphaned packages from disabled repos block dependency resolution

## Related Failure Patterns

- SOP-013 (SUSE Repo Refresh) — repo issues cause zypper to fail before reaching conflict resolution
- SOP-031 (Expired Certificates) — SUSE registration expiry blocks repo access

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is SLES 12 or SLES 15
- SUSEConnect registration is active

## Diagnosis

Check zypper state and locks:

```bash
zypper locks 2>/dev/null; echo "---"; cat /var/run/zypp.pid 2>/dev/null && echo "Zypper PID lock exists" || echo "No PID lock"; echo "---"; zypper ps -s 2>/dev/null; echo "---"; zypper verify --dry-run 2>&1 | head -20
```

## Remediation Steps

### Step 1: Check for running zypper processes

```bash
ZYPP_PID=$(cat /var/run/zypp.pid 2>/dev/null); if [ -n "$ZYPP_PID" ]; then if kill -0 "$ZYPP_PID" 2>/dev/null; then echo "Active zypper process: $ZYPP_PID"; ps -p "$ZYPP_PID" -o pid,ppid,cmd; else echo "Stale PID file (process $ZYPP_PID not running)"; rm -f /var/run/zypp.pid; echo "Stale lock removed"; fi; else echo "No zypper lock"; fi
```

Expected output: "No zypper lock" or "Stale lock removed"
On failure: continue

### Step 2: Kill stuck zypper processes if necessary

```bash
PIDS=$(pgrep -f "zypper|packagekit" 2>/dev/null); if [ -n "$PIDS" ]; then echo "Waiting 30s for processes to finish (avoids RPM DB corruption): $PIDS"; sleep 30; PIDS=$(pgrep -f "zypper|packagekit" 2>/dev/null); if [ -n "$PIDS" ]; then kill -15 $PIDS 2>/dev/null; sleep 10; PIDS=$(pgrep -f "zypper|packagekit" 2>/dev/null); if [ -n "$PIDS" ]; then echo "ESCALATE: processes $PIDS still running after SIGTERM - NOT sending SIGKILL, because kill -9 during an RPM/zypper transaction risks RPM DB corruption. Escalate for manual investigation instead."; else rm -f /var/run/zypp.pid; echo "Processes terminated gracefully"; fi; else rm -f /var/run/zypp.pid; echo "Processes exited on their own"; fi; else echo "No zypper processes"; fi
```

Expected output: "No zypper processes", "Processes exited on their own", or "Processes terminated gracefully" (or an "ESCALATE:" message if processes persist after SIGTERM)
On failure: continue

### Step 3: List and remove package locks

```bash
LOCK_FILE=/var/tmp/sop041-locks.txt; : > "$LOCK_FILE"; LOCKS=$(zypper locks 2>/dev/null | grep -c "^[0-9]"); if [ "$LOCKS" -gt 0 ]; then echo "Found $LOCKS package locks:"; zypper locks; zypper locks 2>/dev/null | awk -F'|' '$1 ~ /^[[:space:]]*[0-9]+[[:space:]]*$/ {gsub(/^[[:space:]]+|[[:space:]]+$/,"",$2); print $2}' > "$LOCK_FILE"; echo "Lock names saved to $LOCK_FILE (for Rollback restore)"; while IFS= read -r lk; do [ -n "$lk" ] && zypper rl "$lk" 2>&1; done < "$LOCK_FILE"; echo "Removed the captured package-name locks (pattern/repository locks, if any, are left intact - they cannot be faithfully restored by name, so a blanket 'zypper rl *' would destroy them irrecoverably)"; else echo "No package locks"; fi
```

Expected output: "No package locks" or "Removed the captured package-name locks (...)"
On failure: continue

### Step 4: Verify installed modules/extensions provide needed dependencies

```bash
SUSEConnect --list-extensions 2>&1 | grep -E "Activated|Not Activated" | head -20; echo "---"; zypper --non-interactive verify 2>&1 | head -20; echo "Modules checked"
```

Expected output: Module status
On failure: continue

### Step 5: Allow vendor changes for patches

> **CAUTION:** `--allow-vendor-change` lets zypper silently switch a package's vendor (e.g. from SUSE to a third-party repo, or vice versa). This can replace supported SUSE packages with third-party builds without prompting and may affect support status. Confirm the vendor changes in the output and revert with `zypper dup --allow-vendor-change` back to the desired vendor if any switch is unwanted.

```bash
zypper --non-interactive --no-confirm patch --allow-vendor-change --with-interactive 2>&1 | tail -10; echo "Patch attempt exit: ${PIPESTATUS[0]}"
```

Expected output: Patch results
On failure: continue

### Step 6: Verify zypper state

```bash
zypper --non-interactive verify 2>&1; echo "Verify exit: $?"
```

Expected output: "Verify exit: 0"
On failure: abort

## Validation

```bash
zypper --non-interactive verify 2>&1 && zypper list-patches --category security 2>&1 | tail -5 && echo "ZYPPER STATE OK"
```

Expected: "ZYPPER STATE OK"

## Rollback

```bash
LOCK_FILE=/var/tmp/sop041-locks.txt
if [ -s "$LOCK_FILE" ]; then while read -r pkg; do [ -n "$pkg" ] && zypper al "$pkg" 2>/dev/null && echo "Lock restored: $pkg"; done < "$LOCK_FILE"; echo "Package locks restored from $LOCK_FILE"; else echo "No saved locks to restore (Step 3 records removed locks to $LOCK_FILE)"; fi
echo "Check /var/log/zypp/history for recent changes"
```

## Escalation

If zypper conflicts persist:
- Check if additional SUSE modules need activation: `SUSEConnect --list-extensions`
- Activate missing modules: `SUSEConnect -p <module/version/arch>`
- For orphaned packages: `zypper rm --clean-deps <orphaned-package>`
- Use `zypper install --force-resolution` to let zypper choose the best resolution
- For vendor change issues: `zypper dup --allow-vendor-change` (use with caution)
- Check if patterns enforce unwanted package versions: `zypper info -t pattern <pattern>`
