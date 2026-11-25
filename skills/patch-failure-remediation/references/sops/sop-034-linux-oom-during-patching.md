# SOP-034: Resolve Insufficient Memory (OOM) During Patching

| Field | Value |
|-------|-------|
| ID | SOP-034 |
| Category | oom_during_patching |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Package manager process killed mid-transaction (yum/dnf/apt/zypper disappears)
- "Cannot allocate memory" errors in patch output
- dmesg shows "Out of memory: Kill process" targeting yum/dnf/dpkg/apt
- Patch exits with signal 9 (SIGKILL) with no error message
- Transaction starts but instance becomes unresponsive during download/install phase
- SSM agent reports command timed out while package manager was OOM-killed
- "mmap() failed" errors during RPM database operations

## Root Cause

OOM conditions during patching when:

- Instance type has insufficient RAM for the number of packages being updated simultaneously
- Large transaction set (50+ packages) requires more memory than available for dependency resolution
- DNF/YUM metadata loading consumes excessive memory on systems with many repos
- Applications consuming most of available RAM leave insufficient for package manager
- No swap configured on the instance
- Memory leak in long-running applications combined with patch operation memory needs
- t2/t3 instances with CPU credits exhausted causing swap thrashing

## Related Failure Patterns

- SOP-032 (Incomplete Transaction) — OOM kills cause interrupted transactions
- SOP-004 (Corrupt RPM DB) — OOM during DB write corrupts the database

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available

## Diagnosis

Check memory state and OOM history:

```bash
free -h; echo "---"; dmesg -T 2>/dev/null | grep -i "out of memory\|oom\|killed process" | tail -10; echo "---"; cat /proc/meminfo | grep -E "MemTotal|MemAvailable|SwapTotal|SwapFree"
```

## Remediation Steps

### Step 1: Check current memory availability

```bash
free -m | awk '/Mem:/{printf "Total: %dMB, Available: %dMB, Used%%: %d%%\n", $2, $7, ($3/$2)*100}'; echo "---"; swapon -s 2>/dev/null || echo "No swap"
```

Expected output: Memory statistics
On failure: continue

### Step 2: Free memory by clearing caches

```bash
sync; echo 3 > /proc/sys/vm/drop_caches; free -m | awk '/Mem:/{printf "After cache drop - Available: %dMB\n", $7}'
```

Expected output: Available memory after cache drop
On failure: continue

### Step 3: Create temporary swap if none exists and memory is low

```bash
AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); SWAP=$(awk '/SwapTotal/{print int($2/1024)}' /proc/meminfo); if [ "$AVAIL" -lt 512 ] && [ "$SWAP" -lt 100 ]; then dd if=/dev/zero of=/var/swapfile bs=1M count=1024 2>/dev/null && chmod 600 /var/swapfile && mkswap /var/swapfile >/dev/null 2>&1 && swapon /var/swapfile 2>&1 && echo "Swap created: 1GB" || echo "Swap creation failed"; else echo "Sufficient memory ($AVAIL MB) or swap already exists ($SWAP MB)"; fi
```

Expected output: "Swap created: 1GB" or "Sufficient memory"
On failure: continue

### Step 4: Stop non-essential services temporarily

```bash
FREED=0; for svc in prometheus grafana-server elasticsearch splunkd; do if systemctl is-active --quiet $svc 2>/dev/null; then systemctl stop $svc 2>/dev/null && FREED=$((FREED+1)); fi; done; echo "Stopped $FREED non-essential services"; free -m | awk '/Mem:/{printf "Available now: %dMB\n", $7}'
```

Expected output: Services stopped and available memory
On failure: continue

### Step 5: Verify sufficient memory for patching (need at least 256MB free)

```bash
AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); if [ "$AVAIL" -ge 256 ]; then echo "MEMORY OK: ${AVAIL}MB available"; else echo "MEMORY INSUFFICIENT: ${AVAIL}MB available (need 256MB)"; exit 1; fi
```

Expected output: "MEMORY OK"
On failure: abort

## Validation

```bash
AVAIL=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); echo "Available: ${AVAIL}MB"; [ "$AVAIL" -ge 256 ] && echo "MEMORY SUFFICIENT FOR PATCHING" || echo "STILL LOW"
```

Expected: "MEMORY SUFFICIENT FOR PATCHING"

## Rollback

```bash
if [ -f /var/swapfile ]; then swapoff /var/swapfile 2>/dev/null; rm -f /var/swapfile; echo "Temporary swap removed"; fi
for svc in prometheus grafana-server elasticsearch splunkd; do systemctl start $svc 2>/dev/null; done; echo "Services restarted"
```

## Escalation

If memory cannot be freed sufficiently:
- Consider upgrading to a larger instance type before the next maintenance window
- Split the patch operation into smaller batches (fewer packages per transaction)
- For DNF: set `max_parallel_downloads=1` in /etc/dnf/dnf.conf to reduce memory usage
- Add persistent swap: create and enable a swap file in /etc/fstab
- Investigate which application is consuming excessive memory and whether it can be scheduled around the maintenance window
