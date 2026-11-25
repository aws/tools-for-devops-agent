# SOP-025: Resolve Corrupt dpkg Updates Journal Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-025 |
| Category | corrupt_dpkg |
| Severity | High |
| Risk Level | High |
| Platforms | Linux |
| Distributions | Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, Debian 11, Debian 12 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch fails with "dpkg: error: parsing file '/var/lib/dpkg/updates/XXXX' near line 0: end of file after field name"
- "dpkg was interrupted, you must manually run 'dpkg --configure -a' to correct the problem"
- `dpkg --configure -a` itself fails due to corrupt journal files in /var/lib/dpkg/updates/
- APT operations fail with "E: dpkg was interrupted" before reaching repository checks
- DPKG configure exits with code 2
- APT sources returning DNS resolution failures compounding the dpkg corruption

## Root Cause

Corrupt dpkg updates journal files occur when:

- A previous dpkg operation was interrupted mid-write (OOM kill, power loss, forced termination)
- Partial writes to /var/lib/dpkg/updates/ directory left truncated or zero-byte journal files
- Disk I/O errors during package installation corrupted the pending updates journal
- The /var/lib/dpkg/updates/ directory contains files that dpkg cannot parse, blocking all subsequent package operations
- Network-related APT failures (DNS resolution errors, unreachable repositories) may co-occur but are secondary to the dpkg journal corruption

## Related Failure Patterns

- SOP-014 (Ubuntu Lock) — lock issues and interrupted dpkg share similar initial symptoms
- SOP-003 (Network Unreachable) — DNS resolution failures may compound this issue

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Root access available via SSM
- /var/lib/dpkg directory exists and is accessible

## Diagnosis

Inspect the corrupt journal files:

```bash
ls -la /var/lib/dpkg/updates/; file /var/lib/dpkg/updates/* 2>/dev/null; cat /var/lib/dpkg/updates/* 2>&1 | head -20
```

Confirm dpkg is broken:

```bash
dpkg --configure -a 2>&1 | head -10; echo "EXIT:$?"
```

## Remediation Steps

### Step 1: Remove corrupt dpkg updates journal files

```bash
BK=/var/lib/dpkg/updates.bak.$(date +%Y%m%d%H%M%S); mkdir -p "$BK" && cp -a /var/lib/dpkg/updates/. "$BK"/ && echo "Backed up updates journal to $BK" || { echo "ERROR: backup of updates journal failed - NOT removing journal files (originals preserved); escalate"; exit 1; }; rm -f /var/lib/dpkg/updates/* && echo 'Corrupt updates removed' || { echo "ERROR: removal of journal files failed (backup preserved at $BK); escalate"; exit 1; }
```

Expected output: "Corrupt updates removed"
On failure: abort (permissions issue or filesystem read-only)

The /var/lib/dpkg/updates/ directory holds pending package state changes. Corrupt entries here prevent dpkg from processing any operations. Removing them discards incomplete transactions that were never committed to the main status database.

### Step 2: Re-run dpkg configure to fix interrupted state

```bash
dpkg --configure -a 2>&1; echo "DPKG configure exit: $?"
```

Expected output: "DPKG configure exit: 0"
On failure: abort

### Step 3: Verify package manager is functional

```bash
apt-get check 2>&1 && echo 'APT OK'
```

Expected output: "APT OK"
On failure: abort

## Validation

```bash
dpkg --configure -a 2>&1 && apt-get check 2>&1 && echo "DPKG and APT OK"
```

Expected: "DPKG and APT OK" with exit code 0

## Rollback

The removed journal files were backed up to the timestamped `/var/lib/dpkg/updates.bak.<timestamp>` directory created in Step 1. They represent incomplete transactions that were already corrupt, so restoring them is rarely useful; if needed for forensic inspection, the originals can be copied back from that backup directory. If package state is inconsistent after remediation:

```bash
apt-get install -f 2>&1; echo "Attempted dependency fix: $?"
```

## Escalation

If `dpkg --configure -a` still fails after clearing the updates directory:
- Check if /var/lib/dpkg/status itself is corrupt: `dpkg --audit 2>&1`
- Restore /var/lib/dpkg/status from backup: `cp /var/lib/dpkg/status-old /var/lib/dpkg/status`
- For DNS/repository issues compounding the problem, address network connectivity separately per SOP-003
- If the dpkg database is irrecoverably corrupt, consider restoring from a recent AMI or EBS snapshot
- The original updates journal is preserved under `/var/lib/dpkg/updates.bak.<timestamp>` (from Step 1) for inspection or restoration if the removal is later suspected to have discarded needed state
