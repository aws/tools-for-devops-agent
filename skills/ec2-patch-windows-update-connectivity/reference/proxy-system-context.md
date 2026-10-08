# Proxy authentication in the SYSTEM context (HTTP 407)

**Signatures:** `0x80072EFD` (cannot connect through proxy), `0x80244017` (WU_E_PT_HTTP_STATUS_DENIED
= HTTP 407 Proxy Auth Required), `0x8024402C` (name not resolved via proxy); updates work for
logged-in users but fail under SSM patching. **Key fact:** SSM / AWS-RunPatchBaseline runs as
**SYSTEM (LocalSystem)**, which has no cached proxy credentials and can't do NTLM/Kerberos to a proxy.

## Diagnose
```powershell
netsh winhttp show proxy                 # WUA uses the WinHTTP (system) proxy
Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings' | Select ProxyEnable,ProxyServer  # per-user IE (NOT what SYSTEM uses)
Test-NetConnection windowsupdate.microsoft.com -Port 443 -WarningAction SilentlyContinue
```

## Fix — set the WinHTTP proxy + a WU bypass list (system context)
```powershell
$cur = netsh winhttp show proxy 2>&1
if($cur -match 'Proxy Server'){
  $proxy = ($cur | Select-String 'Proxy Server').ToString() -replace '.*:\s+',''
  $bypass = '*.windowsupdate.microsoft.com;*.update.microsoft.com;*.download.windowsupdate.com;*.download.microsoft.com;169.254.169.254;169.254.169.123'
  netsh winhttp set proxy proxy-server="$proxy" bypass-list="$bypass" | Out-Null
  "WinHTTP proxy + WU bypass set"
} else { netsh winhttp import proxy source=ie | Out-Null; "imported IE proxy to WinHTTP" }
Restart-Service wuauserv -Force
```

## Verify
```powershell
netsh winhttp show proxy | Select-String windowsupdate
try{ (Invoke-WebRequest https://windowsupdate.microsoft.com -UseBasicParsing -TimeoutSec 15).StatusCode; "PROXY OK" }catch{ "still $($_.Exception.Response.StatusCode.value__)" }
```

## Escalation
- NTLM/Kerberos proxy: SYSTEM cannot authenticate — the proxy MUST allow the WU URLs unauthenticated (bypass), or use an internal WSUS that clients reach without proxy auth.
- WPAD/PAC referencing user-context creds → doesn't work for SYSTEM; set an explicit WinHTTP proxy/bypass instead.
- Consider PrivateLink/VPC endpoints where available.
- Rollback: `netsh winhttp reset proxy`.
