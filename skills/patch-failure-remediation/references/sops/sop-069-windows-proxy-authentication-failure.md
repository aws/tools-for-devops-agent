# SOP-069: Resolve Windows Update Failure Due to Proxy Authentication Issues

| Field | Value |
|-------|-------|
| ID | SOP-069 |
| Category | windows_proxy_authentication_failure |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80072EFD` ("ERROR_INTERNET_CANNOT_CONNECT") through proxy
- `0x80244017` ("WU_E_PT_HTTP_STATUS_DENIED") — HTTP 407 Proxy Auth Required
- `0x8024402C` ("WU_E_PT_WINHTTP_NAME_NOT_RESOLVED") via proxy
- Windows Update scan times out when proxy requires authentication
- WinHTTP proxy configured but SYSTEM account has no proxy credentials
- Updates work for logged-in users but fail for SYSTEM (SSM patching context)

## Root Cause

Proxy authentication blocks Windows Update when:

- WinHTTP proxy configured but SYSTEM account has no cached credentials
- Corporate proxy requires NTLM/Kerberos auth — SYSTEM cannot authenticate
- Proxy PAC file references user-context credentials
- WinINET proxy configured (per-user) but WinHTTP (system-wide) not set
- WPAD auto-discovery points to proxy requiring authentication
- Proxy bypass list doesn't include Windows Update/WSUS endpoints
- Server 2012 R2: WinHTTP doesn't inherit proxy from IE settings automatically

## Related Failure Patterns

- SOP-016 (WPAD Proxy) — WPAD detection issues
- SOP-021 (WSUS Unreachable) — proxy blocking WSUS traffic
- SOP-060 (Firewall) — proxy vs firewall differentiation

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Knowledge of customer's proxy infrastructure

## Diagnosis

```powershell
$winhttp = & netsh winhttp show proxy 2>&1
Write-Output "WinHTTP proxy: $winhttp"
$ie = Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
Write-Output "IE ProxyEnable: $($ie.ProxyEnable) ProxyServer: $($ie.ProxyServer)"
# Test direct connectivity vs proxy
$direct = Test-NetConnection -ComputerName "windowsupdate.microsoft.com" -Port 443 -WarningAction SilentlyContinue
Write-Output "Direct 443: $($direct.TcpTestSucceeded)"
```

## Remediation Steps

### Step 1: Check current proxy configuration

```powershell
$winhttp = & netsh winhttp show proxy 2>&1
Write-Output "=== WinHTTP (System) ==="
$winhttp | ForEach-Object { Write-Output "  $_" }
$sysproxy = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
Write-Output "=== System IE Settings ==="
Write-Output "  ProxyEnable: $($sysproxy.ProxyEnable)"
Write-Output "  ProxyServer: $($sysproxy.ProxyServer)"
Write-Output "  ProxyOverride: $($sysproxy.ProxyOverride)"
```

Expected output: Proxy configuration displayed
On failure: continue

### Step 2: Set WinHTTP proxy bypass for Windows Update endpoints

```powershell
$currentProxy = & netsh winhttp show proxy 2>&1
if ($currentProxy -match "Proxy Server") {
    $proxy = ($currentProxy | Select-String "Proxy Server").ToString() -replace ".*:\s+",""
    $bypass = "*.windowsupdate.microsoft.com;*.update.microsoft.com;*.download.windowsupdate.com;*.download.microsoft.com;169.254.169.254;169.254.169.123"
    & netsh winhttp set proxy proxy-server="$proxy" bypass-list="$bypass" 2>&1 | Out-Null
    Write-Output "Proxy bypass list updated for Windows Update endpoints"
} else { Write-Output "No proxy configured — connectivity issue is not proxy-related" }
```

Expected output: Bypass list updated or no proxy
On failure: continue

### Step 3: Import IE proxy settings to WinHTTP (if IE has working config)

```powershell
$ieSetting = Get-ItemProperty 'Registry::HKEY_USERS\.DEFAULT\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
if (-not $ieSetting) {
    # Try importing from current user
    & netsh winhttp import proxy source=ie 2>&1 | Out-Null
    Write-Output "Imported IE proxy settings to WinHTTP"
} else { Write-Output "Checked .DEFAULT proxy settings" }
```

Expected output: Import status
On failure: continue

### Step 4: Configure proxy for SYSTEM account (LocalSystem IE settings)

```powershell
$regPath = 'Registry::HKEY_USERS\S-1-5-18\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings'
if (-not (Test-Path $regPath)) {
    # Load SYSTEM user hive
    $regPath = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings'
}
# Set proxy bypass for WU in system context
$bypass = (Get-ItemProperty $regPath -Name ProxyOverride -ErrorAction SilentlyContinue).ProxyOverride
$wuBypass = "*.windowsupdate.microsoft.com;*.update.microsoft.com;169.254.169.254"
if ($bypass -and $bypass -notmatch "windowsupdate") {
    Set-ItemProperty $regPath -Name ProxyOverride -Value "$bypass;$wuBypass"
    Write-Output "Added WU bypass to existing proxy exceptions"
} elseif (-not $bypass) {
    Set-ItemProperty $regPath -Name ProxyOverride -Value $wuBypass -ErrorAction SilentlyContinue
    Write-Output "Set WU proxy bypass"
}
Write-Output "PROXY BYPASS CONFIGURED"
```

Expected output: "PROXY BYPASS CONFIGURED"
On failure: continue

### Step 5: Test Windows Update connectivity through proxy

```powershell
Restart-Service wuauserv -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
try {
    $web = Invoke-WebRequest -Uri "https://windowsupdate.microsoft.com" -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
    Write-Output "PROXY REMEDIATION OK: WU endpoint reachable (HTTP $($web.StatusCode))"
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -eq 407) { Write-Output "STILL BLOCKED: HTTP 407 Proxy Auth Required" }
    elseif ($code) { Write-Output "HTTP $code from proxy" }
    else { Write-Output "Connection attempt result: $($_.Exception.Message)" }
}
```

Expected output: "PROXY REMEDIATION OK"
On failure: abort

## Validation

```powershell
# The remediation may fix the effective proxy config via any of the paths WU actually uses:
# the WinHTTP proxy (Step 2), the imported IE->WinHTTP config (Step 3), or the SYSTEM/system
# IE registry ProxyOverride bypass (Step 4). Validate whichever path applies — checking only
# WinHTTP would falsely fail a correct registry-based fix.
$winhttpBypass = (& netsh winhttp show proxy 2>&1) -match "windowsupdate"

$regPaths = @(
    'Registry::HKEY_USERS\S-1-5-18\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
    'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings'
)
$regBypass = $false
foreach ($p in $regPaths) {
    if (Test-Path $p) {
        $ov = (Get-ItemProperty $p -Name ProxyOverride -ErrorAction SilentlyContinue).ProxyOverride
        if ($ov -match "windowsupdate") { $regBypass = $true }
    }
}

# If no proxy is configured at all, direct connectivity to WU is itself a valid success state.
# Language-independent direct-access check: read the WinHTTP proxy flag DWORD from the registry instead of matching the localized "Direct access" text from netsh. Blob layout: bytes[0..3]=version, bytes[4..7]=change counter, bytes[8..11]=flags DWORD (1=DIRECT, 2=named proxy, 4=autoconfig). The flag byte is at offset 8; a missing key also defaults to direct.
$whRaw = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\Connections' -Name WinHttpSettings -ErrorAction SilentlyContinue).WinHttpSettings
$noProxy = ($null -eq $whRaw) -or ($whRaw.Length -lt 9) -or ($whRaw[8] -eq 1)

if ($winhttpBypass -or $regBypass -or $noProxy) { "PROXY REMEDIATION OK" } else { "PROXY BYPASS NOT SET" }
```

Expected: "PROXY REMEDIATION OK"

## Rollback

```powershell
& netsh winhttp reset proxy 2>&1 | Out-Null
Write-Output "WinHTTP proxy configuration reset to direct"
```

## Escalation

If proxy authentication cannot be bypassed:
- Customer must configure proxy to allow unauthenticated access to Microsoft Update URLs
- Alternative: set up internal WSUS server that doesn't require proxy for client access
- For NTLM proxy: SYSTEM account cannot authenticate — proxy exception is required
- Consider using AWS PrivateLink endpoints if available for the service
- For Server 2012 R2: `proxycfg.exe` tool may be needed for legacy WinHTTP configuration
- Check if customer has a PAC file that can be updated to bypass WU URLs
