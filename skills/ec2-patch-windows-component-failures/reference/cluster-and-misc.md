# Failover cluster node, language pack, corrupt profile

## Windows Server Failover Cluster (WSFC) node — drain BEFORE reboot
**Signatures:** patch needs a reboot but the node is an active cluster owner, `0x80070426` (cluster
service dependency), CSV locked during install, reboot blocked by quorum, SQL AlwaysOn / Hyper-V
resource prevents reboot, CAU conflicts with SSM. **High-risk — never reboot a clustered node blind.**

```powershell
Import-Module FailoverClusters -EA SilentlyContinue
if(-not (Get-Cluster -EA SilentlyContinue)){ "NOT A CLUSTER NODE"; return }
$me=$env:COMPUTERNAME
Get-ClusterNode | Select Name,State
Get-ClusterGroup | ? {$_.OwnerNode -eq $me -and $_.State -eq 'Online'} | Select Name,GroupType
# drain owned groups, then suspend the node:
Get-ClusterGroup | ? {$_.OwnerNode -eq $me -and $_.State -eq 'Online' -and $_.Name -ne 'Cluster Group'} | % { Move-ClusterGroup -Name $_.Name | Out-Null }
Suspend-ClusterNode -Name $me -Drain
```
**Ready-to-reboot check:** node `State=Paused` AND 0 owned online groups. **Never suspend the last
online node** (quorum loss). Prefer **Cluster-Aware Updating (CAU)** over ad-hoc SSM reboots. Resume
after patching: `Resume-ClusterNode -Name $me`.

Escalation: SQL AlwaysOn → confirm secondaries synchronized before failover; disk/file-share witness
must be reachable from other nodes; 2-node clusters → sequential patching with customer approval; if
CAU is configured, use it instead of SSM.

## Language pack conflict
A cumulative update can fail if a language pack / MUI doesn't match the OS build ("not applicable").
Align the LP with the current build (remove the mismatched LP or install the matching one) before the LCU.

## Corrupt user profile
A patch's post-install config can fail on a corrupt profile (`0x8007...` profile-load errors, temp
profile loaded). Check `HKLM:\...\ProfileList` for `.bak` entries and duplicate SIDs; repair/recreate
the affected profile. Rarely the blocker on a server, but rule it out if the component itself is healthy.
