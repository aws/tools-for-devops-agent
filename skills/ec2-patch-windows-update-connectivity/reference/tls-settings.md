# TLS 1.2 enablement for Windows Update

**Signatures:** WU HTTPS handshake fails on modern endpoints, `0x80072F8F` variants after clock is
confirmed correct, .NET/WinHTTP negotiating an old protocol, Server 2012 R2 without TLS 1.2 support.

**First confirm the clock is correct** (root-certs-and-clock reference) — a wrong clock also throws
`0x80072F8F`.

## Enable TLS 1.2 + strong crypto for .NET / WinHTTP
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]([int]3072)  # TLS 1.2
Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\.NETFramework\v4.0.30319' -Name SchUseStrongCrypto -Value 1 -Type DWord -Force
Set-ItemProperty 'HKLM:\SOFTWARE\Wow6432Node\Microsoft\.NETFramework\v4.0.30319' -Name SchUseStrongCrypto -Value 1 -Type DWord -Force
# enable the TLS 1.2 SCHANNEL protocol explicitly (esp. 2012 R2):
$base='HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2'
New-Item "$base\Client" -Force | Out-Null
Set-ItemProperty "$base\Client" -Name Enabled -Value 1 -Type DWord
Set-ItemProperty "$base\Client" -Name DisabledByDefault -Value 0 -Type DWord
```

## Reset WU components after the change
```powershell
Stop-Service wuauserv,cryptSvc,bits,msiserver -Force
Rename-Item C:\Windows\SoftwareDistribution SoftwareDistribution.old -EA SilentlyContinue
Rename-Item C:\Windows\System32\catroot2 catroot2.old -EA SilentlyContinue
Start-Service wuauserv,cryptSvc,bits,msiserver
```

## Verify
```powershell
try{ (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0").Updates.Count; "TLS OK" }catch{ $_.Exception.Message }
```

## Escalation
- Server 2012 R2: needs KB3140245 for TLS 1.2 WinHTTP support (and KB2813430 for SHA-2).
- FIPS mode may block cipher suites → review the FIPS policy.
- A proxy doing TLS inspection (MITM) presents its own cert → trust the proxy CA or bypass WU (proxy reference).
