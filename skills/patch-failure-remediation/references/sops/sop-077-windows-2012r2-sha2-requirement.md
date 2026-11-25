# SOP-077: Resolve Windows Patch Failure Due to Windows Server 2012 R2 SHA-2 Signing Requirement

| Field | Value |
|-------|-------|
| ID | SOP-077 |
| Category | windows_2012r2_sha2_requirement |
| Severity | High |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- All Windows Update operations fail after 2019-07 on Server 2012 R2
- `0x800B0101` ("A required certificate is not within its validity period")
- `0x80096010` ("The certificate's signer was not found")
- Cumulative updates refuse to install — signature validation failure
- WSUS scan returns 0 applicable updates despite patches being available
- CBS.log shows "signature hash algorithm is not supported"

## Root Cause

Since July 2019, Microsoft signs all Windows updates with SHA-2 only. Server 2012 R2 without the SHA-2 prerequisite updates cannot validate these signatures:

- KB4474419 (SHA-2 code signing support) not installed
- KB4490628 (Servicing Stack Update with SHA-2 support) not installed
- System was restored from backup/snapshot predating SHA-2 updates
- Image was created from original 2012 R2 media without SHA-2 prerequisites
- WSUS does not offer SHA-2 prerequisites because they were manually declined

## Related Failure Patterns

- SOP-058 (SSU Prerequisite) — SHA-2 SSU is the foundational requirement
- SOP-070 (Root Certificates) — certificate chain validation related
- SOP-024 (TLS Failure) — both are cryptographic prerequisite issues

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Instance is Windows Server 2012 R2 only (2016+ has SHA-2 built in)
- Instance has internet access or local package source available

## Diagnosis

```powershell
$os = (Get-CimInstance Win32_OperatingSystem).Caption
if ($os -notmatch '2012 R2') { Write-Output "NOT 2012 R2 — SHA-2 SOP not applicable"; return }
$sha2KB = Get-HotFix -Id KB4474419 -ErrorAction SilentlyContinue
$ssuKB = Get-HotFix -Id KB4490628 -ErrorAction SilentlyContinue
Write-Output "KB4474419 (SHA-2 support): $(if ($sha2KB) { 'INSTALLED' } else { 'MISSING' })"
Write-Output "KB4490628 (SHA-2 SSU): $(if ($ssuKB) { 'INSTALLED' } else { 'MISSING' })"
```

## Remediation Steps

### Step 1: Verify this is Windows Server 2012 R2

```powershell
$os = Get-CimInstance Win32_OperatingSystem
$build = $os.BuildNumber
Write-Output "OS: $($os.Caption) Build: $build"
if ($build -ne '9600') {
    Write-Output "NOT 2012 R2 (build 9600) — SHA-2 prereqs built into this OS version"
    Write-Output "SOP NOT APPLICABLE"
} else { Write-Output "Confirmed Server 2012 R2 — checking SHA-2 prerequisites" }
```

Expected output: OS confirmed as 2012 R2 or not applicable
On failure: abort

### Step 2: Check if SHA-2 prerequisite KBs are installed

```powershell
$required = @(
    @{KB='KB4474419'; Desc='SHA-2 code signing support'},
    @{KB='KB4490628'; Desc='Servicing Stack Update with SHA-2'}
)
$missing = @()
foreach ($r in $required) {
    $installed = Get-HotFix -Id $r.KB -ErrorAction SilentlyContinue
    if ($installed) { Write-Output "INSTALLED: $($r.KB) - $($r.Desc)" }
    else { Write-Output "MISSING: $($r.KB) - $($r.Desc)"; $missing += $r.KB }
}
Write-Output "Missing prerequisites: $($missing.Count)"
```

Expected output: KB installation status
On failure: continue

### Step 3: Download and install SHA-2 SSU (KB4490628) if missing

```powershell
$ssu = Get-HotFix -Id KB4490628 -ErrorAction SilentlyContinue
if (-not $ssu) {
    Write-Output "Attempting to install KB4490628 via Windows Update..."
    $session = New-Object -ComObject Microsoft.Update.Session
    $searcher = $session.CreateUpdateSearcher()
    $results = $searcher.Search("IsInstalled=0").Updates | Where-Object { $_.Title -match 'KB4490628|Servicing Stack' }
    if ($results.Count -gt 0) {
        $dl = $session.CreateUpdateDownloader()
        $toInstall = New-Object -ComObject Microsoft.Update.UpdateColl
        foreach ($u in $results) { $toInstall.Add($u) | Out-Null }
        $dl.Updates = $toInstall; $dl.Download() | Out-Null
        $inst = $session.CreateUpdateInstaller()
        $inst.Updates = $toInstall
        $r = $inst.Install()
        Write-Output "SSU install result: $($r.ResultCode)"
    } else { Write-Output "KB4490628 not found via WU — manual install required" }
} else { Write-Output "KB4490628 already installed" }
```

Expected output: SSU installed or already present
On failure: continue

### Step 4: Install SHA-2 code signing support (KB4474419) if missing

```powershell
$sha2 = Get-HotFix -Id KB4474419 -ErrorAction SilentlyContinue
if (-not $sha2) {
    Write-Output "Attempting to install KB4474419 via Windows Update..."
    $session = New-Object -ComObject Microsoft.Update.Session
    $searcher = $session.CreateUpdateSearcher()
    $results = $searcher.Search("IsInstalled=0").Updates | Where-Object { $_.Title -match 'KB4474419|SHA-2' }
    if ($results.Count -gt 0) {
        $dl = $session.CreateUpdateDownloader()
        $toInstall = New-Object -ComObject Microsoft.Update.UpdateColl
        foreach ($u in $results) { $toInstall.Add($u) | Out-Null }
        $dl.Updates = $toInstall; $dl.Download() | Out-Null
        $inst = $session.CreateUpdateInstaller()
        $inst.Updates = $toInstall
        $r = $inst.Install()
        Write-Output "SHA-2 support install result: $($r.ResultCode)"
    } else { Write-Output "KB4474419 not found via WU — manual install required" }
} else { Write-Output "KB4474419 already installed" }
```

Expected output: SHA-2 KB installed or already present
On failure: continue

### Step 5: Verify SHA-2 prerequisites are in place

```powershell
$sha2 = Get-HotFix -Id KB4474419 -ErrorAction SilentlyContinue
$ssu = Get-HotFix -Id KB4490628 -ErrorAction SilentlyContinue
if ($sha2 -and $ssu) { Write-Output "SHA-2 PREREQUISITES OK: Both KBs installed" }
elseif ($sha2 -or $ssu) { Write-Output "PARTIAL: SHA2=$([bool]$sha2) SSU=$([bool]$ssu) — reboot required before next patch cycle" }
else { Write-Output "SHA-2 PREREQUISITES MISSING: Manual installation required" }
```

Expected output: "SHA-2 PREREQUISITES OK"
On failure: abort

## Validation

```powershell
$sha2 = Get-HotFix -Id KB4474419 -ErrorAction SilentlyContinue
$ssu = Get-HotFix -Id KB4490628 -ErrorAction SilentlyContinue
if ($sha2 -and $ssu) { "SHA-2 REMEDIATION OK" } else { "SHA-2 STILL MISSING" }
```

Expected: "SHA-2 REMEDIATION OK"

## Rollback

SHA-2 support updates cannot be uninstalled and should not be removed — they are prerequisites for all future updates.

## Escalation

If SHA-2 KBs cannot be installed via WU:
- Download standalone packages from Microsoft Update Catalog:
  - KB4490628: https://www.catalog.update.microsoft.com/Search.aspx?q=KB4490628
  - KB4474419: https://www.catalog.update.microsoft.com/Search.aspx?q=KB4474419
- Install SSU first (KB4490628), reboot, then install KB4474419
- If neither can install: the existing SSU may be too old — find the earliest SHA-2 compatible SSU
- For WSUS environments: ensure these KBs are approved and not declined
- Consider if Server 2012 R2 is approaching end-of-extended-support — plan OS upgrade
