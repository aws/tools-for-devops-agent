# SOP-057: Resolve Windows Driver Update Failure / Blue Screen After Patching

| Field | Value |
|-------|-------|
| ID | SOP-057 |
| Category | windows_driver_update_failure |
| Severity | Critical |
| Risk Level | High |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- BSOD (Blue Screen of Death) after installing driver updates via Windows Update
- Instance unreachable after patching with driver updates included
- `0x800F0217` ("CBS_E_NEED_REBOOT with driver failure")
- PV driver or ENA driver incompatibility after update
- AWS NVMe driver conflict with Windows Update-provided driver
- Instance boots to recovery mode after driver patch
- Device Manager shows yellow exclamation on network or storage adapter

## Root Cause

Driver update failures on EC2 occur when:

- Windows Update pushes a generic driver that conflicts with AWS PV/ENA/NVMe drivers
- PV driver update breaks network connectivity on instances using Citrix PV
- ENA driver update introduces regression for specific instance types
- NVMe driver update breaks boot volume access on Nitro instances
- Third-party antivirus filter drivers conflict with updated network drivers
- Server 2012 R2: Citrix PV to AWS PV driver migration incomplete
- Server 2016+: Windows in-box driver overrides AWS-specific driver

## Related Failure Patterns

- SOP-020 (SSM Connectivity Loss) — driver failure causes connectivity loss
- SOP-022 (Reboot Race) — driver install during shutdown causes corruption

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- If instance is unreachable, use EC2 Serial Console or attach root volume to recovery instance

## Diagnosis

```powershell
Get-WinEvent -LogName System -MaxEvents 50 | Where-Object { $_.ProviderName -match 'BugCheck|Driver|ndis|storport' -and $_.Level -le 3 } | Select-Object TimeCreated,Id,Message | Format-List
Get-WindowsDriver -Online | Where-Object { $_.ProviderName -match 'Amazon|AWS|ENA|NVMe' } | Select-Object Driver,ProviderName,Version,Date
```

## Remediation Steps

### Step 1: Identify AWS-specific drivers and their versions

```powershell
$awsDrivers = Get-WindowsDriver -Online | Where-Object { $_.ClassName -match 'Net|SCSIAdapter|System' -and ($_.ProviderName -match 'Amazon|AWS' -or $_.OriginalFileName -match 'ena|nvme|xen') }
$awsDrivers | ForEach-Object { Write-Output "$($_.ClassName): $($_.ProviderName) v$($_.Version) ($($_.Date))" }
Write-Output "AWS drivers found: $($awsDrivers.Count)"
```

Expected output: AWS drivers listed
On failure: continue

### Step 2: Check for pending driver installations that could cause issues

```powershell
$staged = Get-WindowsDriver -Online | Where-Object { $_.ClassName -match 'Net|SCSIAdapter' -and $_.ProviderName -notmatch 'Amazon|AWS|Microsoft' }
if ($staged) {
    $staged | ForEach-Object { Write-Output "THIRD-PARTY: $($_.ClassName) - $($_.ProviderName) v$($_.Version)" }
    Write-Output "WARNING: Non-AWS drivers found for critical device classes"
} else { Write-Output "No third-party critical drivers detected" }
```

Expected output: Driver inventory
On failure: continue

### Step 3: Hide problematic driver updates from Windows Update

```powershell
$session = New-Object -ComObject Microsoft.Update.Session
$searcher = $session.CreateUpdateSearcher()
$driverUpdates = $searcher.Search("IsInstalled=0 and Type='Driver'").Updates
$hidden = 0
foreach ($u in $driverUpdates) {
    if ($u.Title -match 'network|ethernet|storage|scsi|nvme') {
        $u.IsHidden = $true
        $hidden++
        Write-Output "Hidden: $($u.Title)"
    }
}
Write-Output "Hidden $hidden driver update(s) from Windows Update"
```

Expected output: Driver updates hidden count
On failure: continue

### Step 4: Set registry to prevent driver updates via Windows Update

```powershell
$path = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
if (-not (Test-Path $path)) { New-Item $path -Force | Out-Null }
Set-ItemProperty $path -Name 'ExcludeWUDriversInQualityUpdate' -Value 1 -Type DWord
Write-Output "Driver exclusion policy set"
```

Expected output: "Driver exclusion policy set"
On failure: continue

### Step 5: Verify critical AWS drivers are current and functional

```powershell
$ena = Get-NetAdapter | Where-Object { $_.InterfaceDescription -match 'ENA|Elastic' }
$net = Test-NetConnection -ComputerName 169.254.169.254 -Port 80 -WarningAction SilentlyContinue
if ($ena -and $net.TcpTestSucceeded) { Write-Output "DRIVER PROTECTION OK: ENA active, IMDS reachable" }
elseif ($ena) { Write-Output "DRIVER OK: ENA present but IMDS check skipped" }
else { Write-Output "WARNING: ENA adapter not found — check instance type" }
```

Expected output: "DRIVER PROTECTION OK"
On failure: abort

## Validation

```powershell
$policy = (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name ExcludeWUDriversInQualityUpdate -ErrorAction SilentlyContinue).ExcludeWUDriversInQualityUpdate
$net = Get-NetAdapter | Where-Object { $_.Status -eq 'Up' }
if ($policy -eq 1 -and $net) { "DRIVER REMEDIATION OK" } else { "CHECK REQUIRED: Policy=$policy NetAdapters=$($net.Count)" }
```

Expected: "DRIVER REMEDIATION OK"

## Rollback

```powershell
Remove-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'ExcludeWUDriversInQualityUpdate' -Force -ErrorAction SilentlyContinue
Write-Output "Driver exclusion policy removed — drivers will update via WU again"
```

## Escalation

If instance is unreachable after driver update:
- Use EC2 Serial Console to access recovery environment
- Attach root volume to rescue instance, roll back driver from `\Windows\System32\DriverStore`
- For ENA issues: verify instance type supports ENA, install latest from https://s3.amazonaws.com/ec2-windows-drivers-downloads/ENA/Latest/AwsEnaNetworkDriver.zip
- For NVMe boot issues: boot into Safe Mode via bcdedit, roll back NVMe driver
- For Server 2012 R2 on PV: ensure AWS PV drivers are installed before allowing driver WU updates
- Contact AWS Support if Nitro instance loses NVMe boot volume visibility
