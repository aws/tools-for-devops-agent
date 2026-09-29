# Cost Architecture remediations — shard 01

Canonical IDs: `A1,A2,A3,A4,A5,A6,A7,A8`

### A1 — Spot adoption
**Why it matters:** Spot can cut compute cost up to ~90% for fault-tolerant (stateless/batch) workloads — not using it where appropriate is direct overspend.
**Steps:** Add a Spot-capable Karpenter NodePool (broad instance diversity, Op22) for interruption-tolerant workloads; keep stateful/critical on On-Demand. Ensure graceful interruption handling.
**Snippet:**
```yaml
requirements:
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot", "on-demand"]
```
**References:**
- [EKS Best Practices — Cost Optimization: Compute and Autoscaling](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### A2 — Graviton adoption
**Why it matters:** arm64 gives better price-performance. (Same as P9.)
**Steps:** Build multi-arch images; add arm64 to NodePool arch requirements; migrate compatible workloads.
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### A3 — gp3 over gp2
**Why it matters:** gp3 is ~20% cheaper per GB than gp2 and decouples IOPS/throughput from size — strictly better for most volumes.
**Steps:** Create a gp3 StorageClass (set default), migrate gp2 PVCs over time; new PVCs use gp3.
**Snippet:**
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations: { storageclass.kubernetes.io/is-default-class: "true" }
provisioner: ebs.csi.aws.com
parameters: { type: gp3, encrypted: "true" }
volumeBindingMode: WaitForFirstConsumer
```
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A4 — No unused PVCs
**Why it matters:** Orphaned (unmounted) PVCs keep paying for EBS/EFS capacity no workload uses.
**Steps:** Identify PVCs not referenced by any pod; confirm with owners, snapshot if needed, then delete to reclaim storage.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A5 — Cost monitoring tooling
**Why it matters:** You can't optimize what you can't attribute — without Kubecost/OpenCost (or CUR + split cost allocation) spend isn't mapped to teams/namespaces.
**Steps:** Deploy Kubecost/OpenCost or enable Split Cost Allocation Data in CUR; set up showback per namespace/team.
**References:**
- [EKS Best Practices — Cost Optimization: Awareness](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-awareness.html)

### A6 — Right-sizing signal
**Why it matters:** Right-sizing is step 1 of cost-opt; pods without requests can't be right-sized or scheduled well, and break attribution.
**Steps:** Set requests on all workloads; run VPA in audit mode for recommendations; address the largest over-provisioned workloads first.
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### A7 — Node autoscaler present
**Why it matters:** Without a node autoscaler the cluster can't shed idle capacity (wasted spend) or absorb demand (reliability). Karpenter / Cluster Autoscaler / Auto Mode are required for elastic compute.
**Steps:** Adopt Karpenter (or EKS Auto Mode's managed Karpenter) for flexible, consolidation-aware scaling; ensure consolidation is enabled to reclaim underused nodes.
**References:**
- [EKS Best Practices — Cost Optimization: Compute and Autoscaling](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### A8 — Consolidation / descheduler
**Why it matters:** Without consolidation, nodes stay underutilized after workloads scale down → idle spend.
**Steps:** Enable Karpenter consolidation (Op12) or run the descheduler to rebalance and reclaim nodes.
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

