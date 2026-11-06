# Cost Architecture remediations — shard 01
Canonical IDs: `A1,A2,A3,A4,A5,A6,A7,A8,A9,A10,A11,A12,A13,A14,A15,A16,A17,A18,A19,A20,A21,A22,A23,AM1`

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

### A9 — No NodePort services
**Why it matters:** NodePort is hard to manage/secure and doesn't consolidate behind shared LBs. (Cost + ops angle of N17.)
**Steps:** Use LB/Ingress via the LBC; consolidate behind shared ALBs.
**References:**
- [EKS Best Practices — Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html)

### A10 — Ingress consolidation
**Why it matters:** One ALB/NLB per service multiplies hourly + LCU charges; sharing one ALB across many services via Ingress cuts LB cost sharply.
**Steps:** Use a shared ALB with IngressGroup annotations so many Ingresses share one load balancer.
**Snippet:**
```yaml
metadata:
  annotations:
    alb.ingress.kubernetes.io/group.name: shared-prod
```
**References:**
- [EKS Best Practices — Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html)

### A11 — Topology-aware routing
**Why it matters:** Cross-AZ traffic is billed each way; topology-aware routing keeps traffic AZ-local where possible, cutting data-transfer cost and latency.
**Steps:** Enable topology-aware routing (`service.kubernetes.io/topology-mode: Auto`) on high-traffic services with replicas in each AZ.
**References:**
- [EKS Best Practices — Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html)

### A12 — EFS vs EBS appropriateness
**Why it matters:** EFS costs more per GB than EBS — using it for single-writer workloads that only need EBS is overspend.
**Steps:** Use EFS only for genuine ReadWriteMany; use EBS (gp3) for single-writer volumes.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A13 — HPA + VPA coverage for right-sizing
**Why it matters:** HPA (replicas) + VPA (requests) are the core right-sizing loop; missing either leaves capacity over- or under-provisioned.
**Steps:** HPA on stateless workloads (P5) + VPA recommendations (P6) feeding request tuning.
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### A14 — PDBs don't block scale-down
**Why it matters:** Blocking PDBs (`minAvailable:100%`/`maxUnavailable:0`) stop Karpenter/CAS reclaiming idle nodes — a silent cost leak, not just an update risk. (Cost angle of R7.)
**Steps:** Fix blocking PDBs (see R7) so consolidation can reclaim nodes.
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### A15 — Instance-store for ephemeral scratch
**Why it matters:** Heavy-scratch/cache workloads on large EBS root volumes pay for EBS they don't need durably; instance-store (NVMe) is included in the instance price.
**Steps:** For ephemeral scratch, use instance-store-backed instance types and mount the local NVMe rather than oversizing EBS.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A16 — EFS lifecycle / IA storage class
**Why it matters:** Cold data on EFS Standard costs far more than necessary; lifecycle management moves it to IA/Archive automatically.
**Steps:** Enable an EFS lifecycle policy to transition infrequently-accessed files to EFS-IA/Archive.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A17 — EBS backup retention bounded
**Why it matters:** Unbounded VolumeSnapshots/DLM snapshots accrue cost indefinitely.
**Steps:** Set a snapshot retention policy (DLM or the snapshot controller) so old snapshots are pruned.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A18 — Right-sized EBS volumes
**Why it matters:** Heavily over-provisioned gp3 capacity/IOPS/throughput is pure waste — gp3 lets you tune each independently.
**Steps:** Compare provisioned vs used; resize gp3 capacity/IOPS/throughput down to actual need.
**References:**
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

### A19 — Cross-AZ traffic awareness
**Why it matters:** Chatty service-to-service paths spanning AZs incur cross-AZ data-transfer charges each way.
**Steps:** Use topology-aware routing (A11) or AZ-local scheduling for chatty paths; measure with flow logs / cost tooling.
**References:**
- [EKS Best Practices — Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html)

### A20 — LB target-type IP
**Why it matters:** IP target-type removes the NodePort hop (latency + cost). (Same as N14.)
**Steps:** Set LB target-type to `ip`.
**References:**
- [EKS Best Practices — Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html)

### A21 — Control-plane log selectivity
**Why it matters:** EKS control-plane logs are billed per type (Vended Logs) — enabling all types everywhere (especially non-prod) is avoidable spend.
**Steps:** Enable only needed CP log types; be selective in non-prod; stream to S3 for cheaper long-term retention.
**References:**
- [EKS Best Practices — Cost Optimization: Observability](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-observability.html)

### A22 — Telemetry volume / retention
**Why it matters:** Telemetry cost scales with volume — unbounded log retention, high metric cardinality, and 100% trace sampling get expensive fast.
**Steps:** Bound log retention, filter noisy logs, control metric cardinality, and sample traces.
**References:**
- [EKS Best Practices — Cost Optimization: Observability](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-observability.html)

### A23 — Fargate for spiky / low-density workloads
**Why it matters:** Fargate bills per pod with no idle-node cost and isolates each pod in its own micro-VM — a good fit for bursty/batch workloads or strong per-pod isolation needs. For dense, steady-state workloads, EC2/Karpenter bin-packing is cheaper, so this is an architectural fit question, not a defect.
**Steps:** Identify bursty/low-density or isolation-sensitive workloads (`eks.listFargateProfiles` shows current use); evaluate moving them to Fargate profiles, and keep dense steady-state workloads on EC2/Karpenter.
**References:**
- [EKS — Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

## Cost — manual / AWS-API (AM)

### AM1 — VPC endpoints for AWS services
**Why / fix:** ECR/S3/STS/EC2/logs endpoints cut NAT data-processing cost. Verify endpoints exist in the VPC. Link: [Cost Optimization: Networking](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-networking.html).
