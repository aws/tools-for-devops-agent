# SOP-032: Resolve Interrupted Patch Transaction / Incomplete Update

| Field | Value |
|-------|-------|
| ID | SOP-032 |
| Category | incomplete_transaction |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Amazon Linux 2, Amazon Linux 2023, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Transaction check error" from DNF/YUM with "file from install of X conflicts with file from package Y"
- "There are unfinished transactions remaining" from yum-complete-transaction
- Packages stuck in partial install state — headers installed but files missing
- "dpkg: error: dpkg status database is locked by another process" after crash
- "Half-installed" or "Half-configured" packages in dpkg status
- DNF history shows "Incomplete" transaction entries
- "RPMDB altered outside of dnf" warnings
- Previous patch maintenance window timed out mid-transaction

## Root Cause

Incomplete transactions occur when:

- SSM patch operation timed out during active package installation (maintenance window too short)
- Instance rebooted during package transaction (OOM kill, instance stop, spot termination)
- Network interruption during package download phase caused partial RPM/DEB writes
- yum/dnf process was killed while installing packages (SIGKILL)
- Power loss during transaction commit phase
- Previous remediation attempt partially completed before aborting

## Related Failure Patterns

- SOP-004 (Corrupt RPM DB) — interrupted transactions are a leading cause of DB corruption
- SOP-025 (Corrupt dpkg) — interrupted dpkg is the Debian equivalent
- SOP-014 (Ubuntu Lock) — locks may be left from incomplete transactions

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- No other package operations currently in progress
- Sufficient disk space for transaction completion

## Diagnosis

Check for incomplete transactions:

```bash
if command -v dnf &>/dev/null; then dnf history list --last 5 2>&1; dnf history info last 2>&1 | head -20; elif command -v yum &>/dev/null; then yum history list all | head -10; fi; echo "---"; dpkg --audit 2>/dev/null; echo "---"; cat /var/lib/yum/transaction-all* 2>/dev/null | head -5
```

## Remediation Steps

### Step 1: Identify incomplete transactions (RPM-based)

```bash
if command -v dnf &>/dev/null; then dnf history list --last 5 2>&1; echo "---"; test -f /var/lib/dnf/transaction 2>/dev/null && echo "Pending DNF transaction found" || echo "No pending DNF transaction"; elif command -v yum &>/dev/null; then yum history list all 2>&1 | head -10; fi; echo "Transaction check done"
```

Expected output: Transaction history
On failure: continue

### Step 2: Complete or rollback incomplete YUM/DNF transaction

> **CAUTION:** `distro-sync` aligns every package to the current repo versions and can downgrade/revert just-applied patches if the repo advertises older versions than what was partially installed; confirm no security patch is being rolled back.

```bash
if command -v dnf &>/dev/null; then dnf -y distro-sync 2>&1 | tail -10; echo "DNF distro-sync exit: ${PIPESTATUS[0]}"; elif command -v yum &>/dev/null; then if command -v yum-complete-transaction &>/dev/null; then yum-complete-transaction --cleanup-only 2>&1; fi; yum -y distro-sync 2>&1 | tail -10; echo "YUM distro-sync exit: ${PIPESTATUS[0]}"; fi
```

Expected output: Exit code 0
On failure: continue

### Step 3: Fix Debian/Ubuntu incomplete packages

```bash
if command -v dpkg &>/dev/null; then dpkg --configure -a 2>&1; apt-get install -f -y 2>&1; echo "DPKG fix exit: $?"; else echo "Not Debian-based"; fi
```

Expected output: "DPKG fix exit: 0"
On failure: continue

### Step 4: Fix SUSE incomplete transactions

```bash
if command -v zypper &>/dev/null; then zypper --non-interactive verify 2>&1; zypper --non-interactive dist-upgrade --dry-run 2>&1 | tail -5; echo "Zypper verify done"; else echo "Not SUSE"; fi
```

Expected output: "Zypper verify done"
On failure: continue

### Step 5: Clean duplicate packages (RPM-based)

> **NOTE:** Duplicate cleanup must never remove the currently running kernel. Keeping multiple kernel versions is expected; before removing any duplicate `kernel*` package, confirm it is not `$(uname -r)`. `package-cleanup`/`dnf remove --duplicates` normally keep the newest and running kernel, but verify no kernel matching the running version is removed.

```bash
if command -v package-cleanup &>/dev/null; then package-cleanup --dupes 2>&1; package-cleanup --cleandupes -y 2>&1; echo "Dupes cleaned"; elif command -v dnf &>/dev/null; then dnf remove --duplicates -y 2>&1; echo "Dupes cleaned"; else echo "Not applicable"; fi
```

Expected output: "Dupes cleaned"
On failure: continue

### Step 6: Verify package manager integrity

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1; echo "DNF check exit: $?"; elif command -v yum &>/dev/null; then yum check 2>&1; echo "YUM check exit: $?"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1; echo "APT check exit: $?"; elif command -v zypper &>/dev/null; then zypper verify 2>&1; echo "Zypper verify exit: $?"; fi
```

Expected output: Exit code 0
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf check 2>&1 && dnf check-update -q 2>&1 | wc -l && echo "TRANSACTION STATE OK"; elif command -v apt-get &>/dev/null; then apt-get check 2>&1 && dpkg --audit 2>&1 && echo "TRANSACTION STATE OK"; elif command -v zypper &>/dev/null; then zypper verify 2>&1 && echo "TRANSACTION STATE OK"; fi
```

Expected: "TRANSACTION STATE OK"

## Rollback

```bash
if command -v dnf &>/dev/null; then echo "To undo last transaction:"; dnf history list --last 3; echo "Run: dnf history undo <id>"; elif command -v yum &>/dev/null; then echo "To undo last transaction:"; yum history list all | head -5; echo "Run: yum history undo <id>"; fi
```

## Escalation

If incomplete transactions cannot be resolved:
- For RPM: `rpm --rebuilddb` and retry
- For severely broken RPM state: remove all duplicate packages manually, then `dnf distro-sync`
- For Debian: `dpkg --force-remove-reinstreq --remove <broken-package>` then reinstall
- Consider increasing the SSM maintenance window timeout to prevent future mid-transaction interruptions
- If the issue recurs, investigate if the instance is being OOM-killed during patching (`dmesg | grep -i oom`)
