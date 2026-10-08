# Patch timeout / maintenance window exceeded

**Signatures:** `TimedOut` / `DeliveryTimedOut`, "Execution timed out", the op starts but never
completes in the window, 100+ pending packages can't download+install in time, partial patch state,
"Command delivery timed out" before install begins, execution exceeds `maxTimeoutSeconds`.

**Root cause:** the window duration is too short for the patch volume/bandwidth — NOT a code defect.
Common contributors: large packages (kernel/glibc/firmware), slow repo throughput, many configured
repos, burstable instance (t2/t3) out of CPU credits, a backlog from a prior failed window, or
concurrent `unattended-upgrades`/`yum-cron` competing for bandwidth and locks.

## Diagnose volume + speed
```bash
if command -v dnf &>/dev/null; then dnf check-update -q 2>&1 | wc -l; elif command -v apt-get &>/dev/null; then apt-get -s upgrade 2>&1 | grep -c '^Inst'; fi
curl -o /dev/null -s -w "download: %{speed_download} B/s\n" https://amazonlinux.us-east-1.amazonaws.com/2/core/latest/x86_64/mirror.list
```

## Optimize (after clearing any interrupted state)
```bash
# 1. fix interrupted state from the prior timeout:
if command -v dnf &>/dev/null; then dnf clean all; elif command -v apt-get &>/dev/null; then dpkg --configure -a; apt-get install -f -y; fi
# 2. parallel downloads / fastest mirror:
if command -v dnf &>/dev/null; then grep -q max_parallel_downloads /etc/dnf/dnf.conf || echo 'max_parallel_downloads=10' >> /etc/dnf/dnf.conf; grep -q fastestmirror /etc/dnf/dnf.conf || echo 'fastestmirror=True' >> /etc/dnf/dnf.conf; fi
# 3. pre-download to separate download from install time:
if command -v dnf &>/dev/null; then dnf makecache; elif command -v apt-get &>/dev/null; then apt-get update -qq; apt-get -d upgrade -y; fi
```

## Recommendation by volume
- **100+ pending** → split into multiple windows; apply **security-first** (`dnf update --security`) then the rest.
- **< 100** → should complete within a standard window after optimization.

## Escalation
- Increase the SSM maintenance-window duration (default 3600s is often too short for 100+ packages).
- Bandwidth-limited: pre-stage packages via S3 or a VPC-local yum/apt mirror/proxy.
- Verify the instance type's network baseline (t2.micro is limited); schedule off-peak.
- Rollback the tuning if needed: remove `/etc/apt/apt.conf.d/99parallel`, strip the added dnf.conf lines.
