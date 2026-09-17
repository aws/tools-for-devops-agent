# Cost Architecture remediations — shard 02

Canonical IDs: `A9,A10,A11,A12,A13,A14,A15,A16`

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

