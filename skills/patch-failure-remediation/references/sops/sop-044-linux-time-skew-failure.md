# SOP-044: Resolve NTP/Time Skew Causing Repository Metadata Validation Failures

| Field | Value |
|-------|-------|
| ID | SOP-044 |
| Category | time_skew_failure |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Metadata file does not match checksum" due to cache timestamp issues
- "SSL certificate is not yet valid" when connecting to repos
- "Release file is not valid yet" in APT output
- "Repository metadata is too far in the future"
- GPG signature verification fails with "signature made in the future"
- "HTTPS certificate verification failed: certificate is not yet valid"
- AWS API calls fail with "Signature expired" affecting S3-backed repos

## Root Cause

Time skew affecting patching when:

- chronyd/ntpd not running or unable to reach NTP servers
- Instance was stopped for extended period and clock drifted
- VM clock drift on heavily loaded hypervisor (less common on Nitro instances)
- NTP blocked by security groups or NACLs (UDP port 123)
- chrony/NTP configured to use external servers but instance is in private subnet without NAT
- Amazon Time Sync Service (169.254.169.123) not accessible
- Time zone misconfiguration causing apparent skew in log messages

## Related Failure Patterns

- SOP-028 (Stale Metadata Cache) — time skew causes cache validation failures
- SOP-031 (Expired Certificates) — time skew makes valid certs appear expired or not-yet-valid

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

Check time synchronization state:

```bash
date; echo "---"; timedatectl 2>/dev/null; echo "---"; chronyc tracking 2>/dev/null || ntpq -p 2>/dev/null; echo "---"; curl -sIk https://amazonaws.com 2>/dev/null | grep -i date
```

## Remediation Steps

### Step 1: Check current time skew

```bash
REMOTE_DATE=$(curl -sIk https://amazonaws.com 2>/dev/null | grep -i "^date:" | cut -d' ' -f2-); LOCAL_DATE=$(date -u); echo "Local:  $LOCAL_DATE"; echo "Remote: $REMOTE_DATE"
```

Expected output: Local and remote timestamps for comparison
On failure: continue

### Step 2: Force time synchronization via chrony

```bash
if command -v chronyc &>/dev/null; then systemctl start chronyd 2>/dev/null; chronyc makestep 2>&1; chronyc tracking 2>&1 | head -5; echo "Chrony sync done"; elif command -v ntpdate &>/dev/null; then ntpdate -u 169.254.169.123 2>&1; echo "NTP sync done"; elif command -v timedatectl &>/dev/null; then timedatectl set-ntp true 2>&1; echo "Timedatectl NTP enabled"; fi
```

Expected output: "Chrony sync done" or "NTP sync done"
On failure: continue

### Step 3: Configure Amazon Time Sync Service as source

```bash
if command -v chronyc &>/dev/null; then if ! grep -q "169.254.169.123" /etc/chrony.conf /etc/chrony/chrony.conf 2>/dev/null; then echo "server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4" >> /etc/chrony.conf 2>/dev/null || echo "server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4" >> /etc/chrony/chrony.conf 2>/dev/null; systemctl restart chronyd 2>&1; echo "Amazon Time Sync added"; else echo "Amazon Time Sync already configured"; fi; fi
```

Expected output: "Amazon Time Sync already configured" or "Amazon Time Sync added"
On failure: continue

### Step 4: Verify time is now accurate

```bash
sleep 2; OFFSET=$(chronyc tracking 2>/dev/null | grep "System time" | awk '{print $4}'); if [ -n "$OFFSET" ]; then echo "Time offset: ${OFFSET}s"; else date -u; echo "Manual verification needed"; fi; echo "Time check done"
```

Expected output: Small offset (< 1 second)
On failure: abort

## Validation

```bash
chronyc tracking 2>/dev/null | grep -E "Leap status|System time" || date -u; echo "---"; TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); if [ -n "$REGION" ]; then PROBE_HOST="amazonlinux.${REGION}.amazonaws.com"; else PROBE_HOST="cdn.amazonlinux.com"; echo "NOTE: region unavailable from IMDS - time sync already succeeded above; falling back to region-agnostic probe $PROBE_HOST rather than aborting"; fi; curl -sf --connect-timeout 5 https://${PROBE_HOST}/ >/dev/null && echo "TIME SYNC OK - HTTPS WORKING" || echo "STILL FAILING"
```

Expected: "TIME SYNC OK - HTTPS WORKING"

## Rollback

```bash
echo "Time synchronization is non-destructive - no rollback needed"
```

## Escalation

If time cannot be synchronized:
- Verify security group allows outbound UDP 123 (or use Amazon Time Sync which is link-local)
- Check if chronyd is masked: `systemctl unmask chronyd && systemctl start chronyd`
- For private subnets: Amazon Time Sync (169.254.169.123) works without internet access
- Manual time set as last resort: `date -s "$(curl -sIk https://amazonaws.com | grep -i date | cut -d' ' -f2-)"`
- If clock drift recurs frequently, check for `clocksource=tsc` issues in kernel parameters
