# Operations remediations — shard 05

Canonical IDs: `OpM9,Op25,Op26,Op27,Op28`

### OpM9 — AWS Health integration
**Why / fix:** EventBridge rules matching `aws.health` (EKS filter) surface AWS-side maintenance/issues for the cluster. Confirm a rule + target exists. Link: [AWS Health docs](https://docs.aws.amazon.com/health/latest/ug/what-is-aws-health.html).

# Node health & runtime (Op25)

### Op25 — Node conditions healthy (Disk/Memory/PID pressure, NotReady)
**Why it matters:** A node reporting `DiskPressure`, `MemoryPressure`, or `PIDPressure` has crossed a kubelet eviction threshold — the kubelet starts evicting pods, which reschedule onto neighbors and can cascade pressure across the fleet. A `NotReady` node removes its capacity entirely and, if it holds singleton or stateful pods, takes those workloads down until it recovers or is replaced.
**Steps:**
1. Identify the affected nodes and condition: `kubectl get nodes -o json` → read `.status.conditions` for `Ready`, `DiskPressure`, `MemoryPressure`, `PIDPressure`.
2. **DiskPressure:** find what's filling the disk (image cache, ephemeral volumes, logs). Drain the node, expand the root/ephemeral EBS volume or raise `ephemeral-storage` requests, and enable image garbage collection. `kubectl describe node ${NODE}` shows the eviction signal and threshold.
3. **MemoryPressure:** size the instance up, or fix memory-leaking/over-committed pods (set/lower memory limits, add VPC/HPA). Cross-reference Observability O7 (OOMKilled).
4. **PIDPressure:** raise the kubelet `--pod-max-pids` / `--system-reserved=pid=…` or reduce pod density on the node.
5. **NotReady:** `kubectl describe node ${NODE}` + node/system logs; common causes are kubelet/CNI/runtime failure or lost API-server connectivity. Replace the node (MNG/Karpenter) if it doesn't recover.
**Snippet (find pressured nodes):**
```bash
kubectl get nodes -o json | jq -r '.items[] | {n:.metadata.name, c:[.status.conditions[]|select(.status=="True" and (.type=="DiskPressure" or .type=="MemoryPressure" or .type=="PIDPressure"))|.type], ready:([.status.conditions[]|select(.type=="Ready")][0].status)} | select(.c!=[] or .ready!="True")'
```
**References:**
- [Kubernetes — Node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### Op26 — Node Auto Repair enabled *(AWS-API)*
**Why it matters:** Independently configurable from the Monitoring Agent (Op8) — a cluster can run the agent yet never replace the nodes it flags. With auto-repair on, unhealthy nodes are cordoned and replaced automatically.
**How to verify / fix:** `aws eks describe-nodegroup --cluster-name ${CLUSTER} --nodegroup-name ${NG} --query nodegroup.nodeRepairConfig`; enable Node Auto Repair on managed nodegroups (or rely on Karpenter's built-in repair). Requires Op8. **N/A** in kubectl-only mode.
**References:**
- [EKS User Guide — Node health and auto repair](https://docs.aws.amazon.com/eks/latest/userguide/node-health.html)

### Op27 — Karpenter NodePool exclusivity / weighting
**Why it matters:** When multiple NodePools match a pod and none is weighted, Karpenter picks one **randomly** → inconsistent, unpredictable scheduling.
**Steps:** Make NodePools mutually exclusive (distinct instance sets / taints) or set `spec.weight` so the intended pool wins on overlap.
**Snippet:**
```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata: { name: general }
spec:
  weight: 10   # higher weight wins when multiple NodePools match
```
**References:**
- [EKS Best Practices — Karpenter (NodePools mutually exclusive or weighted)](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op28 — Karpenter Spot-to-Spot consolidation
**Why it matters:** Without the `SpotToSpotConsolidation` feature gate, Karpenter won't consolidate Spot→Spot, leaving Spot-heavy clusters on more (or pricier) Spot capacity than needed.
**Steps:** Enable `SpotToSpotConsolidation` in the Karpenter controller settings (Helm `settings.featureGates.spotToSpotConsolidation=true`) for Spot-heavy clusters. **N/A** if there are no Spot NodePools.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

