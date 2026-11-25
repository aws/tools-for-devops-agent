# SOP-063: Resolve Windows Update Failure Due to Incorrect System Time / Clock Skew

| Field | Value |
|-------|-------|
| ID | SOP-063 |
| Category | windows_time_skew_patch_failure |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80072F8F` ("A security error occurred") due to certificate date validation
- `0x80072F0D` ("The certificate authority is invalid or incorrect")
- Windows Update HTTPS connections fail with "The certificate is not yet valid"
- Kerberos authentication failures preventing WSUS access
- CBS.log shows timestamp validation errors
- Time is significantly off from UTC (>5 minutes skew)

## Root Cause

System clock skew causes patch failures when:

- EC2 instance lost time sync after hibernation or stop/start
- NTP service (W32Time) not configured or pointing to unreachable server
- Domain-joined instance cannot reach domain controller for time sync
- Hypervisor clock drift on older instance types
- System clock set far in future/past manually
- Time zone misconfigured causing UTC offset calculation errors
- Server 2012 R2: VMICTimeProvider conflicts with W32Time

## Related Failure Patterns

- SOP-024 (TLS Failure) — clock skew causes identical TLS cert errors
- SOP-021 (WSUS Unreachable) — Kerberos auth fails with clock skew >5min

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

```powershell
$time = Get-Date
$utc = [DateTime]::UtcNow
Write-Output "Local time: $time"
Write-Output "UTC time: $utc"
$w32tm = & w32tm /query /status 2>&1
$w32tm | Select-String "Source|Last Successful|Offset"
```

## Remediation Steps

### Step 1: Check current time and NTP status

```powershell
$localTime = Get-Date
$ntpStatus = & w32tm /query /status 2>&1
# Guard for null: when W32Time is not running there is no "Source:" line, so the match is
# $null and calling .ToString() on it would throw. Handle the no-source case gracefully.
$sourceMatch = $ntpStatus | Select-String "Source:" | Select-Object -First 1
if ($sourceMatch) { $source = $sourceMatch.ToString().Split(":")[1].Trim() }
else { $source = "UNKNOWN (no Source reported — W32Time may not be running)" }
$offsetMatch = $ntpStatus | Select-String "Root Dispersion" | Select-Object -First 1
$offset = if ($offsetMatch) { $offsetMatch.ToString() } else { "Root Dispersion: unavailable" }
Write-Output "Current UTC: $([DateTime]::UtcNow.ToString('yyyy-MM-dd HH:mm:ss'))"
Write-Output "NTP Source: $source"
Write-Output $offset
```

Expected output: Time and NTP status displayed
On failure: continue

### Step 2: Configure NTP to use Amazon Time Sync

```powershell
& w32tm /config /manualpeerlist:"169.254.169.123" /syncfromflags:MANUAL /reliable:YES /update 2>&1 | Out-Null
Write-Output "NTP configured to Amazon Time Sync (169.254.169.123)"
```

Expected output: "NTP configured to Amazon Time Sync"
On failure: continue

### Step 3: Restart time service and force sync

```powershell
Restart-Service W32Time -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$result = & w32tm /resync /force 2>&1
Write-Output "Time sync result: $($result | Select-String 'command completed|error')"
```

Expected output: "command completed successfully"
On failure: continue

### Step 4: Verify time is within acceptable skew

```powershell
Start-Sleep -Seconds 5
$status = & w32tm /query /status 2>&1
$source = ($status | Select-String "Source:") -replace "Source:\s*",""
# Check IMDS for comparison (use IMDSv2: fetch a token first, then pass it in the header)
try {
    $token = (Invoke-WebRequest -Uri "http://169.254.169.254/latest/api/token" -Method PUT -Headers @{ 'X-aws-ec2-metadata-token-ttl-seconds' = '60' } -UseBasicParsing -TimeoutSec 2).Content
    $imdsTime = (Invoke-WebRequest -Uri "http://169.254.169.254/latest/meta-data/ami-launch-index" -Headers @{ 'X-aws-ec2-metadata-token' = $token } -UseBasicParsing -TimeoutSec 2).Headers.Date
    Write-Output "IMDS response time: $imdsTime"
} catch { Write-Output "IMDS time check skipped" }
Write-Output "NTP source: $source"
Write-Output "TIME SYNC OK"
```

Expected output: "TIME SYNC OK"
On failure: abort

## Validation

```powershell
$status = & w32tm /query /status 2>&1
$source = $status | Select-String "Source:"
if ($source -and $source -notmatch "Free-Running|Local CMOS") { "TIME REMEDIATION OK: $source" }
else { "TIME ISSUE: Source=$source" }
```

Expected: "TIME REMEDIATION OK"

## Rollback

```powershell
# NOTE: DOMHIER (domain hierarchy) is only valid on a DOMAIN-JOINED instance. On a
# non-domain-joined instance, reverting to DOMHIER leaves it with NO working time source
# and it will drift again. On non-domain instances, restore the Amazon Time Sync / NTP
# source instead of DOMHIER.
$domainJoined = (Get-CimInstance Win32_ComputerSystem).PartOfDomain
if ($domainJoined) {
    & w32tm /config /syncfromflags:DOMHIER /update 2>&1 | Out-Null
    Write-Output "Reverted to domain hierarchy time sync"
} else {
    & w32tm /config /manualpeerlist:"169.254.169.123" /syncfromflags:MANUAL /reliable:YES /update 2>&1 | Out-Null
    Write-Output "Non-domain instance: restored Amazon Time Sync (169.254.169.123) rather than DOMHIER"
}
Restart-Service W32Time
```

## Escalation

If time cannot be synchronized:
- Check if security group allows UDP 123 outbound (NTP)
- For domain-joined: ensure domain controller is reachable for time sync
- If clock is extremely far off (years): manually set approximate time first, then sync
- Check if Hyper-V time integration service is conflicting: `Get-VMIntegrationService`
- For Server 2012 R2: disable VMICTimeProvider if it conflicts with W32Time
- Verify Amazon Time Sync Service is accessible: `Test-NetConnection 169.254.169.123 -Port 123`
