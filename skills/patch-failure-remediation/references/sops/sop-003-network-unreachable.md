# SOP-003: Resolve Network/Repository Connectivity Issues During Patching

| Field | Value |
|-------|-------|
| ID | SOP-003 |
| Category | network_unreachable |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, Ubuntu 20.04, Ubuntu 22.04, RHEL 8, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 150 seconds |
| Last Validated | 2026-05-10 |

## Symptoms

- Patch fails with "Cannot retrieve repository metadata" or "Failed to connect"
- Timeout errors reaching package repositories
- DNS resolution failures for repository URLs
- HTTP 403/404 from repository endpoints
- "Could not resolve host" errors in yum/dnf/apt output
- "Connection timed out after 30001 milliseconds"
- SSL certificate verification failures connecting to repos

## Root Cause

Network connectivity issues during patching caused by:

- DNS resolution failures — resolver configuration wrong, VPC DNS settings disabled, or systemd-resolved misconfigured
- Security group or NACL blocking outbound HTTPS (port 443) to repository endpoints
- VPC endpoint misconfiguration for S3-backed YUM/APT repos (gateway endpoint route missing from route table)
- Proxy configuration not set for package manager when instance is in a private subnet
- Repository URL changes or temporary AWS infrastructure outages
- IMDSv2 hop limit set to 1 on containerized instances causing metadata failures
- Route table missing NAT gateway or internet gateway route for private subnets
- iptables/nftables rules blocking outbound traffic added by security tooling

## Related Failure Patterns

This SOP commonly overlaps with:
- SOP-007 (AWS CLI Credentials) — network issues can masquerade as credential failures when S3-backed repos return 403
- SOP-011 (RHUI CDS) — RHUI-specific connectivity is a subset of this general pattern
- SOP-016 (WPAD Proxy) — Windows equivalent of proxy misconfiguration

## Prerequisites

- Instance is reachable via SSM (proving basic network path to SSM endpoints works)
- Agent has permission to test network connectivity

## Diagnosis

Determine network path type (public vs private subnet):

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60"); SUBNET=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/network/interfaces/macs/$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/mac)/subnet-id); echo "Subnet: $SUBNET"
```

Check if proxy environment variables are set:

```bash
env | grep -i proxy; cat /etc/environment 2>/dev/null | grep -i proxy
```

## Remediation Steps

### Step 1: Test DNS resolution for key endpoints

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); if [ -n "$REGION" ]; then PROBE_HOST="amazonlinux.${REGION}.amazonaws.com"; else PROBE_HOST="cdn.amazonlinux.com"; echo "NOTE: region unavailable from IMDS (expected if this very network fault also blocks metadata) - falling back to region-agnostic probe $PROBE_HOST; continuing (do NOT abort - this is the network SOP)"; fi; nslookup "$PROBE_HOST" 2>/dev/null || dig "$PROBE_HOST" +short; echo "DNS check done"
```

Expected output: IP addresses followed by "DNS check done"
On failure: go to Step 2

### Step 2: Fix DNS resolution

Handles both systemd-resolved symlink and traditional resolv.conf:

```bash
if [ -L /etc/resolv.conf ]; then mkdir -p /etc/systemd/resolved.conf.d; printf '[Resolve]\nDNS=169.254.169.253\n' > /etc/systemd/resolved.conf.d/aws-vpc.conf; systemctl restart systemd-resolved; else cp /etc/resolv.conf /etc/resolv.conf.bak; sed -i '1i nameserver 169.254.169.253' /etc/resolv.conf; fi; echo "DNS fixed"
```

Expected output: "DNS fixed"
On failure: continue

The address 169.254.169.253 is the Amazon VPC DNS resolver (AmazonProvidedDNS). It is always available within a VPC.

### Step 3: Test HTTPS connectivity to repositories

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60" 2>/dev/null); REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/placement/region 2>/dev/null); if [ -n "$REGION" ]; then PROBE_HOST="amazonlinux.${REGION}.amazonaws.com"; else PROBE_HOST="cdn.amazonlinux.com"; echo "NOTE: region unavailable from IMDS - falling back to region-agnostic probe $PROBE_HOST; continuing (do NOT abort - this is the network SOP)"; fi; curl -sf --connect-timeout 10 "https://${PROBE_HOST}/" >/dev/null && echo "HTTPS OK" || echo "HTTPS FAILED"
```

Expected output: "HTTPS OK"
On failure: continue

### Step 4: Check and fix proxy configuration

```bash
if [ -f /etc/yum.conf ]; then grep -q "^proxy=" /etc/yum.conf && echo "Proxy configured" || echo "No proxy"; fi; if [ -n "$https_proxy" ]; then echo "ENV proxy: $https_proxy"; fi; echo "Proxy check done"
```

Expected output: Proxy status information
On failure: continue

### Step 5: Refresh repository metadata

```bash
yum makecache 2>/dev/null || dnf makecache 2>/dev/null || apt-get update 2>/dev/null; echo "Metadata refreshed"
```

Expected output: "Metadata refreshed"
On failure: abort

## Validation

```bash
yum repolist 2>/dev/null || dnf repolist 2>/dev/null || apt-get update --print-uris 2>/dev/null | head -5; echo "Repos accessible"
```

Expected: Repository list with package counts

## Rollback

```bash
rm -f /etc/systemd/resolved.conf.d/aws-vpc.conf 2>/dev/null && systemctl restart systemd-resolved 2>/dev/null
if [ -f /etc/resolv.conf.bak ]; then cp /etc/resolv.conf.bak /etc/resolv.conf; rm -f /etc/resolv.conf.bak; fi
```

## Escalation

If connectivity cannot be restored at the OS level, the issue is likely infrastructure:
- Security group missing outbound rule for 443
- NACL denying ephemeral port range for return traffic
- NAT gateway in a different AZ or exhausted its elastic IP allocation
- VPC endpoint policy denying access to the specific S3 bucket hosting repos

Escalate with: VPC ID, subnet ID, security group IDs, and output of `curl -v https://repo-endpoint` showing where the connection fails.
