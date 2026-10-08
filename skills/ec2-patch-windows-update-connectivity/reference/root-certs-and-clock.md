# Root certificate store & clock skew

**Signatures:** `0x800B0109` ("terminated in a root certificate which is not trusted"), `0x800B010A`
("untrusted certificate chain"), `0x80072F8F` ("security error"), WU/WSUS HTTPS chain validation
fails, Microsoft CDN root not trusted. Two distinct causes: a **wrong clock** or a **stale root store**.

## Rule out clock first (cheapest)
```powershell
Get-Date
w32tm /stripchart /computer:time.aws.com /samples:1 /dataonly 2>&1 | Select -Last 3
# resync if skewed:
net stop w32time; w32tm /unregister; w32tm /register; net start w32time; w32tm /resync /force
```
`0x80072F8F` on a long-stopped instance is usually the clock. Fix time, retry before touching certs.

## Refresh the root certificate store
```powershell
$r=Get-ChildItem Cert:\LocalMachine\Root; "roots=$($r.Count) expired=$(($r|?{$_.NotAfter -lt (Get-Date)}).Count)"
(Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot' -Name DisableRootAutoUpdate -EA SilentlyContinue).DisableRootAutoUpdate
# enable auto-update if a policy disabled it:
Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot' -Name DisableRootAutoUpdate -Value 0 -EA SilentlyContinue
# pull current roots from WU and import:
certutil -generateSSTFromWU "$env:TEMP\roots.sst"
certutil -addstore -f Root "$env:TEMP\roots.sst"; Remove-Item "$env:TEMP\roots.sst" -Force
```

## Verify
```powershell
try{ [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ([Net.HttpWebRequest]::Create('https://download.windowsupdate.com')).GetResponse().Close(); "CERT OK" }catch{ "CERT FAIL: $($_.Exception.InnerException.Message)" }
```

## Escalation
- Air-gapped: `certutil -syncWithWU <dir>` on a connected host, copy the CTL/roots in.
- Proxy blocking `ctldl.windowsupdate.com` (cert trust list endpoint) → allow it (firewall/proxy references).
- Server 2012 R2: KB2813430 for SHA-2 root support.
- Security team intentionally removed roots for compliance → coordinate before re-adding.
