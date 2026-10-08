# Reboot race — "A system shutdown is in progress"

**Signatures:** `Invoke-PatchBaselineOperation : A system shutdown is in progress.`, `failed to run
commands: exit status 0xffffffff`, the failure hits immediately at patch start with **no install
attempted**, often right after a prior patch cycle's reboot or an overlapping restart action.

**Root cause:** the patch started while the OS was **already shutting down/rebooting**; Windows
rejects new operations during shutdown. This is a **timing/orchestration race**, not a patch-content
or connectivity problem — and it's transient: once boot finishes, a retry succeeds.

## Diagnose — mid-reboot vs genuinely failed
```bash
aws ssm describe-instance-information --filters Key=InstanceIds,Values=<id> --region <region> \
  --query "InstanceInformationList[0].{Ping:PingStatus,LastPing:LastPingDateTime}" --output table
```
```powershell
# if Online, check uptime + pending shutdown in-guest:
$os=Get-CimInstance Win32_OperatingSystem
"UptimeMin=$([math]::Round(((Get-Date)-$os.LastBootUpTime).TotalMinutes,1)) RebootPending=$(Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')"
```
Decision: not Online / very low uptime / shutdown active → reboot in progress → bounded wait. Online +
healthy uptime + no pending reboot → race already cleared → confirm readiness.

## Bounded wait — NEVER loop indefinitely (max ~10 polls / ~10 min)
```bash
ok=false
for i in $(seq 1 10); do
  ping=$(aws ssm describe-instance-information --filters Key=InstanceIds,Values=<id> --region <region> \
    --query "InstanceInformationList[0].PingStatus" --output text 2>/dev/null)
  [ "$ping" = "Online" ] && { ok=true; break; }
  sleep 60
done
echo "ONLINE=$ok after $i poll(s)"
```
- `ONLINE=true` → confirm readiness, then allow the next scheduled cycle / a single retry.
- Still not Online after 10 polls → **STOP**. It's impaired, not racing → route to SSM-connectivity triage + escalate. Do not keep polling.

## Confirm readiness BEFORE any retry
```powershell
$os=Get-CimInstance Win32_OperatingSystem
$up=[math]::Round(((Get-Date)-$os.LastBootUpTime).TotalMinutes,1)
$pending=Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
if(-not $pending -and $up -gt 5){"REBOOT RACE RESOLVED (uptime ${up}m)"}else{"NOT READY RebootPending=$pending Uptime=${up}m"}
```
`RebootPending=True` or still offline → do **not** retry into a rebooting host; escalate. No changes
are made here (only a wait) → nothing to roll back.

## Prevention / escalation
- Stagger reboots vs patch invocations; use `NoReboot` install + a controlled reboot after (see pending-reboot).
- Ensure no other automation restarts instances during the window.
- Recurring race → identify the competing reboot source; repeated retries won't fix an orchestration race.
