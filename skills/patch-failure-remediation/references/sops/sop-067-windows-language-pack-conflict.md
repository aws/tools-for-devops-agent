# SOP-067: Resolve Windows Patch Failure Due to Language Pack / MUI Conflicts

| Field | Value |
|-------|-------|
| ID | SOP-067 |
| Category | windows_language_pack_conflict |
| Severity | Low |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- `0x800F0986` ("CBS_E_LANG_NOT_APPLICABLE")
- `0x800F0908` ("CBS_E_NOT_APPLICABLE_FOR_LANGUAGE")
- Cumulative update fails on MUI/language pack validation step
- CBS.log shows "language neutral package requires language specific prerequisite"
- Update applicable on en-US systems but fails on localized installations
- Server with multiple language packs takes excessively long to patch

## Root Cause

Language pack conflicts during patching when:

- Installed language packs are out of date relative to the cumulative update
- Language pack was installed from a different OS build version
- Partial language pack installation left MUI resources inconsistent
- LCU contains language-specific components but matching LP is missing
- Server 2012 R2: LP installed from RTM media conflicts with post-SP updates
- Feature-on-Demand language resources missing from local component store
- Mixed architecture language packs (x86 LP on x64 system)

## Related Failure Patterns

- SOP-051 (Corrupt CBS) — LP conflicts can manifest as store corruption
- SOP-058 (SSU) — SSU may be needed for language pack servicing

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Identify the system's installed language packs

## Diagnosis

```powershell
$langs = & DISM /Online /Get-Intl 2>&1 | Select-String "Default|Installed"
$lps = & DISM /Online /Get-Packages /Format:Table 2>&1 | Select-String "LanguagePack|LanguageFeatures"
Write-Output "=== Language Config ==="
$langs
Write-Output "=== Installed Language Packs ==="
$lps | Select-Object -First 10
```

## Remediation Steps

### Step 1: Identify installed language packs and system locale

```powershell
$intl = & DISM /Online /Get-Intl 2>&1
$intl | Select-String "system locale|Default|UI language" | ForEach-Object { Write-Output $_.Line.Trim() }
$packages = & DISM /Online /Get-Packages /Format:Table 2>&1
$lps = $packages | Select-String "LanguagePack"
Write-Output "Installed language packs: $($lps.Count)"
$lps | ForEach-Object { Write-Output "  $($_.Line.Trim())" }
```

Expected output: Language configuration listed
On failure: continue

### Step 2: Check if language packs are outdated vs OS build

```powershell
$build = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').UBR
$packages = & DISM /Online /Get-Packages /Format:Table 2>&1
$lpPackages = $packages | Select-String "LanguagePack" | Select-String -NotMatch "en-US"
$outdated = @()
foreach ($lp in $lpPackages) {
    if ($lp.Line -match "Install Pending|Superseded") { $outdated += $lp.Line.Trim() }
}
Write-Output "OS UBR: $build"
Write-Output "Non-en-US language packs in non-current state: $($outdated.Count)"
$outdated | ForEach-Object { Write-Output "  $_" }
```

Expected output: LP status vs build
On failure: continue

### Step 3: Run DISM to clean up superseded language components

```powershell
& DISM /Online /Cleanup-Image /StartComponentCleanup 2>&1 | Select-String "operation completed|error"
Write-Output "Component cleanup for LP remnants: exit $LASTEXITCODE"
```

Expected output: "Component cleanup" with exit code
On failure: continue

### Step 4: Remove problematic non-default language packs (if not needed)

```powershell
$defaultLang = (Get-WinSystemLocale).Name.Split('-')[0]
$packages = & DISM /Online /Get-Packages /Format:List 2>&1
$lpNames = ($packages | Select-String "Package Identity.*LanguagePack" | ForEach-Object { ($_.Line -split ":")[1].Trim() }) | Where-Object { $_ -notmatch $defaultLang -and $_ -notmatch "en-US" }
if ($lpNames.Count -gt 0) {
    Write-Output "Non-essential LPs found: $($lpNames.Count)"
    Write-Output "NOTE: Removal requires customer approval — listing only"
    $lpNames | ForEach-Object { Write-Output "  Candidate for removal: $_" }
} else { Write-Output "No removable language packs identified" }
Write-Output "LP ASSESSMENT COMPLETE"
```

Expected output: "LP ASSESSMENT COMPLETE"
On failure: continue

### Step 5: Reset Windows Update and verify patch applicability

```powershell
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
Start-Service wuauserv
Write-Output "LP CONFLICT REMEDIATION READY"
```

Expected output: "LP CONFLICT REMEDIATION READY"
On failure: abort

## Validation

```powershell
$result = & DISM /Online /Cleanup-Image /CheckHealth 2>&1
if ($result -match "healthy") { "LP REMEDIATION OK" } else { "CBS HEALTH CHECK: $($result | Select-String 'repairable|corrupted|healthy')" }
```

Expected: "LP REMEDIATION OK"

## Rollback

Language pack removal cannot be easily reversed — requires reinstallation from media. Component cleanup is safe and non-reversible but only removes superseded content.

## Escalation

If language pack conflicts persist:
- Install updated language packs matching current OS build from Microsoft Update Catalog
- For Server 2012 R2: LP must match the servicing level — install LP then immediately apply latest rollup
- For Server 2016+: use Features on Demand ISO for language pack installation
- If customer needs non-English locale: update LP to same build number as current LCU
- Consider switching system locale to en-US if localization is not required
- Multiple LPs significantly increase patching time — recommend removing unused LPs
