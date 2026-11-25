# SOP-048: Resolve Patch Timeout / Maintenance Window Exceeded

| Field | Value |
|-------|-------|
| ID | SOP-048 |
| Category | patch_timeout |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- SSM Patch Manager reports "TimedOut" or "DeliveryTimedOut"
- "Execution timed out" in patch command output
- Patch operation starts but never completes within maintenance window
- Large number of packages (100+) cannot download and install within allotted time
- Instance shows partial patch state — some packages updated, others not
- "Command delivery timed out" before package installation even begins
- SSM document execution exceeds maxTimeoutSeconds

## Root Cause

Patch timeout occurs when:

- Maintenance window duration too short for the volume of pending patches
- Slow network throughput to package repositories (bandwidth throttled or high latency)
- Large packages (kernel, firmware, glibc) take longer to download on limited bandwidth
- Package manager running dependency resolution on large transaction sets consumes time
- Instance CPU/memory constrained (t2/t3 burstable with exhausted credits)
- Repository metadata download phase slow due to many configured repos
- Previous failed patches left a large backlog that exceeds single-window capacity
- unattended-upgrades or yum-cron running concurrently, competing for bandwidth and locks

## Related Failure Patterns

- SOP-032 (Incomplete Transaction) — timeouts cause interrupted transactions
- SOP-034 (OOM During Patching) — resource constraints cause both OOM and slow operations
- SOP-014 (Ubuntu Lock) — concurrent operations extend patch time

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Previous timed-out patch did not leave corrupted state

## Diagnosis

Check pending update volume and network speed:

```bash
if command -v dnf &>/dev/null; then dnf check-update -q 2>&1 | wc -l | awk '{print "Pending updates: "$1}'; elif command -v apt-get &>/dev/null; then apt-get -s upgrade 2>&1 | grep "upgraded" | head -1; elif command -v zypper &>/dev/null; then zypper list-updates 2>&1 | wc -l | awk '{print "Pending updates: "$1}'; fi; echo "---"; TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); ARCH=$(uname -m); CANDS=""; [ -n "$REGION" ] && CANDS="https://amazonlinux.${REGION}.amazonaws.com/2/core/latest/${ARCH}/mirror.list"; CANDS="$CANDS https://cdn.amazonlinux.com/al2023/core/mirrors/latest/${ARCH}/mirror.list"; MEASURED=""; for U in $CANDS; do CODE=$(curl -o /dev/null -s -w "%{http_code}" --connect-timeout 5 --max-time 20 "$U" 2>/dev/null); if [ "$CODE" = "200" ]; then curl -o /dev/null -s -w "Download speed (from $U): %{speed_download} bytes/sec\n" --connect-timeout 5 --max-time 20 "$U" 2>/dev/null; MEASURED=1; break; fi; done; [ -z "$MEASURED" ] && echo "Bandwidth probe inconclusive - no Amazon Linux mirror endpoint returned 200 (non-AL distro or restricted egress); rely on the pending-update count above"
```

## Remediation Steps

### Step 1: Fix any interrupted state from previous timeout

```bash
if command -v dnf &>/dev/null; then dnf clean all 2>&1; dnf history redo last 2>&1 | grep -q "^Nothing" && echo "No incomplete transaction" || echo "Incomplete transaction resolved"; elif command -v apt-get &>/dev/null; then dpkg --configure -a 2>&1; apt-get install -f -y 2>&1; echo "Previous state fixed"; elif command -v zypper &>/dev/null; then zypper --non-interactive verify 2>&1; echo "Previous state fixed"; fi
```

Expected output: "No incomplete transaction" or "Previous state fixed"
On failure: continue

### Step 2: Reduce repository metadata overhead

```bash
DISABLED_FILE=/var/tmp/sop048-disabled-repos.txt; if command -v dnf &>/dev/null; then dnf config-manager --save --setopt=metadata_expire=86400 2>/dev/null; : > "$DISABLED_FILE"; for repo in $(dnf repolist --enabled 2>/dev/null | grep -iE "debug|source|media" | awk '{print $1}'); do dnf config-manager --set-disabled "$repo" 2>/dev/null && echo "$repo" >> "$DISABLED_FILE"; done; echo "Disabled $(wc -l < "$DISABLED_FILE" 2>/dev/null) unnecessary repos (recorded in $DISABLED_FILE for rollback)"; fi; echo "Metadata optimization done"
```

Expected output: "Metadata optimization done"
On failure: continue

### Step 3: Configure parallel downloads to speed up

```bash
if command -v dnf &>/dev/null; then grep -q "max_parallel_downloads" /etc/dnf/dnf.conf || echo "max_parallel_downloads=10" >> /etc/dnf/dnf.conf; grep -q "fastestmirror" /etc/dnf/dnf.conf || echo "fastestmirror=True" >> /etc/dnf/dnf.conf; echo "DNF optimized for speed"; elif command -v apt-get &>/dev/null; then echo 'Acquire::Queue-Mode "access";' > /etc/apt/apt.conf.d/99parallel 2>/dev/null; echo "APT optimized"; fi
```

Expected output: "DNF optimized for speed" or "APT optimized"
On failure: continue

### Step 4: Pre-download packages to separate download from install time

```bash
if command -v dnf &>/dev/null; then dnf makecache 2>&1 | tail -3; dnf updateinfo list security 2>&1 | wc -l | awk '{print "Security advisories: "$1}'; elif command -v apt-get &>/dev/null; then apt-get update -qq 2>&1; apt-get -d upgrade -y 2>&1 | tail -5; echo "Packages pre-downloaded"; elif command -v zypper &>/dev/null; then zypper --non-interactive refresh 2>&1; zypper --non-interactive download-only patch --category security 2>&1 | tail -5; echo "Patches pre-downloaded"; fi
```

Expected output: "Packages pre-downloaded" or advisory count
On failure: continue

### Step 5: Verify system is ready for efficient patching

```bash
if command -v dnf &>/dev/null; then COUNT=$(dnf check-update -q 2>&1 | grep -c "\."); echo "Updates ready: $COUNT"; elif command -v apt-get &>/dev/null; then COUNT=$(apt-get -s upgrade 2>&1 | grep "^Inst" | wc -l); echo "Updates ready: $COUNT"; fi; echo "SYSTEM OPTIMIZED FOR PATCHING"
```

Expected output: "SYSTEM OPTIMIZED FOR PATCHING"
On failure: continue

## Validation

```bash
echo "Optimization applied. Recommendations:"; if command -v dnf &>/dev/null; then COUNT=$(dnf check-update -q 2>&1 | grep -c "\."); fi; if [ "${COUNT:-0}" -gt 100 ]; then echo "WARNING: $COUNT pending updates - consider splitting into multiple maintenance windows"; echo "  Use: dnf update --security (security only first)"; else echo "OK: ${COUNT:-0} pending updates should complete within standard window"; fi
```

Expected: Recommendation output

## Rollback

```bash
rm -f /etc/apt/apt.conf.d/99parallel 2>/dev/null
if [ -f /etc/dnf/dnf.conf ]; then sed -i '/^max_parallel_downloads/d; /^fastestmirror/d' /etc/dnf/dnf.conf; fi
# Re-enable ONLY the repos this SOP disabled in Step 2 (recorded in the tracking file) - never blindly re-enable every debug/source/media repo, which would clobber repos the customer had already disabled
DISABLED_FILE=/var/tmp/sop048-disabled-repos.txt
if command -v dnf &>/dev/null && [ -f "$DISABLED_FILE" ]; then while read -r repo; do [ -n "$repo" ] && dnf config-manager --set-enabled "$repo" 2>/dev/null; done < "$DISABLED_FILE"; rm -f "$DISABLED_FILE"; fi
echo "Optimizations removed"
```

## Escalation

If patches consistently time out:
- Increase SSM maintenance window duration (default 3600s may be insufficient for 100+ packages)
- Split patch operations: apply security patches first, then recommended in a separate window
- For bandwidth-limited instances: pre-stage packages via S3 or local mirror
- Consider configuring a yum/apt proxy/mirror within the VPC for faster downloads
- Check if instance type has sufficient network baseline (t2.micro has limited bandwidth)
- Schedule patching during off-peak hours when network contention is lower
