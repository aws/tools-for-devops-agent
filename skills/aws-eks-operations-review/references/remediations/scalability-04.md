# Scalability remediations — shard 04

Canonical IDs: `ScM4,ScM5,ScM6,ScM7,Sc22,Sc23`

### ScM4 — metrics-server vertical sizing
**Why / fix:** metrics-server holds data in memory — scale its requests/limits with node count. Review its Deployment resources. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### ScM5 — AWS service quotas that gate scale
**Why / fix:** Review quotas EKS scaling commonly hits: ENIs/Region (5,000), IPv4 CIDRs/VPC (5), SGs/ENI (5), rules/SG (50), routes/route-table (50), VPCs/Region (5), IAM roles/account (1,000), OIDC providers/account (100), EC2/EBS limits. Check Service Quotas console. Link: [Known Limits & Service Quotas](https://docs.aws.amazon.com/eks/latest/best-practices/known_limits_and_service_quotas.html).

### ScM6 — AWS API request throttling
**Why / fix:** High-churn clusters (Karpenter/CAS/controllers) can hit EC2/ASG/IAM API rate limits — watch for throttling and ensure backoff/caching. Link: [Scale Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html).

### ScM7 — Single endpoint across multiple LBs
**Why / fix:** For services that exceed one LB's target-group limits, front multiple LBs with Route 53 / Global Accelerator / CloudFront. Link: [Known Limits & Service Quotas](https://docs.aws.amazon.com/eks/latest/best-practices/known_limits_and_service_quotas.html).

### Sc22 — EBS volume-attachment limit per instance *(AWS-API leg)*
**Why it matters:** Dense stateful workloads can exhaust an instance's EBS attachment limit — new volumes stick in `Attaching` and pods stay `ContainerCreating`. Older Nitro instances share ~28 attachments across EBS + ENIs + instance-store; 7th-gen have a dedicated limit up to 64.
**Steps:** Count EBS-backed PVs bound per node vs the instance's limit; move dense stateful workloads to larger / 7th-generation instances, or spread them across more nodes.
**References:**
- [EBS volume limits for Amazon EC2 instances](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/volume_limits.html)

### Sc23 — Kueue queue health (conditional)
**Why it matters:** Kueue manages batch/ML job admission. A stopped or misconfigured ClusterQueue silently blocks all jobs in dependent LocalQueues — batch workloads hang with no visible error.
**Steps:**
1. Check ClusterQueue status: `kubectl get clusterqueues -o json` — verify `.status.conditions` includes `Active=True`.
2. Check LocalQueues: `kubectl get localqueues -A` — no queues should be in `StoppedByClusterQueue` state.
3. Check stuck Workloads: `kubectl get workloads -A` — investigate any `Inadmissible` for > 10 min.
4. Common causes: ResourceFlavor not resolvable (instance type unavailable), borrowing/lending limits too restrictive, ClusterQueue paused manually.
5. Fix: update ResourceFlavors to match available capacity, adjust borrowing limits, or resume the ClusterQueue.
**References:**
- [Kueue documentation](https://kueue.sigs.k8s.io/docs/)
- [Kueue — Run batch workloads](https://kueue.sigs.k8s.io/docs/tasks/)
