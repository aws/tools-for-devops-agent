# SOP-070: Resolve Windows Update Failure Due to Outdated Root Certificates

| Field | Value |
|-------|-------|
| ID | SOP-070 |
| Category | windows_outdated_root_certificates |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 120 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x80072F8F` ("A security error occurred") on HTTPS connections to WU
- `0x800B0109` ("A certificate chain processed, but terminated in a root certificate which is not trusted")
- `0x800B010A` ("An untrusted certificate chain was detected")
- Windows Update HTTPS handshake fails despite correct clock
- WSUS HTTPS endpoint rejected due to certificate chain validation failure
- Microsoft CDN certificates not trusted (new root CA)

## Root Cause

Certificate trust failures during patching when:

- Root certificate store is outdated (auto-update disabled or network-isolated)
- GPO disabled automatic root certificate updates
- Microsoft added a new root CA that isn't in the local trusted store
- Intermediate CA certificates missing from store
- CRL/OCSP endpoints unreachable for revocation checking
- Server 2012 R2: old SHA-1 root expired, SHA-2 root not added
- Air-gapped or highly restricted network prevents cert auto-update
- Third-party security tool removed Microsoft root certificates

## Related Failure Patterns

- SOP-024 (TLS Failure) — TLS version vs certificate trust differentiation
- SOP-063 (Time Skew) — identical error code but different root cause
- SOP-060 (Firewall) — blocked CRL/OCSP endpoints

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Verify system clock is correct before assuming certificate issue (SOP-063)

## Diagnosis

```powershell
$roots = Get-ChildItem Cert:\LocalMachine\Root | Measure-Object
$expired = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.NotAfter -lt (Get-Date) }
Write-Output "Root certs: $($roots.Count), Expired: $($expired.Count)"
# Check Microsoft root CAs
$msRoots = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match 'Microsoft' }
Write-Output "Microsoft roots: $($msRoots.Count)"
# Check for auto-update disablement
$certReg = Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot' -Name 'DisableRootAutoUpdate' -ErrorAction SilentlyContinue
Write-Output "Root auto-update disabled: $($certReg.DisableRootAutoUpdate)"
```

## Remediation Steps

### Step 1: Check root certificate store health

```powershell
$roots = Get-ChildItem Cert:\LocalMachine\Root
$expired = $roots | Where-Object { $_.NotAfter -lt (Get-Date) }
$msRoots = $roots | Where-Object { $_.Subject -match 'Microsoft Root' }
Write-Output "Total root certs: $($roots.Count)"
Write-Output "Expired root certs: $($expired.Count)"
Write-Output "Microsoft root CAs: $($msRoots.Count)"
$autoUpdate = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot' -Name 'DisableRootAutoUpdate' -ErrorAction SilentlyContinue).DisableRootAutoUpdate
Write-Output "Root auto-update disabled by policy: $(if ($autoUpdate -eq 1) {'YES'} else {'NO'})"
```

Expected output: Certificate store status
On failure: continue

### Step 2: Enable automatic root certificate updates

```powershell
$regPath = 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot'
# Capture the ACTUAL pre-change value so rollback can restore it exactly (not assume a fixed
# value). "ABSENT" means the value did not exist and rollback should remove it again.
$origFile = "$env:SystemRoot\Temp\SOP070_orig_DisableRootAutoUpdate.txt"
if (Test-Path $regPath) {
    $val = (Get-ItemProperty $regPath -Name 'DisableRootAutoUpdate' -ErrorAction SilentlyContinue).DisableRootAutoUpdate
    if ($null -eq $val) { Set-Content -Path $origFile -Value 'ABSENT' -Force }
    else { Set-Content -Path $origFile -Value ([string]$val) -Force }
    if ($val -eq 1) {
        Set-ItemProperty $regPath -Name 'DisableRootAutoUpdate' -Value 0
        Write-Output "Root certificate auto-update enabled"
    } else { Write-Output "Auto-update already enabled" }
} else {
    Set-Content -Path $origFile -Value 'KEY_ABSENT' -Force
    Write-Output "No policy restricting root updates"
}
```

Expected output: Auto-update status
On failure: continue

### Step 3: Manually download and install current Microsoft root certificates

```powershell
try {
    # Download current root cert bundle via certutil
    $result = & certutil -generateSSTFromWU "$env:TEMP\roots.sst" 2>&1
    if (Test-Path "$env:TEMP\roots.sst") {
        $certs = Get-ChildItem "$env:TEMP\roots.sst"
        # Import to trusted root store
        & certutil -addstore Root "$env:TEMP\roots.sst" 2>&1 | Out-Null
        Remove-Item "$env:TEMP\roots.sst" -Force
        Write-Output "Root certificates updated from Windows Update"
    } else { Write-Output "Could not download root certs (network may be blocked)" }
} catch { Write-Output "Root cert update failed: $($_.Exception.Message)" }
```

Expected output: "Root certificates updated" or network issue noted
On failure: continue

### Step 4: Install critical Microsoft root CAs manually if download failed

```powershell
# Verify essential Microsoft roots exist
$essentialThumbprints = @(
    "3B1EFD3A66EA28B16697394703A72CA340A05BD5",  # Microsoft Root CA 2010
    "A43489159A520F0D93D032CCAF37E7FE20A8B419",  # Microsoft Root CA 2011
    "D4DE20D05E66FC53FE1A50882C78DB2852CAE474"   # Baltimore CyberTrust Root
)
$missing = @()
foreach ($tp in $essentialThumbprints) {
    $cert = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq $tp }
    if (-not $cert) { $missing += $tp }
}
if ($missing.Count -eq 0) { Write-Output "Essential Microsoft roots: ALL PRESENT" }
else { Write-Output "MISSING $($missing.Count) essential root(s): $($missing -join ', ')" }
```

Expected output: "Essential Microsoft roots: ALL PRESENT"
On failure: continue

### Step 5: Test certificate validation against Windows Update

```powershell
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $request = [System.Net.HttpWebRequest]::Create("https://windowsupdate.microsoft.com")
    $request.Timeout = 15000
    $response = $request.GetResponse()
    $response.Close()
    Write-Output "CERTIFICATE VALIDATION OK: HTTPS to WU succeeded"
} catch {
    if ($_.Exception.InnerException -match "certificate|trust|security") {
        Write-Output "CERTIFICATE STILL FAILING: $($_.Exception.InnerException.Message)"
    } else { Write-Output "Connection issue (may not be cert-related): $($_.Exception.Message)" }
}
```

Expected output: "CERTIFICATE VALIDATION OK"
On failure: abort

## Validation

```powershell
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $r = [System.Net.HttpWebRequest]::Create("https://download.windowsupdate.com")
    $r.Timeout = 10000
    $r.GetResponse().Close()
    "CERTIFICATE REMEDIATION OK"
} catch { "CERTIFICATE STILL FAILING" }
```

Expected: "CERTIFICATE REMEDIATION OK"

## Rollback

```powershell
# Restore the ACTUAL original DisableRootAutoUpdate state captured in Step 2 — do NOT assume
# it was disabled. If auto-update was originally enabled (or the value/key did not exist),
# this correctly restores that instead of forcing it to 1.
$regPath = 'HKLM:\SOFTWARE\Policies\Microsoft\SystemCertificates\AuthRoot'
$origFile = "$env:SystemRoot\Temp\SOP070_orig_DisableRootAutoUpdate.txt"
if (Test-Path $origFile) {
    $orig = (Get-Content $origFile -Raw).Trim()
    switch ($orig) {
        'KEY_ABSENT' {
            if (Test-Path $regPath) { Remove-ItemProperty $regPath -Name 'DisableRootAutoUpdate' -Force -ErrorAction SilentlyContinue }
            Write-Output "Restored original state: no auto-update policy value present"
        }
        'ABSENT' {
            if (Test-Path $regPath) { Remove-ItemProperty $regPath -Name 'DisableRootAutoUpdate' -Force -ErrorAction SilentlyContinue }
            Write-Output "Restored original state: DisableRootAutoUpdate value removed"
        }
        default {
            if (-not (Test-Path $regPath)) { New-Item $regPath -Force | Out-Null }
            Set-ItemProperty $regPath -Name 'DisableRootAutoUpdate' -Value ([int]$orig)
            Write-Output "Restored original DisableRootAutoUpdate = $orig"
        }
    }
} else {
    Write-Output "No captured original value found — leaving current auto-update policy unchanged"
}
```

## Escalation

If certificates cannot be updated:
- For air-gapped networks: manually export root certs from a connected machine and import
- Use `certutil -syncWithWU <directory>` on a connected machine, then copy CTL files
- Check if proxy is blocking `ctldl.windowsupdate.com` (certificate trust list endpoint)
- For Server 2012 R2: ensure KB2813430 is installed for SHA-2 support
- If CRL checking is timing out: temporarily disable revocation checking via registry
- Verify customer hasn't intentionally removed roots for compliance (discuss with security team)
