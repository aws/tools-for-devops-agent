# WSUS routing / unreachable WSUS (UseWUServer=1)

**Signatures:** `0x8024401C` (WU HTTP timeout), PatchDiag "Windows Update is not reachable" /
"UpdateServiceConfigurationStatus: Not Healthy", `UseWuServerRegKey: 1`, compliance flapping
COMPLIANT↔NON_COMPLIANT. The instance is GPO-configured to use an **internal WSUS server**
(`UseWUServer=1`); if WSUS or the network path is down, WUA times out.

**This is an infrastructure/config problem, not an OS fix.** Do NOT loop-retry.

## Diagnose (read-only)
```powershell
$wu='HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate'
$use=(Get-ItemProperty "$wu\AU" -Name UseWUServer -EA SilentlyContinue).UseWUServer
$srv=(Get-ItemProperty $wu -Name WUServer -EA SilentlyContinue).WUServer
"UseWUServer=$use WUServer=$srv"
if($srv){ $u=[Uri]$srv; Resolve-DnsName $u.Host -EA SilentlyContinue | Select Name,IPAddress; Test-NetConnection $u.Host -Port $u.Port -InformationLevel Detailed }
```

## Decide (evaluate once — no loop)
- `UseWUServer=1` and TCP test to WSUS (8530/8531) **fails** → WSUS/network outage → **escalate**, do not retry.
- `UseWUServer=1` and WSUS reachable → likely WSUS-side (IIS app pool/content) → escalate to WSUS owner.
- `UseWUServer=0`/absent → not a WSUS case; it's a Microsoft-Update path issue (proxy/TLS/cert references).

## Temporary fallback (REQUIRES APPROVAL — reverts on GPO refresh)
```powershell
Set-ItemProperty "$wu\AU" -Name UseWUServer -Value 0; Restart-Service wuauserv
# one-cycle workaround only; GPO will restore UseWUServer=1 on next refresh
```

## Escalation
- Capture `UseWUServer`, `WUServer`, `Test-NetConnection`, `Resolve-DnsName`, PatchDiag reachability line.
- Escalate to the WSUS server owner + network team with subnet/SG/route IDs and WSUS host:port (8530 HTTP / 8531 HTTPS).
- Stale `WUServer` pointing at a decommissioned host → fix the GPO.
- WSUS on 8531 with an invalid server cert → WSUS-side cert fix.
