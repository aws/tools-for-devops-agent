# SOP-024: Resolve Windows Update SSL/TLS Certificate Validation Failure (0x80072F8F)

| Field | Value |
|-------|-------|
| ID | SOP-024 |
| Category | certificate_error |
| Severity | High |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022 |
| Requires Reboot | Possible |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-05 |

## Symptoms

- "Exception from HRESULT: 0x80072F8F"
- "An error occurred when attempting to search Windows Update"
- "SSM Patch Manager PatchWindows plugin reports FAILED"
- "Windows Update Agent unable to connect to update service"

## Root Cause

- System clock is significantly out of sync (SSL certificate appears expired or not yet valid)
- Root CA certificates are expired or missing from the certificate store
- TLS 1.2 is not enabled and Windows Update endpoint requires it
- Proxy or firewall intercepting HTTPS traffic with an untrusted certificate
- Windows Update endpoints are unreachable due to network configuration

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Agent has permission to run SSM commands on the instance
- Instance has outbound HTTPS (443) access to Windows Update endpoints

## Remediation Steps

### Step 1: Check system clock against NTP

```powershell
w32tm /stripchart /computer:time.aws.com /samples:1 /dataonly
Write-Output "EXIT:$LASTEXITCODE"
```

- **Expected output:** Time offset shown (should be within a few seconds)
- **On failure:** continue

### Step 2: Force time sync if clock is skewed

```powershell
net stop w32time
w32tm /unregister
w32tm /register
if ($LASTEXITCODE -ne 0) {
    Write-Output "WARNING: w32tm /register failed (exit $LASTEXITCODE) - retrying once to restore the Time service registration"
    w32tm /register
    if ($LASTEXITCODE -ne 0) {
        Write-Output "ERROR: w32time is left UNREGISTERED/BROKEN (exit $LASTEXITCODE) - the Time service will not start correctly. Flag this instance for manual w32time repair before relying on clock sync; do not treat time as trustworthy."
    }
}
net start w32time
w32tm /resync /force
Write-Output "EXIT:$LASTEXITCODE"
```

- **Expected output:** "The command completed successfully. EXIT:0"
- **On failure:** continue

### Step 3: Verify current system time is correct

```powershell
$now = Get-Date
Write-Output "Current time: $($now.ToString('yyyy-MM-dd HH:mm:ss UTC'))"
$token = Invoke-RestMethod -Method Put -Uri 'http://169.254.169.254/latest/api/token' -Headers @{'X-aws-ec2-metadata-token-ttl-seconds'='60'} -TimeoutSec 2
$response = Invoke-WebRequest -Uri 'http://169.254.169.254/latest/meta-data/ami-launch-index' -Headers @{'X-aws-ec2-metadata-token'=$token} -UseBasicParsing -TimeoutSec 2
$serverTime = [DateTime]::Parse($response.Headers['Date'])
$offset = [math]::Abs(($now - $serverTime).TotalSeconds)
Write-Output ($offset -lt 60)
```

- **Expected output:** True (time difference less than 60 seconds)
- **On failure:** continue

### Step 4: Update root certificates from Microsoft

```powershell
certutil -generateSSTFromWU roots.sst
if ($LASTEXITCODE -eq 0) {
    certutil -addstore -f root roots.sst
    Remove-Item roots.sst -Force
    Write-Output "Certificates updated"
} else {
    Write-Output "Certificate download failed"
}
```

- **Expected output:** "Certificates updated"
- **On failure:** continue

### Step 5: Ensure TLS 1.2 is enabled for .NET and Windows Update

```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]([int]3072)
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\.NETFramework\v4.0.30319' -Name 'SchUseStrongCrypto' -Value 1 -Type DWord -Force
Set-ItemProperty -Path 'HKLM:\SOFTWARE\Wow6432Node\Microsoft\.NETFramework\v4.0.30319' -Name 'SchUseStrongCrypto' -Value 1 -Type DWord -Force
Write-Output 'TLS 1.2 enabled'
```

- **Expected output:** "TLS 1.2 enabled"
- **On failure:** abort

### Step 6: Reset Windows Update components

```powershell
Stop-Service wuauserv, cryptSvc, bits, msiserver -Force
Rename-Item C:\Windows\SoftwareDistribution SoftwareDistribution.old -ErrorAction SilentlyContinue
Rename-Item C:\Windows\System32\catroot2 catroot2.old -ErrorAction SilentlyContinue
Start-Service wuauserv, cryptSvc, bits, msiserver
Write-Output 'Windows Update components reset'
```

- **Expected output:** "Windows Update components reset"
- **On failure:** abort

### Step 7: Validate Windows Update connectivity restored

```powershell
$job = Start-Job -ScriptBlock {
    try {
        $Session = New-Object -ComObject Microsoft.Update.Session
        $Searcher = $Session.CreateUpdateSearcher()
        $Results = $Searcher.Search("IsInstalled=0 and Type='Software'")
        "TLS ISSUE RESOLVED - Found $($Results.Updates.Count) updates available for next patch cycle"
    } catch { "FAILED: $($_.Exception.Message)" }
}
if (Wait-Job $job -Timeout 180) {
    Receive-Job $job
} else {
    Stop-Job $job
    Write-Output "FAILED: Windows Update search did not complete within 180s (aborting rather than hanging)"
}
Remove-Job $job -Force
```

- **Expected output:** "TLS ISSUE RESOLVED - Found N updates available for next patch cycle"
- **On failure:** abort

## Validation

```powershell
$job = Start-Job -ScriptBlock {
    try {
        $Session = New-Object -ComObject Microsoft.Update.Session
        $Searcher = $Session.CreateUpdateSearcher()
        $Results = $Searcher.Search("IsInstalled=0")
        "SUCCESS: Update search completed, $($Results.Updates.Count) updates found"
    } catch { "FAILED: $($_.Exception.Message)" }
}
if (Wait-Job $job -Timeout 180) { Receive-Job $job } else { Stop-Job $job; Write-Output "FAILED: Update search did not complete within 180s (timed out)" }
Remove-Job $job -Force
```

**Expected:** SUCCESS: Update search completed without 0x80072F8F error

## Rollback

```powershell
if (Test-Path C:\Windows\SoftwareDistribution.old) { Remove-Item C:\Windows\SoftwareDistribution -Recurse -Force 2>$null; Rename-Item C:\Windows\SoftwareDistribution.old SoftwareDistribution }
if (Test-Path C:\Windows\System32\catroot2.old) { Remove-Item C:\Windows\System32\catroot2 -Recurse -Force 2>$null; Rename-Item C:\Windows\System32\catroot2.old catroot2 }
Write-Output 'Rollback complete'
```

## Escalation

If TLS/certificate errors persist after remediation:
- Verify system clock is correct (SOP-063) — expired/not-yet-valid cert errors are often clock skew
- Check if root certificates are outdated (SOP-070) — missing Microsoft root CA
- For Server 2012 R2: ensure KB3140245 is installed for TLS 1.2 WinHTTP support
- Verify no proxy or firewall is intercepting HTTPS traffic (MITM inspection)
- Check if FIPS mode is enabled and blocking certain TLS cipher suites
- If WSUS is in use: verify WSUS server's SSL certificate is valid and trusted
