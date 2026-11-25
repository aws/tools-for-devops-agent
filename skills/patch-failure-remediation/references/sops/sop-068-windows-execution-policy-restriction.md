# SOP-068: Resolve Windows Update Failure Due to .NET/PowerShell Execution Policy Restriction

| Field | Value |
|-------|-------|
| ID | SOP-068 |
| Category | windows_execution_policy_restriction |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 60 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- SSM patch operation fails with "scripts have been disabled on this system"
- PowerShell-based patch scanning/installation cannot execute
- `AWS-RunPatchBaseline` document fails at script execution step
- "Execution of scripts is disabled on this system" in SSM output
- Constrained Language Mode blocking patch assessment scripts
- AppLocker or WDAC blocking SSM agent's PowerShell scripts

## Root Cause

Execution restrictions block SSM patch operations when:

- PowerShell ExecutionPolicy set to "Restricted" or "AllSigned" via GPO
- Constrained Language Mode enforced by AppLocker/WDAC policy
- AppLocker DLL rules blocking SSM agent modules
- Windows Defender Application Control (WDAC) code integrity policy blocking unsigned scripts
- User-level execution policy overriding machine policy
- Server 2012 R2: .NET 2.0 CLR loaded instead of .NET 4.x for SSM operations
- Software Restriction Policies (SRP) blocking script paths

## Related Failure Patterns

- SOP-056 (GPO Blocking) — same GPO often sets execution policy
- SOP-061 (AV Interference) — application control can block scripts

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)

## Diagnosis

```powershell
Get-ExecutionPolicy -List | Format-Table Scope,ExecutionPolicy
$lm = $ExecutionContext.SessionState.LanguageMode
Write-Output "Language Mode: $lm"
Get-AppLockerPolicy -Effective -ErrorAction SilentlyContinue | Select-Object -ExpandProperty RuleCollections | Where-Object { $_.Count -gt 0 }
```

## Remediation Steps

### Step 1: Check current execution policy at all scopes

```powershell
$policies = Get-ExecutionPolicy -List
$policies | ForEach-Object { Write-Output "$($_.Scope): $($_.ExecutionPolicy)" }
$langMode = $ExecutionContext.SessionState.LanguageMode
Write-Output "Language Mode: $langMode"
$effective = Get-ExecutionPolicy
Write-Output "Effective: $effective"
```

Expected output: Policies listed with effective result
On failure: continue

### Step 2: Set execution policy to allow SSM scripts

```powershell
try {
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine -Force -ErrorAction Stop
    Write-Output "ExecutionPolicy set to RemoteSigned (LocalMachine)"
} catch {
    # GPO may be overriding — try bypass for process
    Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force -ErrorAction SilentlyContinue
    Write-Output "GPO blocking LocalMachine change — set Bypass for Process scope"
}
```

Expected output: Execution policy set
On failure: continue

### Step 3: Check and handle Constrained Language Mode

```powershell
$langMode = $ExecutionContext.SessionState.LanguageMode
if ($langMode -eq 'ConstrainedLanguage') {
    # Check if __PSLockdownPolicy is set
    $lockdown = [Environment]::GetEnvironmentVariable('__PSLockdownPolicy', 'Machine')
    if ($lockdown) {
        [Environment]::SetEnvironmentVariable('__PSLockdownPolicy', $null, 'Machine')
        Write-Output "Removed __PSLockdownPolicy environment variable"
    }
    Write-Output "WARNING: Constrained Language Mode active — may be enforced by WDAC/AppLocker"
} else { Write-Output "Language Mode OK: $langMode" }
```

Expected output: Language mode status
On failure: continue

### Step 4: Verify SSM agent can execute PowerShell

```powershell
$ssmPath = "${env:ProgramFiles}\Amazon\SSM"
$testScript = Join-Path $ssmPath "sop_test_$(Get-Random).ps1"
try {
    Set-Content $testScript -Value 'Write-Output "SSM_EXEC_OK"'
    $result = & powershell.exe -ExecutionPolicy Bypass -File $testScript 2>&1
    Remove-Item $testScript -Force
    if ($result -match "SSM_EXEC_OK") { Write-Output "EXECUTION POLICY REMEDIATION OK" }
    else { Write-Output "EXECUTION ISSUE: $result" }
} catch { Write-Output "EXECUTION BLOCKED: $($_.Exception.Message)" }
```

Expected output: "EXECUTION POLICY REMEDIATION OK"
On failure: abort

## Validation

```powershell
$ep = Get-ExecutionPolicy
$lm = $ExecutionContext.SessionState.LanguageMode
if ($ep -in @('RemoteSigned','Bypass','Unrestricted') -and $lm -eq 'FullLanguage') { "EXECUTION POLICY OK" }
else { "POLICY ISSUE: EP=$ep LM=$lm" }
```

Expected: "EXECUTION POLICY OK"

## Rollback

```powershell
Set-ExecutionPolicy -ExecutionPolicy Restricted -Scope LocalMachine -Force -ErrorAction SilentlyContinue
Write-Output "Execution policy reverted to Restricted"
```

## Escalation

If execution policy cannot be changed:
- GPO is enforcing policy: contact customer AD team to add exception for SSM
- AppLocker: add publisher rule for Amazon SSM agent binaries
- WDAC: create supplemental policy allowing SSM agent code integrity
- For Constrained Language Mode: only WDAC policy removal can fully disable it
- SSM can use `-ExecutionPolicy Bypass` at process level as workaround
- Verify SSM agent version — newer versions handle policy restrictions better
