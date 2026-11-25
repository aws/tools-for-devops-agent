# SOP-016: Resolve WPAD Proxy Issues Blocking Windows Patching

| Field | Value |
|-------|-------|
| ID | SOP-016 |
| Category | wpad_proxy |
| Severity | Medium |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, Windows Server 2019, Windows Server 2022 |
| Requires Reboot | No (recommend customer-scheduled reboot if WU still fails) |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Windows patching fails with proxy-related download errors
- "WinHTTP Web Proxy Auto-Discovery Service" causing update timeouts
- Windows Update agent unable to reach WSUS or Windows Update endpoints
- Patch downloads stall or timeout due to WPAD proxy misconfiguration
- Error code "0x80072EE2" (ERROR_INTERNET_TIMEOUT) during patching
- Error code "0x80244022" (SUS_E_PT_HTTP_STATUS_SERVICE_UNAVAIL)
- "The request was not made because the proxy failed" in WindowsUpdate.log
- CBS.log shows "Download failed" with proxy-related HTTP errors

## Root Cause

WPAD (Web Proxy Auto-Discovery Protocol) proxy issues occur when:

- WinHttpAutoProxySvc service auto-discovers incorrect proxy settings from DNS or DHCP — the service queries for a "wpad" DNS record and follows whatever PAC file it finds
- WPAD DNS entry resolves to a non-functional or overloaded proxy server in the VPC
- Proxy auto-configuration (PAC) script is unreachable or returns invalid configuration that routes Windows Update traffic through an incompatible proxy
- WPAD interferes with direct connections to Windows Update/WSUS endpoints by forcing traffic through a proxy that blocks large downloads
- Domain-joined instances inherit Group Policy proxy settings that conflict with direct internet access
- The WinHTTP proxy settings differ from Internet Explorer/WinINET proxy settings, causing confusion about which path Windows Update uses

This is common in environments where instances are domain-joined and the domain configures WPAD, but the discovered proxy doesn't allow Windows Update traffic.

## Related Failure Patterns

- SOP-003 (Network Unreachable) — Linux equivalent of connectivity issues
- SOP-007 (AWS CLI Credentials) — similar pattern of misconfigured access paths on Windows

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is Windows (Linux instances skip this remediation)
- Administrator access via SSM Run Command

## Diagnosis

Check current proxy configuration at all levels:

```powershell
Write-Output "=== WinHTTP Proxy ==="; netsh winhttp show proxy; Write-Output "=== IE/System Proxy ==="; Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' | Select-Object ProxyEnable,ProxyServer,AutoConfigURL; Write-Output "=== WPAD Service ==="; Get-Service WinHttpAutoProxySvc | Select-Object Status,StartType
```

Check Windows Update log for proxy errors:

```powershell
Get-WindowsUpdateLog 2>$null; Select-String -Path "$env:TEMP\WindowsUpdate.log" -Pattern "proxy|WPAD|0x80072" -Context 0,2 | Select-Object -Last 10
```

## Remediation Steps

### Step 1: Check current WinHTTP proxy and WPAD service status

```powershell
$svc = Get-Service WinHttpAutoProxySvc -ErrorAction SilentlyContinue; Write-Output "WPAD Service: $($svc.Status), StartType: $($svc.StartType)"; netsh winhttp show proxy; Write-Output "Proxy check done"
```

Expected output: Service status and current proxy settings
On failure: continue

### Step 2: Get current WinHttpAutoProxySvc registry startup value

```powershell
$regPath = 'HKLM:\SYSTEM\CurrentControlSet\Services\WinHttpAutoProxySvc'; $startValue = (Get-ItemProperty -Path $regPath -Name Start -ErrorAction SilentlyContinue).Start; Write-Output "Current Start value: $startValue"; Write-Output "Registry check done"
```

Expected output: "Current Start value: N" (3=Manual, 4=Disabled)
On failure: continue

### Step 3: Disable WinHttpAutoProxySvc and reset proxy

```powershell
Set-Service -Name WinHttpAutoProxySvc -StartupType Disabled -ErrorAction SilentlyContinue; Stop-Service -Name WinHttpAutoProxySvc -Force -ErrorAction SilentlyContinue; netsh winhttp reset proxy; Restart-Service wuauserv -Force -ErrorAction SilentlyContinue; Write-Output "WPAD disabled, proxy reset, WUA restarted"
```

Expected output: "WPAD disabled, proxy reset, WUA restarted"
On failure: abort

> **Note:** A reboot may be required if Windows Update components still cache stale proxy settings after the WUA service restart. Do NOT reboot automatically — inform the customer that a reboot is recommended and schedule it via an approved RFC/maintenance window.

### Step 4: Verify Windows Update connectivity (no reboot performed by this SOP)

```powershell
$result = Test-NetConnection -ComputerName "windowsupdate.microsoft.com" -Port 443 -WarningAction SilentlyContinue; if ($result.TcpTestSucceeded) { Write-Output "WU connectivity OK" } else { Write-Output "WU connectivity FAILED" }
```

Expected output: "WU connectivity OK"
On failure: abort

### Step 5: Revert WinHttpAutoProxySvc to original state after patching

```powershell
Set-Service -Name WinHttpAutoProxySvc -StartupType Manual -ErrorAction SilentlyContinue; Start-Service -Name WinHttpAutoProxySvc -ErrorAction SilentlyContinue; Write-Output "WPAD service reverted to Manual"
```

Expected output: "WPAD service reverted to Manual"
On failure: continue

## Validation

```powershell
$svc = Get-Service WinHttpAutoProxySvc -ErrorAction SilentlyContinue; $wu = Test-NetConnection -ComputerName "windowsupdate.microsoft.com" -Port 443 -WarningAction SilentlyContinue; if ($wu.TcpTestSucceeded) { Write-Output "WPAD REMEDIATION OK" } else { Write-Output "WPAD REMEDIATION FAILED" }
```

Expected: "WPAD REMEDIATION OK"

## Rollback

```powershell
Set-Service -Name WinHttpAutoProxySvc -StartupType Manual -ErrorAction SilentlyContinue
Start-Service -Name WinHttpAutoProxySvc -ErrorAction SilentlyContinue
Write-Output "WinHttpAutoProxySvc reverted to Manual startup"
```

## Prevention

To prevent WPAD-related patch failures:
- Configure a Group Policy to bypass proxy for Windows Update URLs: `*.windowsupdate.microsoft.com`, `*.update.microsoft.com`
- Set WinHTTP proxy bypass list: `netsh winhttp set proxy proxy-server="proxy:8080" bypass-list="*.windowsupdate.microsoft.com;*.update.microsoft.com;169.254.169.254"`
- For instances that don't need WPAD at all, disable it permanently via Group Policy

## Escalation

If Windows Update still fails after WPAD is disabled:
- Check if a transparent proxy or firewall is intercepting HTTPS traffic (TLS inspection breaking Windows Update certificate pinning)
- Verify security group allows outbound 443 to 0.0.0.0/0 or at minimum to Microsoft's IP ranges
- Check if WSUS is configured: `reg query "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" /v WUServer` — if WSUS is set, the instance must reach WSUS, not the internet
- Run Windows Update troubleshooter: `Get-TroubleshootingPack -Path "$env:SystemRoot\diagnostics\system\WindowsUpdate" | Invoke-TroubleshootingPack`
