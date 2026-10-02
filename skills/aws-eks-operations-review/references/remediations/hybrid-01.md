# Hybrid remediations — shard 01

Canonical IDs: `H1,H2,H3,H4,H5,H6,H7,H8`

### H1 — Redundant hybrid connectivity *(AWS-API/topology)*
**Why it matters:** A single DX/VPN link is a single point of disconnection between on-prem nodes and the remote control plane.
**How to verify / fix:** Confirm redundant Direct Connect, or DX + Site-to-Site VPN backup, using the DX Resiliency Toolkit.
**References:**
- [EKS Best Practices — Hybrid network disconnections](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-network-disconnections.html)

### H2 — Zone labels on hybrid nodes
**Why it matters:** Hybrid nodes have no cloud-controller-manager, so `topology.kubernetes.io/zone` isn't auto-applied. Without it, Kubernetes can't make correct zonal failover decisions and may mass-evict during a site disconnect.
**Steps:** Set `topology.kubernetes.io/zone` per hybrid node (via nodeadm/kubelet) to its DC/location.
**Snippet (kubelet node label):**
```
--node-labels=topology.kubernetes.io/zone=${ONPREM_SITE}
```
**References:**
- [EKS Best Practices — Hybrid node pod failover](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-kubernetes-pod-failover.html)

### H3 — Connection monitoring + NodeNotReady alarm *(AWS-API/CW)*
**Why it matters:** Early warning that a hybrid node is disconnecting limits impact.
**How to verify / fix:** Watch DX/VPN metrics; alarm on `NodeNotReady` (Controller Manager logs — requires controllerManager CP logging on).
**References:**
- [EKS Best Practices — Hybrid network disconnections](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-network-disconnections.html)

### H4 — Application traffic stays local
**Why it matters:** On-prem app paths that round-trip through AWS break during a disconnect and add latency/transfer cost.
**Steps:** Keep east/west traffic local to the site; avoid hard dependencies on remote AWS services for on-site flows.
**References:**
- [EKS Best Practices — Hybrid app network traffic](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-app-network-traffic.html)

### H5 — Multi-replica across failure domains
**Why it matters:** A single-site/single-node app can't survive a site disconnect.
**Steps:** Run replicas across nodes/sites with topology spread for critical hybrid apps.
**References:**
- [EKS Best Practices — Hybrid node pod failover](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-kubernetes-pod-failover.html)

### H6 — Tuned unreachable tolerations
**Why it matters:** The default 300s NoExecute eviction may be wrong for hybrid — too fast (needless eviction on a brief blip) or too slow (delayed failover).
**Steps:** Set explicit `node.kubernetes.io/unreachable` `tolerationSeconds` per workload's failover intent.
**Snippet:**
```yaml
tolerations:
  - key: node.kubernetes.io/unreachable
    operator: Exists
    effect: NoExecute
    tolerationSeconds: 60
```
**References:**
- [EKS Best Practices — Hybrid pod failover](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-kubernetes-pod-failover.html)

### H7 — PDBs sized for disconnection
**Why it matters:** Over-restrictive PDBs stall rescheduling during a partial outage.
**Steps:** Size PDBs to allow failover while protecting a minimum (see R6/R7).
**References:**
- [EKS Best Practices — Hybrid pod failover](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-kubernetes-pod-failover.html)

### H8 — Local-survivability for must-run-on-prem apps
**Why it matters:** Apps that must keep running during a control-plane disconnect need to tolerate `unreachable` and stay pinned on-site, or they'll be evicted.
**Steps:** Add `unreachable` tolerations + node affinity pinning these pods to the on-prem nodes.
**References:**
- [EKS Best Practices — Hybrid network disconnection best practices](https://docs.aws.amazon.com/eks/latest/best-practices/hybrid-nodes-network-disconnection-best-practices.html)

## Hybrid — manual (H9–H12)

