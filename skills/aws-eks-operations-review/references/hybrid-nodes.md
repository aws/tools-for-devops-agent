# Cross-cutting checklist: Hybrid Nodes

Not a pillar — a **conditional** checklist that applies **only when the cluster has EKS Hybrid Nodes** (on-prem / edge nodes connected to an EKS control plane in AWS). Gate on `hybrid_nodes > 0` from discovery. If there are no hybrid nodes, mark the whole checklist N/A. When present, run alongside the normal pillars — hybrid nodes change the resilience, networking, and operations assumptions the cloud-centric pillar checks make.

Grade **PASS / FAIL / N/A** with evidence, severity, recommendation. Connectivity / credential / AWS-side items stay N/A in kubectl-only mode.

Anchor: [Hybrid Deployments](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid.html) (network disconnections, pod failover, app network traffic, host credentials).

Reads discovery areas: 2 NODES, 4/5 workloads, 7 PODS, 14 PDB, 35 RELIABILITY, 36 DATA_PLANE.

## Gate

Run only if discovery found hybrid nodes — node label `eks.amazonaws.com/compute-type=hybrid`, or worker nodes with no `spec.providerID` / no cloud zone label. Otherwise N/A — "no hybrid nodes detected."

## Currency framing (read first)

- **The control plane is remote.** Hybrid nodes reach the EKS control plane over Direct Connect / Site-to-Site VPN. The defining risk is **network disconnection** between on-prem nodes and the control plane — design for it.
- **No cloud-controller-manager on hybrid nodes** → zone labels aren't auto-applied. You must set `topology.kubernetes.io/zone` per node (via `nodeadm`/kubelet) so Kubernetes can make correct zonal failover decisions.
- **Disconnection failover hinges on taints + tolerations + leases.** `node-lifecycle-controller` applies `node.kubernetes.io/unreachable` (NoSchedule, then NoExecute) when leases stop renewing; `default-unreachable-toleration-seconds` (300, not configurable in EKS) governs eviction timing. Kubernetes cancels evictions when a **whole zone** is unreachable — so correct zone labels prevent mass eviction during a site disconnect.
- **Host credentials expire.** Hybrid nodes auth via SSM hybrid activations **or** IAM Roles Anywhere (pick one, not both); creds are ~1h and auto-rotate, but a long disconnect can let them lapse → node won't reconnect until refreshed.

## Networking & connectivity (H1–H4)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| H1 | Redundant hybrid connectivity | AWS-API / topology | DX + VPN or redundant DX for control-plane reachability | High | Single link = single point of disconnection. Use the DX Resiliency Toolkit / redundant S2S VPN. |
| H2 | Zone labels on hybrid nodes | area 2 node labels | every hybrid node has `topology.kubernetes.io/zone` set to its DC/location | High | No CCM on hybrid → set zone via nodeadm/kubelet; enables correct zonal failover and prevents mass eviction. |
| H3 | Connection monitoring + NodeNotReady alarm | AWS-API / CW | DX/VPN metrics watched; CloudWatch alarm on `NodeNotReady` (Controller Manager logs) | Medium | Early signal that a hybrid node is disconnecting. Requires CP logging for controllerManager. |
| H4 | Application traffic stays local | area 8 services / topology | on-prem app paths don't round-trip through AWS unnecessarily | Medium | Keep east/west traffic local to the site to survive disconnects and cut latency/transfer. |

## Pod failover behavior (H5–H8)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| H5 | Multi-replica across failure domains | area 4/5/35 | critical apps run replicas across nodes/sites with topology spread | High | A single-site/single-node app can't survive a site disconnect. |
| H6 | Tuned unreachable tolerations | area 4/5 pod spec | latency-sensitive apps set explicit `node.kubernetes.io/unreachable` `tolerationSeconds` | Medium | Default 300s NoExecute eviction may be wrong for hybrid; tune per workload's failover intent. |
| H7 | PDBs sized for disconnection | area 14 (`pdb_blocking`) | PDBs allow failover without blocking, and protect minimums | Medium | Over-restrictive PDBs stall rescheduling during partial outages. |
| H8 | Local-survivability for must-run-on-prem apps | area 4/5 + scheduling | apps that must keep running during a disconnect tolerate `unreachable` and are pinned on-site | High | Pods that must survive a CP disconnect need tolerations + node affinity to stay put and not be evicted. |

## Operations & credentials (H9–H12, mostly manual)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| H9 | Single credential provider | host / AWS-API | SSM hybrid activations **or** IAM Roles Anywhere — not both. |
| H10 | SSM agent version current | host | SSM agent ≥ 3.3.808.0 (30-min backoff cap) so creds recover faster post-disconnect. |
| H11 | Local troubleshooting access | process | operators can reach/restart the SSM agent and read `/var/log/amazon/ssm/...` on-site during a disconnect. |
| H12 | Remote-AWS-service dependency review | architecture | on-prem workloads' dependencies on remote AWS services are known and tolerate disconnection (cache/queue/degrade). |

## How to run

Gate on `hybrid_nodes > 0`. Lead the report with H2 (zone labels — the most common hybrid misconfig) and H5/H8 (survive a disconnect). Flag clearly that several cloud assumptions in the Resilience and Networking pillars **don't hold on hybrid nodes** (no CCM zone labels, remote control plane, disconnection as a first-class failure mode) so those pillar scorecards don't misgrade hybrid nodes. Most H-series items are AWS-API / host-level → N/A in kubectl-only mode, but H2, H5, H6, H7, H8 are gradable from in-cluster data.
