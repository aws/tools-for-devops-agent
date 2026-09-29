# Performance remediations — shard 02

Canonical IDs: `P9,P10,P11,P12,P13,PM1,PM2`

### P9 — Graviton adoption
**Why it matters:** arm64 (Graviton) typically gives better price-performance than equivalent x86 — leaving it unused is money and efficiency left on the table.
**Steps:** Build multi-arch images; add arm64 to Karpenter NodePool `kubernetes.io/arch` requirements; migrate compatible workloads.
**Snippet:**
```yaml
requirements:
  - key: kubernetes.io/arch
    operator: In
    values: ["arm64", "amd64"]
```
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### P10 — Instance selection fit
**Why it matters:** Mismatched instance families (e.g. memory-bound workloads on compute-optimized nodes) waste one dimension while bottlenecking another.
**Steps:** Match instance families to workload profile (C for CPU-bound, R for memory-bound, M general); let Karpenter pick from a fitting set rather than over-provisioning.
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### P11 — Prefix delegation (pod density / startup)
**Why it matters:** Default secondary-IP mode caps pod density and slows IP assignment; prefix delegation raises both. (Also N4.)
**Steps:** Set `ENABLE_PREFIX_DELEGATION=true` on vpc-cni; tune `WARM_PREFIX_TARGET`.
**References:**
- [EKS Best Practices — Prefix Mode for Linux](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html)

### P12 — Compute Optimizer recommendations reviewed *(AWS-API)*
**Why it matters:** Compute Optimizer analyzes real CloudWatch utilization and flags worker instances as `OVER_PROVISIONED` (paying for unused capacity) or `UNDER_PROVISIONED` (throttling / saturation risk). It cross-checks instance right-sizing from data, not config.
**How to verify / fix:** `computeoptimizer.getEC2InstanceRecommendations` for the worker instances; for each non-`OPTIMIZED` finding, adopt the recommended instance type (downsize over-provisioned, upsize under-provisioned) in the MNG/Karpenter requirements. Enable Compute Optimizer in the account if not active.
**N/A** in kubectl-only mode — flag for AWS-API follow-up.
**References:**
- [AWS Compute Optimizer — EC2 recommendations](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-ec2-recommendations.html)
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### P13 — EBS volume performance headroom *(AWS-API)*
**Why it matters:** A gp2/st1/sc1 volume that exhausts its `BurstBalance` is throttled to its low baseline — a sudden latency cliff for stateful pods. IOPS or throughput saturation on any EBS type stalls I/O. These show up only in `AWS/EBS` CloudWatch metrics, not in kubectl.
**How to verify / fix:**
1. For each EBS-backed PV's volume, check `BurstBalance` (Minimum), `VolumeReadOps`+`VolumeWriteOps` vs provisioned IOPS, and throughput vs provisioned (thresholds in [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md)).
2. Migrate gp2→gp3 (no burst model; independently provisioned IOPS/throughput) and raise gp3 IOPS/throughput to observed peak; split very hot volumes.
**N/A** without CloudWatch access.
**References:**
- [EBS — Volume performance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)
- [EBS — Monitoring volumes with CloudWatch](https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html)

## Performance — manual / metrics-dependent (PM)

### PM1 — Actual usage vs requests
**Why / fix:** Compare `kubectl top pods/nodes` to configured requests to find over/under-provisioning. Needs metrics-server. Link: [Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html).

### PM2 — Node utilization / bin-packing
**Why / fix:** Persistently low-utilization nodes indicate poor bin-packing → enable Karpenter consolidation or right-size. Use `kubectl top nodes`. Link: [Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html).

