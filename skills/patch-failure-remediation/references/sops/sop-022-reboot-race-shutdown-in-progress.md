# SOP-022: Resolve "A System Shutdown Is In Progress" Reboot-Race Patch Failures

| Field | Value |
|-------|-------|
| ID | SOP-022 |
| Category | reboot_race_shutdown_in_progress |
| Severity | Medium |
| Risk Level | Low |
| Platforms | Windows |
| Distributions | Windows Server 2016, 2019, 2022, 2025 |
| Requires Reboot | No (waits for an in-progress reboot to finish) |
| Estimated Duration | up to 600 seconds (bounded wait for boot) |
| Last Validated | 2026-06-11 |

## Symptoms

- `Invoke-PatchBaselineOperation : A system shutdown is in progress.`
- `failed to run commands: exit status 0xffffffff`
- The failure occurs immediately at patch start, with no patch install attempted
- Often on instances that were rebooting from a prior patch cycle or another orchestrated restart

## Root Cause

The patch operation started while the OS was **already shutting down or rebooting** (commonly the reboot from a previous patch install, or a separate maintenance/restart action overlapping the patch window). Windows rejects new operations during shutdown, so `Invoke-PatchBaselineOperation` aborts immediately. This is a **timing/orchestration race**, not a patch-content or connectivity problem. It is transient: once the instance finishes booting, a retry succeeds.

## Related Failure Patterns

- SOP-017 (Windows Lock Conflict) — a different concurrency failure (two patch ops, lock file)
- SOP-019 (Pending-Reboot) — when patches are installed but the reboot hasn't happened yet
- SOP-018 (Transient Post-Scan Auto-Close) — the post-reboot re-scan often shows the instance is actually fine

## Prerequisites

- Instance exists and is expected to return online after the reboot
- Operator can run `AWS-RunPowerShellScript` and `describe-instance-information`
- A maintenance/change window is still open for a single retry

## Diagnosis

Confirm the instance is mid-reboot rather than genuinely failed:

```bash
# Is SSM reporting the agent online yet?
aws ssm describe-instance-information --filters Key=InstanceIds,Values=<instance-id> \
  --region <region> --query "InstanceInformationList[0].{Ping:PingStatus,LastPing:LastPingDateTime}" --output table
```

If Online, check uptime / pending shutdown in-guest:

```powershell
$os=Get-CimInstance Win32_OperatingSystem
"LastBootUpTime=$($os.LastBootUpTime)  UptimeMin=$([math]::Round(((Get-Date)-$os.LastBootUpTime).TotalMinutes,1))"
$pending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
"RebootPending=$pending"
```

**Decision rule (evaluate once):**
- `PingStatus != Online` OR uptime very low / a shutdown is active → the reboot is in progress → **Step 1** (bounded wait).
- `PingStatus = Online`, healthy uptime, no pending reboot → the race already cleared → **Step 2** (confirm readiness).

## Remediation Steps

> This SOP uses a **bounded wait** to let the in-progress reboot complete. It must never loop indefinitely. Hard cap: poll boot completion at most **10 times (≈10 minutes)**, then confirm readiness for the next scheduled patch cycle. It does NOT re-invoke patching.

### Step 1: Wait for boot to complete — BOUNDED (max 10 polls, ~60s each)

```bash
# bash control loop with a hard cap; no infinite loop
ok=false
for i in $(seq 1 10); do
  ping=$(aws ssm describe-instance-information \
    --filters Key=InstanceIds,Values=<instance-id> \
    --region <region> --query "InstanceInformationList[0].PingStatus" --output text 2>/dev/null)
  if [ "$ping" = "Online" ]; then ok=true; break; fi
  sleep 60
done
echo "ONLINE=$ok after $i poll(s)"
```

Expected: `ONLINE=true` within 10 polls.
- If `ONLINE=true` → confirm no shutdown in progress, then Step 2.
- If still not Online after 10 polls → **STOP**. Do not loop further. The instance is not simply rebooting (it may be impaired/stuck) → route to SOP-020 (connectivity) and Escalation.

### Validation (after wait, before retry)

Before issuing the single retry, confirm the instance is genuinely back and not still finalizing a reboot — so the retry does not race the tail of the same reboot:

```bash
# 1. Agent reports Online
aws ssm describe-instance-information --filters Key=InstanceIds,Values=<instance-id> \
  --region <region> --query "InstanceInformationList[0].PingStatus" --output text
```

```powershell
# 2. In-guest (via AWS-RunPowerShellScript): no pending reboot + fresh uptime
$pending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
"RebootPending=$pending  UptimeMin=$([math]::Round(((Get-Date)-(Get-CimInstance Win32_OperatingSystem).LastBootUpTime).TotalMinutes,1))"
```

Expected: `PingStatus=Online` **and** `RebootPending=False`.
- If both hold → proceed to Step 2.
- If `RebootPending=True` or still not Online → the host is still finalizing the reboot; **do not** issue the retry into a rebooting instance. STOP and route to Escalation (do not loop — Step 1's wait was already bounded).

### Step 2: Confirm instance is ready for next patch cycle

The reboot race has cleared. The patch will be retried automatically by the next scheduled maintenance window run.

```powershell
$pending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$os = Get-CimInstance Win32_OperatingSystem
$uptime = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalMinutes, 1)
if (-not $pending -and $uptime -gt 5) { "READY for next patch cycle (uptime: ${uptime} min)" } else { "NOT READY - RebootPending=$pending, Uptime=${uptime} min" }
```

Expected output: "READY for next patch cycle"
On failure: abort — if still not ready after the bounded wait, escalate. Do not retry patching into a rebooting instance.

## Validation

```powershell
$pending = Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending'
$os = Get-CimInstance Win32_OperatingSystem
$uptime = [math]::Round(((Get-Date) - $os.LastBootUpTime).TotalMinutes, 1)
if (-not $pending -and $uptime -gt 5) { "REBOOT RACE RESOLVED (uptime: ${uptime} min)" } else { "REBOOT RACE NOT RESOLVED - RebootPending=$pending, Uptime=${uptime} min" }
```

Expected: "REBOOT RACE RESOLVED"

## Rollback

No changes are made to the instance (only a bounded wait for the reboot to complete). Nothing to roll back.

## Prevention

- **Stagger reboots and patch invocations** so a previous cycle's reboot completes before the next patch starts (e.g., separate reboot window, or `RebootOption=NoReboot` during install + a controlled reboot afterward — see SOP-019).
- Ensure no other automation (State Manager association, custom scheduler, app deployment) restarts instances during the patch window.
- Increase spacing between sequential patch tasks targeting the same instance.

## Escalation

If the single retry fails again or the instance never returns Online:
- Capture: `PingStatus`, `LastBootUpTime`/uptime, the `A system shutdown is in progress` command output, and any concurrent restart automation.
- If not Online: route to **SOP-020** (SSM connectivity loss).
- If a recurring external restart is suspected: escalate to identify the competing reboot source. Do not keep retrying — repeated retries will not fix an orchestration race.
