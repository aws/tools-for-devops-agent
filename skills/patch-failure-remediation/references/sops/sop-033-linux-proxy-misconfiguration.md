# SOP-033: Resolve Proxy Misconfiguration Blocking Package Manager

| Field | Value |
|-------|-------|
| ID | SOP-033 |
| Category | proxy_misconfiguration |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | RHEL 8, RHEL 9, Oracle Linux 8, Oracle Linux 9, Ubuntu 20.04, Ubuntu 22.04, Ubuntu 24.04, SLES 15, Amazon Linux 2, Amazon Linux 2023 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- "Cannot retrieve repository metadata" with proxy-related error
- "407 Proxy Authentication Required" in yum/dnf/apt output
- "Connection refused" to port 3128/8080 (typical proxy ports)
- Package manager works when proxy env variables are unset but not when set
- "Could not connect to proxy" or "Proxy CONNECT aborted"
- apt fails with "407 Proxy Authentication Required" while curl works
- "The proxy server received an invalid response from an upstream server"
- Packages download partially then fail (proxy buffering/timeout issues)

## Root Cause

Proxy misconfiguration blocking package operations when:

- Proxy server address changed or decommissioned but package manager config still references old proxy
- Proxy credentials expired or rotated
- http_proxy/https_proxy environment variables set globally but proxy only supports HTTP (not HTTPS)
- Package manager has its own proxy config separate from environment variables
- no_proxy not set for AWS metadata endpoints (169.254.169.254) or internal repos
- Squid/corporate proxy denies access to specific repository domains
- Proxy certificate not trusted by the system CA bundle
- Instance moved from private subnet (needs proxy) to public subnet (should not use proxy) or vice versa

## Related Failure Patterns

- SOP-003 (Network Unreachable) — proxy issues are a common subset of connectivity failures
- SOP-031 (Expired Certificates) — proxy SSL interception can cause certificate issues

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Knowledge of network topology (does instance require a proxy to reach internet?)

## Diagnosis

Check proxy configuration across all locations:

```bash
echo "=== Environment ==="; env | grep -i proxy; echo "=== /etc/environment ==="; cat /etc/environment 2>/dev/null | grep -i proxy; echo "=== YUM/DNF ==="; grep -i proxy /etc/yum.conf /etc/dnf/dnf.conf 2>/dev/null; echo "=== APT ==="; cat /etc/apt/apt.conf.d/*proxy* 2>/dev/null; grep -ri proxy /etc/apt/apt.conf 2>/dev/null; echo "=== Zypper ==="; grep -i proxy /etc/sysconfig/proxy 2>/dev/null
```

## Remediation Steps

### Step 1: Identify current proxy configuration

```bash
echo "ENV:"; env | grep -i proxy || echo "  (none)"; echo "YUM/DNF:"; grep -ih "^proxy" /etc/yum.conf /etc/dnf/dnf.conf 2>/dev/null || echo "  (none)"; echo "APT:"; grep -rih "proxy" /etc/apt/apt.conf /etc/apt/apt.conf.d/ 2>/dev/null || echo "  (none)"; echo "SUSE:"; grep -i "PROXY_ENABLED" /etc/sysconfig/proxy 2>/dev/null || echo "  (none)"; echo "Config identified"
```

Expected output: Proxy configuration from all sources
On failure: continue

### Step 2: Test connectivity with and without proxy

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); if [ -n "$REGION" ]; then PROBE_HOST="amazonlinux.${REGION}.amazonaws.com"; else PROBE_HOST="cdn.amazonlinux.com"; echo "NOTE: region unavailable from IMDS (plausible when a proxy is intercepting or blocking traffic to the metadata endpoint) - falling back to region-agnostic probe $PROBE_HOST; continuing (do NOT abort - this is the proxy SOP)"; fi; echo "=== Direct ==="; curl -sf --noproxy '*' --connect-timeout 5 https://${PROBE_HOST}/ >/dev/null && echo "Direct: OK" || echo "Direct: FAILED"; echo "=== Via proxy ==="; curl -sf --connect-timeout 5 https://${PROBE_HOST}/ >/dev/null && echo "Proxy: OK" || echo "Proxy: FAILED"
```

Expected output: Connectivity status
On failure: continue

### Step 3: Fix proxy configuration for package manager (RPM-based)

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); if [ -n "$REGION" ]; then PROBE_HOST="amazonlinux.${REGION}.amazonaws.com"; else PROBE_HOST="cdn.amazonlinux.com"; echo "NOTE: region unavailable from IMDS (plausible when a proxy is intercepting or blocking traffic to the metadata endpoint) - falling back to region-agnostic probe $PROBE_HOST; continuing (do NOT abort - this is the proxy SOP)"; fi; if grep -q "^proxy=" /etc/dnf/dnf.conf 2>/dev/null || grep -q "^proxy=" /etc/yum.conf 2>/dev/null; then CONF=$(test -f /etc/dnf/dnf.conf && echo /etc/dnf/dnf.conf || echo /etc/yum.conf); PROXY_LINE=$(grep "^proxy=" "$CONF"); echo "Current proxy: $PROXY_LINE"; if curl -sf --noproxy '*' --connect-timeout 5 https://${PROBE_HOST}/ >/dev/null 2>&1; then sed -i 's/^proxy=/#proxy=/' "$CONF"; echo "Proxy disabled (direct works)"; else echo "Direct access failed - proxy may still be needed"; fi; else echo "No package manager proxy configured"; fi
```

Expected output: Proxy status update
On failure: continue

### Step 4: Fix proxy configuration for APT (Debian-based)

```bash
if [ -d /etc/apt/apt.conf.d ]; then if curl -sf --noproxy '*' --connect-timeout 5 https://archive.ubuntu.com/ >/dev/null 2>&1; then TS=$(date +%Y%m%d%H%M%S); for f in /etc/apt/apt.conf.d/90proxy /etc/apt/apt.conf.d/95proxy; do [ -f "$f" ] && mv "$f" "${f}.${TS}.bak" && echo "Backed up: ${f}.${TS}.bak"; done; echo "APT proxy removed (direct works)"; else echo "Direct access failed - checking proxy validity"; fi; else echo "Not Debian-based"; fi
```

Expected output: APT proxy status
On failure: continue

### Step 5: Ensure no_proxy includes AWS metadata endpoints

```bash
if env | grep -qi proxy; then CURRENT_NO=$(echo $no_proxy); if ! echo "$CURRENT_NO" | grep -q "169.254.169.254"; then export no_proxy="${CURRENT_NO:+$CURRENT_NO,}169.254.169.254,169.254.170.2"; echo "no_proxy updated: $no_proxy"; else echo "no_proxy already includes metadata"; fi; else echo "No proxy env set"; fi
```

Expected output: no_proxy status
On failure: continue

### Step 6: Verify package manager can reach repositories

```bash
if command -v dnf &>/dev/null; then dnf makecache 2>&1 | tail -3; echo "Exit: ${PIPESTATUS[0]}"; elif command -v yum &>/dev/null; then yum makecache 2>&1 | tail -3; echo "Exit: ${PIPESTATUS[0]}"; elif command -v apt-get &>/dev/null; then apt-get update 2>&1 | tail -5; echo "Exit: ${PIPESTATUS[0]}"; elif command -v zypper &>/dev/null; then zypper refresh 2>&1 | tail -3; echo "Exit: ${PIPESTATUS[0]}"; fi
```

Expected output: "Exit: 0"
On failure: abort

## Validation

```bash
if command -v dnf &>/dev/null; then dnf repolist 2>&1 && echo "PROXY CONFIG OK"; elif command -v apt-get &>/dev/null; then apt-get update -qq 2>&1 && echo "PROXY CONFIG OK"; elif command -v zypper &>/dev/null; then zypper refresh 2>&1 && echo "PROXY CONFIG OK"; fi
```

Expected: "PROXY CONFIG OK"

## Rollback

```bash
if [ -f /etc/dnf/dnf.conf ]; then sed -i 's/^#proxy=/proxy=/' /etc/dnf/dnf.conf; echo "DNF proxy re-enabled"; fi
if [ -f /etc/yum.conf ]; then sed -i 's/^#proxy=/proxy=/' /etc/yum.conf; echo "YUM proxy re-enabled"; fi
for base in /etc/apt/apt.conf.d/90proxy /etc/apt/apt.conf.d/95proxy; do BAK=$(ls -1t ${base}.*.bak 2>/dev/null | head -1); if [ -n "$BAK" ] && [ ! -f "$base" ]; then mv "$BAK" "$base" && echo "APT proxy restored: $base"; fi; done
```

## Escalation

If proxy issues persist:
- Verify proxy server is operational: `curl -v -x http://proxy:3128 https://example.com`
- Check if proxy requires NTLM authentication (common in corporate environments)
- For HTTPS interception proxies, the proxy CA certificate may need to be added to the system trust store
- Verify security group allows outbound to proxy IP and port
- Consider configuring a VPC endpoint for S3/package repos to bypass proxy entirely
