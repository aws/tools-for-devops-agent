# SOP-075: Resolve Windows Update Failure Due to Windows Server Failover Cluster (WSFC) Node State

| Field | Value |
|-------|-------|
| ID | SOP-075 |
| Category | windows_cluster_node_patch_failure |
| Severity | High |
| Risk Level | High |
| Platforms | Windows |
| Distributions | Windows Server 2012 R2, 2016, 2019, 2022, 2025 |
| Requires Reboot | Yes |
| Estimated Duration | 300 seconds |
| Last Validated | 2026-06-01 |

## Symptoms

- Patch requires reboot but node is active in failover cluster
- `0x80070426` ("The service has not been started") — cluster service dependency
- Cluster-Aware Updating (CAU) conflicts with SSM patching
- Node unable to enter maintenance mode for patching
- Updates install but reboot is blocked by cluster quorum requirements
- Cluster shared volumes (CSV) locked during patch installation
- SQL Server AlwaysOn / Hyper-V cluster resource prevents reboot

## Root Cause

Cluster patching conflicts when:

- Node is the active owner of critical clustered resources
- Cluster quorum would be lost if node reboots
- CAU (Cluster-Aware Updating) schedule conflicts with SSM window
- Cluster service dependencies not met for update installation
- CSV filesystem is paused or redirected during maintenance
- Drain timeout too short — workloads not fully migrated
- Witness/quorum node cannot be rebooted independently

## Related Failure Patterns

- SOP-019 (Pending Reboot) — cluster blocks the pending reboot
- SOP-072 (Scheduled Task) — CAU is a scheduled task
- SOP-055 (Pending Install) — blocked reboot leaves pending state

## Prerequisites

- Instance is reachable via SSM (PingStatus: Online)
- Understanding of customer's cluster topology and failover implications
- Confirm other cluster nodes are healthy before proceeding

## Diagnosis

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$node = Get-ClusterNode -ErrorAction SilentlyContinue
if ($node) {
    $node | Select-Object Name,State,NodeWeight | Format-Table
    Get-ClusterGroup -ErrorAction SilentlyContinue | Select-Object Name,OwnerNode,State | Format-Table
} else { Write-Output "Not a cluster node or FailoverClusters module unavailable" }
```

## Remediation Steps

### Step 1: Determine cluster membership and node state

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$cluster = Get-Cluster -ErrorAction SilentlyContinue
if (-not $cluster) { Write-Output "NOT A CLUSTER NODE - Skip cluster SOPs"; return }
$thisNode = $env:COMPUTERNAME
$nodes = Get-ClusterNode
$thisState = ($nodes | Where-Object { $_.Name -eq $thisNode }).State
Write-Output "Cluster: $($cluster.Name)"
Write-Output "This node: $thisNode (State: $thisState)"
Write-Output "All nodes:"
$nodes | ForEach-Object { Write-Output "  $($_.Name): $($_.State)" }
```

Expected output: Cluster topology displayed
On failure: continue (not a cluster node)

### Step 2: Check resources owned by this node

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
$groups = Get-ClusterGroup -ErrorAction SilentlyContinue | Where-Object { $_.OwnerNode -eq $thisNode -and $_.State -eq 'Online' }
Write-Output "Resources owned by $thisNode ($($groups.Count)):"
$groups | ForEach-Object { Write-Output "  $($_.Name) ($($_.GroupType))" }
```

Expected output: Owned resources listed
On failure: continue

### Step 3: Drain roles from node (move resources to other nodes)

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
$groups = Get-ClusterGroup | Where-Object { $_.OwnerNode -eq $thisNode -and $_.State -eq 'Online' -and $_.Name -ne 'Cluster Group' }
if ($groups.Count -gt 0) {
    foreach ($g in $groups) {
        Move-ClusterGroup -Name $g.Name -ErrorAction SilentlyContinue | Out-Null
        Write-Output "Moved: $($g.Name)"
    }
    Start-Sleep -Seconds 10
    $remaining = Get-ClusterGroup | Where-Object { $_.OwnerNode -eq $thisNode -and $_.State -eq 'Online' -and $_.Name -ne 'Cluster Group' }
    Write-Output "Remaining groups on this node: $($remaining.Count)"
} else { Write-Output "No movable groups on this node" }
```

Expected output: Resources drained
On failure: continue

### Step 4: Suspend cluster node for maintenance

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
try {
    Suspend-ClusterNode -Name $thisNode -Drain -ErrorAction Stop
    Write-Output "Node suspended and drained"
} catch {
    Write-Output "Cannot suspend: $($_.Exception.Message)"
    Write-Output "Node may need manual drain or is the last online node"
}
```

Expected output: "Node suspended and drained"
On failure: continue

### Step 5: Verify node is ready for patching/reboot

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
$state = (Get-ClusterNode -Name $thisNode -ErrorAction SilentlyContinue).State
$groups = Get-ClusterGroup | Where-Object { $_.OwnerNode -eq $thisNode -and $_.State -eq 'Online' -and $_.Name -ne 'Cluster Group' }
if ($state -eq 'Paused' -and $groups.Count -eq 0) { Write-Output "CLUSTER NODE READY FOR PATCHING" }
elseif (-not $state) { Write-Output "CLUSTER NODE READY (not clustered)" }
else { Write-Output "NODE NOT READY: State=$state OwnedGroups=$($groups.Count)" }
```

Expected output: "CLUSTER NODE READY FOR PATCHING"
On failure: abort

## Validation

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
$state = (Get-ClusterNode -Name $thisNode -ErrorAction SilentlyContinue).State
if ($state -eq 'Paused' -or -not $state) { "CLUSTER REMEDIATION OK" } else { "NODE STATE: $state" }
```

Expected: "CLUSTER REMEDIATION OK"

## Rollback

```powershell
Import-Module FailoverClusters -ErrorAction SilentlyContinue
$thisNode = $env:COMPUTERNAME
Resume-ClusterNode -Name $thisNode -ErrorAction SilentlyContinue
Write-Output "Cluster node resumed from maintenance"
```

## Escalation

If node cannot be drained:
- Check if this is the last online node — cannot patch without quorum loss
- For SQL AlwaysOn: ensure secondary replicas are synchronized before failover
- If CAU is configured: use CAU instead of SSM for cluster-aware patching
- For quorum witness: disk/file share witness must be accessible from other nodes
- Contact customer DBA/cluster admin before forcing resource moves
- Consider patching during customer's cluster maintenance window only
- For 2-node clusters: plan sequential patching with customer approval
