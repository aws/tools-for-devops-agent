# SOP-078: Repair Corrupt dpkg Status File and Remove Broken APT Sources

| Field | Value |
|-------|-------|
| ID | SOP-078 |
| Category | apt_broken_sources_dpkg_status_corrupt |
| Severity | High |
| Risk Level | Medium |
| Platforms | Linux |
| Distributions | Ubuntu 20.04 (Focal), Ubuntu 22.04 (Jammy), Ubuntu 24.04 (Noble) |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | DRAFT - pending human review |

## Symptoms

- `dpkg` reports a parse error near a specific line in `/var/lib/dpkg/status`, e.g.: `parsing file '/var/lib/dpkg/status' near line 14477 package 'zstd': end of file during value of field 'Homepage' (missing final newline)`
- `dpkg` was interrupted and requires manual intervention: `E: dpkg was interrupted, you must manually run 'dpkg --configure -a' to correct the problem.`
- One or more APT sources fail to resolve with DNS error `-5 - No address associated with hostname`, indicating unreachable or stale third-party repository entries under `/etc/apt/sources.list.d/`
- `apt-get update` produces `W: Some index files failed to download. They have been ignored, or old ones used instead.`
- Patch remediation automation exits non-zero, halting the patching pipeline

## Root Cause

Two compounding issues are present simultaneously:

- **Corrupt dpkg status file:** `/var/lib/dpkg/status` is truncated or missing a final newline at the end of a package stanza (observed at the `Homepage` field of the `zstd` package). This typically results from a prior interrupted `dpkg` or `apt` operation (e.g., a VM snapshot, power interruption, or a failed SSM Run Command session) that left the status file partially written. dpkg cannot parse the file and refuses to proceed with any package operations.
- **Broken APT source entries:** One or more `.list` files under `/etc/apt/sources.list.d/` reference a hostname that does not resolve via DNS. These stale or misconfigured third-party repository entries cause `apt-get update` to emit fetch failures, which can in turn cause patching workflows to fail if they treat warnings or partial failures as errors.

Together these issues prevent both `dpkg` from configuring pending packages and `apt` from refreshing its index, blocking all subsequent patch installation.

## Related Failure Patterns

- `apt_dpkg_interrupted` — covers interrupted dpkg without accompanying source corruption; the dpkg recovery steps in this SOP are a superset of that procedure
- `apt_broken_sources_unresolvable_repo` — covers unresolvable repository sources in isolation, without dpkg status corruption

## Prerequisites

- Instance is reachable via AWS Systems Manager (SSM) Session Manager or SSM Run Command; SSH access is not required but may be used as a fallback
- The SSM agent is running and the instance profile grants `ssm:SendCommand` and `ssm:StartSession`
- The operator executing this SOP has been granted IAM permissions to invoke SSM Run Command on the target instance
- The file `/var/lib/dpkg/status-old` exists and is readable; if it does not exist the manual escalation path in the Escalation section must be followed before proceeding (note: `status-old` is written by dpkg itself on each successful status update and is normally present on any instance that has had at least one successful package operation)
- Sufficient disk space exists on the filesystem hosting `/var/lib/dpkg/` to hold a backup copy of the status file (conservatively, at least 2× the size of the existing status file)
- The instance has outbound HTTPS connectivity to the Ubuntu archive mirrors that will be used after broken sources are removed (e.g., the default AWS regional Ubuntu mirrors or `archive.ubuntu.com`)

## Diagnosis

Verify the dpkg status file is parseable and check for truncation or missing newline:

```bash
tail -5 /var/lib/dpkg/status && echo "STATUS_FILE_TAIL_OK" || echo "STATUS_FILE_READ_ERROR"
```

Confirm the dpkg interrupted-state flag is set:

```bash
ls /var/lib/dpkg/updates/ && cat /var/lib/dpkg/updates/* 2>/dev/null || echo "NO_PENDING_UPDATES"
```

Identify unreachable hosts by running apt-get update and extracting failing hostnames:

```bash
BROKEN_HOSTS=$(apt-get update 2>&1 | grep -oP "(?<=resolving ')[^':]+" | sort -u)
echo "Unreachable hosts: $BROKEN_HOSTS"
```

Check whether `status-old` exists and is non-empty and can serve as a recovery baseline:

```bash
test -s /var/lib/dpkg/status-old && echo "STATUS_OLD_PRESENT_AND_NON_EMPTY" || echo "STATUS_OLD_MISSING_OR_EMPTY"
```

Check for any packages left in a half-configured or half-installed state:

```bash
dpkg --audit 2>&1 | head -40
```

## Remediation Steps

### Step 1: Back up the corrupt dpkg status file

```bash
cp /var/lib/dpkg/status /var/lib/dpkg/status.bak
```

Expected output: (no output on success; the file `/var/lib/dpkg/status.bak` is created)

On failure: abort — if the backup cannot be written (e.g., disk full), do not proceed; resolve disk space before continuing

---

### Step 2: Restore dpkg status from the previous known-good copy

```bash
cp /var/lib/dpkg/status-old /var/lib/dpkg/status 2>/dev/null || { echo "STATUS_OLD_MISSING_CANNOT_RESTORE"; exit 1; }
```

Expected output: (no output on success); if `status-old` is absent the command emits `STATUS_OLD_MISSING_CANNOT_RESTORE` and exits — follow the Escalation path

On failure: abort — without a valid status file dpkg cannot operate; do not attempt further steps

---

### Step 3: Configure all pending or half-configured packages

```bash
dpkg --configure -a --force-confdef 2>&1
```

Expected output: Zero or more lines describing package configuration actions; command exits 0. A non-zero exit indicates additional corruption beyond the scope of this SOP — follow the Escalation path.

On failure: abort

---

### Step 4: Fix broken package dependencies

```bash
apt-get install -f -y 2>&1
```

Expected output: `0 upgraded, 0 newly installed, 0 to remove and N not upgraded.` (counts may vary); exit code 0. Warnings about unreachable sources are acceptable at this stage; errors are not.

On failure: abort

---

### Step 5: Identify and remove broken source entries dynamically

Extract unreachable hostnames from the current APT errors and remove all source files referencing them:

```bash
# Extract failing hostnames from apt-get update output
BROKEN_HOSTS=$(apt-get update 2>&1 | grep -oP "(?<=resolving ')[^':]+" | sort -u)

if [ -z "$BROKEN_HOSTS" ]; then
  # Fallback: also catch "Could not resolve host" pattern
  BROKEN_HOSTS=$(apt-get update 2>&1 | grep -oP "Could not resolve host: \K[^\s']+" | sort -u)
fi

if [ -z "$BROKEN_HOSTS" ]; then
  echo "NO_BROKEN_HOSTS_DETECTED"
else
  echo "Broken hosts detected: $BROKEN_HOSTS"
  for host in $BROKEN_HOSTS; do
    echo "Removing sources referencing: $host"
    # Remove from sources.list.d
    grep -rl "$host" /etc/apt/sources.list.d/ 2>/dev/null | while read f; do
      echo "  Removing: $f"
      rm -f "$f"
    done
    # Remove from main sources.list.
    # Escape regex metacharacters in $host so dots match literally (not "any char") and no
    # unrelated line that merely contains the substring is deleted. Anchor to actual repo
    # lines (deb / deb-src) referencing the host, using '#' as the sed delimiter since URLs
    # contain '/'.
    esc_host=$(printf '%s' "$host" | sed 's/[.[\*^$/]/\\&/g')
    sed -i "\#^[[:space:]]*deb\(-src\)\?[[:space:]].*${esc_host}#d" /etc/apt/sources.list 2>/dev/null
  done
fi
```

Expected output: One or more lines indicating removed files per broken host. If `NO_BROKEN_HOSTS_DETECTED` is emitted, the sources issue may have already been resolved by prior steps.

On failure: continue — individual removal failures are non-fatal; the subsequent `apt-get update` will surface any remaining issues

---

### Step 6: Verify sources.list.d is clear of stale entries

```bash
echo "=== Remaining source files ==="
ls /etc/apt/sources.list.d/ 2>/dev/null || echo "SOURCES_LIST_D_EMPTY"
echo "=== Configured repositories ==="
grep -rh '^deb ' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null | awk '{print $2}' | sort -u
```

Expected output: Only known-good, reachable repository URLs should be listed. Any unexpected entries should be manually reviewed before proceeding.

On failure: continue — this is a diagnostic gate; the operator must review any listed files before proceeding

---

### Step 7: Refresh the APT package index

```bash
apt-get update 2>&1
```

Expected output: Lines beginning with `Get:` or `Hit:` for each configured repository, followed by `Reading package lists... Done`; no lines beginning with `E:` or `W: Failed to fetch`. Exit code 0.

On failure: abort — a failed index refresh means the remediation is incomplete; follow the Escalation path

---

**Note:** This SOP only remediates the dpkg corruption and broken APT sources. Patch installation is handled by the patching agent separately after this SOP completes successfully.

## Validation

```bash
dpkg --audit 2>&1 && \
  dpkg-query -l 2>/dev/null | grep -E '^(iF|rH|hH|pH)' | wc -l | xargs -I{} sh -c 'test {} -eq 0 || { echo "DPKG_BROKEN_COUNT: {}"; exit 1; }; echo "DPKG_NO_BROKEN_PACKAGES"' && \
  apt-get update 2>&1 | grep -c '^E:\|Failed to fetch' | xargs -I{} sh -c 'test {} -eq 0 || { echo "APT_SOURCES_STILL_BROKEN: {} errors"; exit 1; }; echo "APT_SOURCES_CLEAN"' && \
  echo "SOP-078 VALIDATION OK: dpkg status clean, APT index fresh, no broken packages, no broken sources"
```

## Rollback

If the remediation fails after Step 1 but before Step 3 (i.e., the status restore made things worse rather than better), restore the original corrupt status file from the backup taken in Step 1:

```bash
cp /var/lib/dpkg/status.bak /var/lib/dpkg/status
```

Note: restoring the corrupt file returns the system to its pre-remediation state, which is itself broken; this rollback only prevents further divergence and preserves the original evidence for escalation. No rollback is available for the removal of `.list` files performed in Step 5 — removed source entries must be re-added manually if they were intentional. For this reason, Step 6 includes a gate to review remaining sources before proceeding.

## Escalation

Escalate to a senior platform engineer or the on-call SRE if any of the following conditions are met:

- `/var/lib/dpkg/status-old` is absent or empty and the status file cannot be restored (Step 2 exits non-zero) — include the output of `tail -20 /var/lib/dpkg/status.bak` and `ls -lh /var/lib/dpkg/` to assess the extent of corruption
- `dpkg --configure -a` (Step 3) exits non-zero after the status restore — include the full output of `dpkg --configure -a 2>&1` and `dpkg --audit 2>&1`
- `apt-get update` (Step 7) still emits `E:` or `W: Failed to fetch` lines after broken sources have been removed — include `/etc/apt/sources.list`, the output of `ls /etc/apt/sources.list.d/`, and network connectivity evidence (`curl -I https://archive.ubuntu.com 2>&1`)
- The instance is part of an Auto Scaling Group — consider replacing the instance rather than remediating in place; include the instance ID, AMI ID, and launch template version in the escalation ticket

Data to include in all escalation tickets:
- Instance ID and AWS Region
- Full contents of `/var/lib/dpkg/status.bak` (or a compressed copy via SSM S3 upload)
- Output of `dpkg --audit 2>&1`
- Output of `apt-get update 2>&1` (unfiltered)
- Output of `ls -lh /var/lib/dpkg/` and `ls /etc/apt/sources.list.d/`
- SSM Run Command invocation ID for the failed remediation run
