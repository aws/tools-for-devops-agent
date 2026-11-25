# SOP-007: Resolve AWS CLI Credential Issues Blocking Patching

| Field | Value |
|-------|-------|
| ID | SOP-007 |
| Category | aws_cli_credentials |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Linux |
| Distributions | Amazon Linux 2, Amazon Linux 2023, Ubuntu 20.04, Ubuntu 22.04, RHEL 8, RHEL 9 |
| Requires Reboot | No |
| Estimated Duration | 90 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch pre-checks fail with "Unable to locate credentials" or "ExpiredTokenException"
- SSM agent unable to assume instance profile role
- Patch download from S3 fails with "Access Denied" or credential errors
- "InvalidClientTokenId" or "SignatureDoesNotMatch" errors in patch logs
- "The security token included in the request is expired" during patching
- "NoCredentialProviders: no valid providers in chain" from AWS SDK

## Root Cause

AWS CLI credential issues during patching caused by:

- Instance metadata service (IMDS) unreachable or throttled — hop limit of 1 blocks metadata from containers, or iptables rules block 169.254.169.254
- Stale credentials cached in ~/.aws/credentials file override the instance profile (leftover from development or manual testing)
- IMDSv2 token expired and not refreshed — applications holding long-lived tokens that HTTP PUT renewal fails
- Instance profile not attached or IAM role trust policy does not trust ec2.amazonaws.com
- AWS CLI config file pointing to wrong credential source (e.g., credential_process pointing to expired SSO session)
- Clock skew on the instance causes signature validation failures (more than 5 minutes drift)

## Related Failure Patterns

- SOP-003 (Network Unreachable) — network issues can block IMDS access and appear as credential failures
- SOP-016 (WPAD Proxy) — proxy misconfiguration blocking IMDS on Windows

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance has an IAM instance profile attached (check in EC2 console)

## Diagnosis

Determine credential provider chain:

```bash
aws configure list 2>&1; echo "---"; curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -o /dev/null -w "%{http_code}" http://169.254.169.254/latest/meta-data/ 2>/dev/null; echo " (IMDS HTTP status)"
```

Check for clock skew:

```bash
date -u; curl -sI --connect-timeout 5 --max-time 10 https://s3.amazonaws.com 2>/dev/null | grep -i "^date:"
```

## Remediation Steps

### Step 1: Verify IMDS accessibility

```bash
TOKEN=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null) && curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/iam/security-credentials/ && echo "" && echo "IMDS OK" || echo "IMDS FAILED"
```

Expected output: Role name followed by "IMDS OK"
On failure: go to Step 2

### Step 2: Fix IMDS connectivity (iptables rules may block)

```bash
if iptables -C OUTPUT -d 169.254.169.254 -j DROP 2>/dev/null; then iptables -D OUTPUT -d 169.254.169.254 -j DROP && echo "IMDS unblocked" || echo "ERROR: failed to delete blocking rule"; else echo "No blocking rule found"; fi
```

Expected output: "IMDS unblocked" or "No blocking rule found"
On failure: continue

### Step 3: Remove stale credential files that override instance profile

```bash
for USER_HOME in /root /home/*; do if [ -f "$USER_HOME/.aws/credentials" ]; then mv "$USER_HOME/.aws/credentials" "$USER_HOME/.aws/credentials.bak.$(date +%s)"; echo "Moved $USER_HOME/.aws/credentials"; fi; done; echo "Stale creds cleared"
```

Expected output: "Stale creds cleared"
On failure: continue

### Step 4: Fix clock skew if present

```bash
if command -v chronyc &>/dev/null; then chronyc makestep 2>/dev/null; echo "Clock synced via chrony"; elif command -v ntpdate &>/dev/null; then ntpdate -u 169.254.169.123 2>/dev/null; echo "Clock synced via ntp"; else echo "No NTP client found"; fi
```

Expected output: "Clock synced via chrony" or equivalent
On failure: continue

### Step 5: Verify AWS CLI can obtain credentials from instance profile

```bash
aws sts get-caller-identity --output json 2>&1; echo "STS_EXIT:$?"
```

Expected output: JSON with Account, Arn, UserId and "STS_EXIT:0"
On failure: abort

### Step 6: Verify S3 access for patch downloads

```bash
REGION=$(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $(curl -s --noproxy '*' --connect-timeout 2 --max-time 5 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" http://169.254.169.254/latest/meta-data/placement/region); aws s3 ls s3://aws-ssm-${REGION}/ --region $REGION 2>&1 | head -3; echo "S3 access check done"
```

Expected output: S3 listing followed by "S3 access check done"
On failure: continue (may indicate IAM policy issue rather than credential issue)

## Validation

```bash
aws sts get-caller-identity --output text && echo "CREDENTIALS OK"
```

Expected: Account ID, ARN, UserId followed by "CREDENTIALS OK"

## Rollback

```bash
for BAK in /root/.aws/credentials.bak.* /home/*/.aws/credentials.bak.*; do if [ -f "$BAK" ]; then ORIG="${BAK%.bak.*}"; mv "$BAK" "$ORIG"; echo "Restored $ORIG"; fi; done
```

## Escalation

If credentials cannot be obtained after IMDS is accessible:
- Verify the instance profile is attached: check EC2 console or `aws ec2 describe-instances`
- Verify the IAM role's trust policy includes `ec2.amazonaws.com` as a trusted principal
- Check if the role has been deleted or its permissions boundary blocks `sts:AssumeRole`
- For IMDSv2 issues, check the instance metadata options hop limit (`aws ec2 describe-instances --instance-id ... --query 'Reservations[].Instances[].MetadataOptions'`)
