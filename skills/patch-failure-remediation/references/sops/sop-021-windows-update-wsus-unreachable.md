# SOP-021: Resolve Windows Update / WSUS Endpoint Unreachable During Patching

| Field | Value |
|-------|-------|
| ID | SOP-021 |
| Category | windows_update_wsus_unreachable |
| Severity | High |
| Risk Level | Medium |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | No |
| Estimated Duration | 180 seconds |
| Last Validated | 2026-06-11 |

## Symptoms

- Patch fails and PatchDiag pre-patch validation shows: `WindowsUpdateEndpointsReachability: Windows Update is not reachable` and `UpdateServiceConfigurationStatus: Not Healthy`
- `Invoke-PatchBaselineOperation : The find operation did not complete successfully. Additional failure information from Windows Update: HResult: -2145107940` (= `0x8024401C`, WU HTTP request timeout)
- A `HRESULT: 0` variant accompanied by `Windows Update is not reachable`
- `failed to run commands: exit status 0xffffffff`
- PatchDiag shows `UseWuServerRegKey: 1` (instance is configured to use an internal WSUS server)
- Compliance flaps COMPLIANT → NON_COMPLIANT across cycles (succeeds only when WSUS is reachable)

## Root Cause

The instance is configured by Group Policy to obtain updates from an **internal WSUS server** (`UseWUServer=1`) instead of public Microsoft Update. When that WSUS server — or the network path to it — is unavailable during the maintenance window, the Windows Update Agent (WUA) cannot complete the scan/install and times out. Common underlying causes:

- WSUS server down, overloaded, or its IIS app pool stopped during the window
- Network path blocked: security group / NACL / route table / firewall between the patched subnet and WSUS (typically TCP 8530 HTTP or 8531 HTTPS)
- DNS cannot resolve the WSUS hostname configured in `WUServer`
- Proxy required for WSUS but not configured for the WUA (`netsh winhttp` proxy / WinHTTP)
- A stale/incorrect `WUServer` GPO value pointing at a decommissioned WSUS host
- WSUS server certificate invalid (when using 8531/HTTPS)

This is an **infrastructure/configuration** problem, not an OS package problem. The fix is usually on the WSUS server or the network, not on the instance.

## Related Failure Patterns

- SOP-003 (Network Unreachable) — Linux equivalent for repo connectivity
- SOP-016 (WPAD Proxy) — Windows proxy autodiscovery issues that can also break WU reachability
- SOP-018 (Transient Post-Scan Auto-Close) — do NOT auto-close these; they are real and recur

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Operator can run `AWS-RunPowerShellScript`
- Knowledge of the expected WSUS endpoint/owner (for escalation)

## Diagnosis

All steps are **read-only**. Run via `AWS-RunPowerShellScript`:

```powershell
# 1. Is the instance pointed at WSUS, and where?
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$au = "$wu\AU"
$useWsus = (Get-ItemProperty $au -Name UseWUServer -ErrorAction SilentlyContinue).UseWUServer
$server  = (Get-ItemProperty $wu -Name WUServer    -ErrorAction SilentlyContinue).WUServer
"UseWUServer=$useWsus  WUServer=$server"

# 2. Can we resolve and reach the WSUS host/port?
if ($server) {
  $u = [Uri]$server
  # WUServer often omits the port; [Uri].Port would then return the scheme default (80/443), not the WSUS port.
  # Prefer an explicitly configured PortNumber, else the port in the URL, else the WSUS default (8530 HTTP / 8531 HTTPS).
  $portReg = (Get-ItemProperty $wu -Name PortNumber -ErrorAction SilentlyContinue).PortNumber
  if ($portReg) { $port = [int]$portReg } elseif (-not $u.IsDefaultPort) { $port = $u.Port } elseif ($u.Scheme -eq 'https') { $port = 8531 } else { $port = 8530 }
  "Resolving $($u.Host) ... (port $port)"; Resolve-DnsName $u.Host -ErrorAction SilentlyContinue | Select-Object Name,IPAddress
  Test-NetConnection -ComputerName $u.Host -Port $port -InformationLevel Detailed
}

# 3. WUA service + last error
Get-Service wuauserv | Select-Object Status,StartType
(New-Object -ComObject Microsoft.Update.AutoUpdate).Results | Select-Object LastSearchSuccessDate,LastInstallationSuccessDate
```

**Decision rule (no loop — evaluate once, branch):**
- `UseWUServer=1` AND `Test-NetConnection` to WSUS **fails** → WSUS/network problem → **Step 1** (escalate) or **Step 2** (approved fallback).
- `UseWUServer=1` AND WSUS reachable → likely WSUS-side (app pool/content) → **escalate to WSUS owner** (Escalation).
- `UseWUServer=0`/absent → not a WSUS case; the instance uses Microsoft Update — re-route to SOP-003-style network/proxy checks and the public WU endpoints.

## Remediation Steps

> This SOP performs **diagnosis and a single, bounded re-scan**. It does **not** loop. Configuration changes to the update source require approval (Step 2) because GPO governs them and they affect the customer's patch-source policy.

### Step 1: Confirm reachability with a bounded check (max 3 probes), then decide

```powershell
$wu='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$server=(Get-ItemProperty $wu -Name WUServer -ErrorAction SilentlyContinue).WUServer
$ok=$false
if($server){ $u=[Uri]$server; $portReg=(Get-ItemProperty $wu -Name PortNumber -ErrorAction SilentlyContinue).PortNumber; if($portReg){$port=[int]$portReg}elseif(-not $u.IsDefaultPort){$port=$u.Port}elseif($u.Scheme -eq 'https'){$port=8531}else{$port=8530}; foreach($i in 1..3){ if((Test-NetConnection $u.Host -Port $port).TcpTestSucceeded){$ok=$true;break}; Start-Sleep 5 } }
"WSUS_REACHABLE=$ok"
```

Expected: `WSUS_REACHABLE=True` if the transient window has passed.
- If `True` → go to Step 3 (re-scan once).
- If `False` after 3 probes → **STOP looping**; this is an infrastructure outage. Go to Escalation (do NOT keep retrying the patch against an unreachable server).

### Step 2 (OPTIONAL, REQUIRES APPROVAL): Temporary fallback to Microsoft Update

Only if the customer approves and the instances are allowed to reach public Microsoft Update. **Note:** Group Policy refresh will revert `UseWUServer`; this is a temporary, one-cycle workaround, not a fix.

```powershell
# REQUIRES CHANGE APPROVAL — alters update source
Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name UseWUServer -Value 0
Restart-Service wuauserv
"Temporarily set UseWUServer=0 (will be reverted by next GPO refresh)"
```

On failure or if not approved: skip to Escalation.

### Step 3: Verify WSUS connectivity is restored

Once WSUS is reachable (either transient issue cleared or Step 2 fallback applied), confirm the Windows Update Agent can communicate:

```powershell
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$server = (Get-ItemProperty $wu -Name WUServer -ErrorAction SilentlyContinue).WUServer
if ($server) { $u = [Uri]$server; $portReg = (Get-ItemProperty $wu -Name PortNumber -ErrorAction SilentlyContinue).PortNumber; if ($portReg) { $port = [int]$portReg } elseif (-not $u.IsDefaultPort) { $port = $u.Port } elseif ($u.Scheme -eq 'https') { $port = 8531 } else { $port = 8530 }; $result = Test-NetConnection -ComputerName $u.Host -Port $port -WarningAction SilentlyContinue; if ($result.TcpTestSucceeded) { "WSUS connectivity restored" } else { "WSUS still unreachable" } } else { "No WSUS configured" }
```

Expected output: "WSUS connectivity restored"
On failure: abort — WSUS is still unreachable; escalate to the WSUS server owner and network team. Do not retry patching against an unreachable server.

## Validation

```powershell
$wu = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$server = (Get-ItemProperty $wu -Name WUServer -ErrorAction SilentlyContinue).WUServer
if ($server) { $u = [Uri]$server; $portReg = (Get-ItemProperty $wu -Name PortNumber -ErrorAction SilentlyContinue).PortNumber; if ($portReg) { $port = [int]$portReg } elseif (-not $u.IsDefaultPort) { $port = $u.Port } elseif ($u.Scheme -eq 'https') { $port = 8531 } else { $port = 8530 }; $result = Test-NetConnection -ComputerName $u.Host -Port $port -WarningAction SilentlyContinue; if ($result.TcpTestSucceeded) { "WSUS REMEDIATION OK" } else { "WSUS REMEDIATION FAILED" } } else { "No WSUS configured - using Microsoft Update" }
(New-Object -ComObject Microsoft.Update.AutoUpdate).Results | Select-Object LastSearchSuccessDate
```

Expected: "WSUS REMEDIATION OK" with a recent LastSearchSuccessDate

## Rollback

```powershell
# If Step 2 fallback was applied and you must restore WSUS immediately (GPO would do this anyway):
Set-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU' -Name UseWUServer -Value 1
Restart-Service wuauserv
```

No rollback is needed for the read-only diagnosis path.

## Prevention

- Monitor WSUS availability/capacity and align its maintenance with the patch window (don't restart WSUS/IIS during the window).
- Add a **pre-window WSUS reachability pre-flight** (Test-NetConnection from a sample instance in each patch subnet); alert and defer affected instances rather than letting them fail.
- Validate the `WUServer` GPO value points at a live WSUS host; remove stale entries.
- Ensure SG/route/proxy/DNS from every patched subnet to WSUS (8530/8531) is correct.

## Escalation

If WSUS/network cannot be made reachable within the window:
- Capture: `UseWUServer`, `WUServer`, `Test-NetConnection` output, `Resolve-DnsName` result, and the PatchDiag `WindowsUpdateEndpointsReachability` line.
- Escalate to the **WSUS server owner and the network team** with subnet/SG/route IDs and the WSUS host:port.
- Do not repeatedly re-run patching against an unreachable WSUS — it will keep failing identically (this SOP intentionally caps retries at one re-scan).
