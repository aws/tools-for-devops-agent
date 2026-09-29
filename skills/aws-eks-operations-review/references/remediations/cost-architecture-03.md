# Cost Architecture remediations — shard 03

Canonical IDs: `A17,A18,A19,A20,A21,A22,A23,AM1`

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

