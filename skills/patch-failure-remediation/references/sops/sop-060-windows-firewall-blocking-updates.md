# SOP-060: Resolve Windows Firewall / Network Profile Blocking Update Endpoints

| Field | Value |
|-------|-------|
| ID | SOP-060 |
| Category | windows_firewall_blocking_updates |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80072EE2` ("ERROR_INTERNET_TIMEOUT") on Windows Update
- `0x80072EFD` ("ERROR_INTERNET_CANNOT_CONNECT")
- `0x80072F8F` when firewall blocks HTTPS but not HTTP
- Windows Update scan finds 0 updates when patches are expected
- Network profile set to "Public" blocking WUA outbound traffic
- Third-party firewall software blocking Windows Update endpoints
- Updates download from WSUS on LAN but fail when targeting Microsoft directly

## Root Cause

Windows Update cannot reach required endpoints when:

- Windows Firewall outbound rules block HTTPS (443) to Microsoft/AWS endpoints
- Network profile incorrectly set to "Public" (more restrictive firewall)
- Third-party firewall (Symantec, McAfee, etc.) blocking WUA traffic
- Security group or NACL blocking required outbound ports
- VPC endpoint or proxy not configured for Windows Update URLs
- Windows Firewall service disabled but third-party firewall removed (no rules active)
- Server 2012 R2: IPsec policy blocking specific outbound connections

## Related Failure Patterns

- SOP-021 (WSUS Unreachable) — similar connectivity issue but WSUS-specific
- SOP-024 (TLS Failure) — TLS vs connectivity differentiation

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of customer's network security requirements

## Diagnosis

```powershell
$profile = Get-NetConnectionProfile | Select-Object Name,NetworkCategory
$fwState = Get-NetFirewallProfile | Select-Object Name,Enabled
Write-Output "Network profiles: $($profile | ForEach-Object { "$($_.Name)=$($_.NetworkCategory)" })"
Write-Output "Firewall state: $($fwState | ForEach-Object { "$($_.Name)=$($_.Enabled)" })"
Test-NetConnection -ComputerName "windowsupdate.microsoft.com" -Port 443 -WarningAction SilentlyContinue | Select-Object ComputerName,TcpTestSucceeded
```

## Remediation Steps

### Step 1: Check network profile and firewall state

```powershell
$profiles = Get-NetConnectionProfile
$fw = Get-NetFirewallProfile
Write-Output "=== Network Profiles ==="
$profiles | ForEach-Object { Write-Output "  $($_.InterfaceAlias): $($_.NetworkCategory)" }
Write-Output "=== Firewall Profiles ==="
$fw | ForEach-Object { Write-Output "  $($_.Name): Enabled=$($_.Enabled) DefaultOutbound=$($_.DefaultOutboundAction)" }
```

Expected output: Profile and firewall states listed
On failure: continue

### Step 2: Test connectivity to Windows Update endpoints

```powershell
$endpoints = @(
    @{Host="windowsupdate.microsoft.com"; Port=443},
    @{Host="update.microsoft.com"; Port=443},
    @{Host="download.windowsupdate.com"; Port=443},
    @{Host="download.microsoft.com"; Port=443}
)
foreach ($ep in $endpoints) {
    $result = Test-NetConnection -ComputerName $ep.Host -Port $ep.Port -WarningAction SilentlyContinue
    Write-Output "$($ep.Host):$($ep.Port) = $($result.TcpTestSucceeded)"
}
```

Expected output: Connectivity results for each endpoint
On failure: continue

### Step 3: Set network profile to Private if incorrectly Public

```powershell
$public = Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq 'Public' }
if ($public) {
    $public | Set-NetConnectionProfile -NetworkCategory Private
    Write-Output "Changed $($public.Count) profile(s) from Public to Private"
} else { Write-Output "No Public profiles found" }
```

Expected output: Profile change or no action
On failure: continue

### Step 4: Add Windows Update firewall exceptions

```powershell
$ruleName = "Allow Windows Update HTTPS"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Outbound -Protocol TCP -RemotePort 443 -Action Allow -Profile Any -Program "$env:SystemRoot\System32\svchost.exe" | Out-Null
    Write-Output "Firewall rule added: $ruleName"
} else { Write-Output "Firewall rule already exists" }
```

Expected output: "Firewall rule added" or "already exists"
On failure: continue

### Step 5: Verify connectivity after changes

```powershell
$test = Test-NetConnection -ComputerName "windowsupdate.microsoft.com" -Port 443 -WarningAction SilentlyContinue
if ($test.TcpTestSucceeded) { Write-Output "CONNECTIVITY OK: Windows Update reachable" }
else { Write-Output "CONNECTIVITY FAILED: Still cannot reach Windows Update" }
```

Expected output: "CONNECTIVITY OK"
On failure: abort

## Validation

```powershell
$test = Test-NetConnection -ComputerName "download.windowsupdate.com" -Port 443 -WarningAction SilentlyContinue
if ($test.TcpTestSucceeded) { "FIREWALL REMEDIATION OK" } else { "STILL BLOCKED" }
```

Expected: "FIREWALL REMEDIATION OK"

## Rollback

```powershell
Remove-NetFirewallRule -DisplayName "Allow Windows Update HTTPS" -ErrorAction SilentlyContinue
# To revert network profile:
# Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Public
Write-Output "Firewall rule removed"
```

## Escalation

If connectivity still blocked:
- Issue is likely at VPC/security group level — check outbound SG rules for port 443
- Verify VPC endpoints or NAT Gateway allows traffic to Microsoft Update CDN
- Check if customer has proxy configured: `netsh winhttp show proxy`
- For Server 2012 R2: check if IPsec connection security rules are blocking
- Third-party firewalls: check Symantec/McAfee/Trend Micro application control rules
- If all endpoints blocked: customer may require WSUS for air-gapped environments
