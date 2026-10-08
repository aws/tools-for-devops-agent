# Windows Update service Disabled (0x80070422)

**Signatures:** patch baseline fails to start the update service, `0x80070422` "The service cannot
be started", `Get-Service wuauserv` shows `StartType: Disabled`, AWS-RunPatchBaseline exits with no
patches scanned. **Disabled ≠ Stopped** — SSM/patch baseline can start a Stopped/Manual service, but
not a Disabled one.

## Diagnose
```powershell
Get-Service wuauserv,bits | Select Name,Status,StartType
```

## Fix — re-enable then start
```powershell
Set-Service -Name wuauserv -StartupType Automatic
Start-Service wuauserv -ErrorAction SilentlyContinue
# BITS is also required for downloads:
Get-Service bits | ? StartType -eq 'Disabled' | % { Set-Service bits -StartupType Manual; Start-Service bits }
Get-Service wuauserv,bits | Select Name,Status,StartType
```

## Verify
```powershell
$s=Get-Service wuauserv; if($s.StartType -ne 'Disabled'){"WU SERVICE ENABLED"}else{"STILL DISABLED"}
$r=(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().Search("IsInstalled=0 and Type='Software'"); "scan OK: $($r.Updates.Count) updates"
```

## Escalation / important
- **A GPO may re-disable the service on the next refresh (~90 min)** — if it flips back, the customer must fix the GPO (this is a policy blocker, see the patch-policy skill). Re-enabling here is only durable if no GPO enforces Disabled.
- If the service was disabled intentionally (hardening / third-party patch tool), get customer approval before enabling; coordinate coexistence.
- Rollback if needed: `Set-Service wuauserv -StartupType Disabled; Stop-Service wuauserv -Force`.
