# Scalability remediations — shard 02
Canonical IDs: `Sc17,Sc18,Sc19,Sc20,Sc21,ScM1,ScM2,ScM3,ScM4,ScM5,ScM6,ScM7,Sc22,Sc23`

### Sc17 — Deployment revisionHistoryLimit bounded
**Why it matters:** The default `revisionHistoryLimit: 10` keeps 10 stale ReplicaSets per Deployment in etcd/API — at scale that's significant object bloat.
**Steps:** Set a small `revisionHistoryLimit` (e.g. 2–3) on Deployments.
**Snippet:**
```yaml
spec: { revisionHistoryLimit: 3 }
```
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)

### Sc18 — enableServiceLinks disabled
**Why it matters:** With many services, injecting each as env vars into every pod bloats pod specs and slows pod startup at scale.
**Steps:** Set `enableServiceLinks: false` on pods that don't need service env-var discovery.
**Snippet:**
```yaml
spec: { enableServiceLinks: false }
```
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)

### Sc19 — Dynamic webhooks per resource bounded
**Why it matters:** Each mutating/validating webhook intercepting a resource (especially pods) adds latency to every matching API request and is a failure point.
**Steps:** Keep the number of webhooks intercepting any single resource small; scope rules tightly; set sane timeouts.
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### Sc20 — IPv6 for large-scale pod networking
**Why it matters:** IPv4 clusters hit RFC1918 IP exhaustion as pods scale; IPv6 removes that ceiling and speeds IP assignment.
**Steps:** For new large-scale clusters use IPv6 mode; for existing IPv4, use prefix delegation/custom networking and document the decision. (Also N7.)
**References:**
- [EKS Best Practices — IPv6](https://docs.aws.amazon.com/eks/latest/best-practices/ipv6.html)

### Sc21 — Cluster services on dedicated capacity
**Why it matters:** Co-locating CoreDNS/metrics-server/controllers with bursty workloads lets a workload spike starve critical cluster services.
**Steps:** Run critical cluster services on a dedicated node group or Fargate (taints/tolerations or nodeSelector) so they're isolated from workload spikes.
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

## Scalability — manual / AWS-API (ScM)

### ScM1 — LoadBalancer / target-group quotas
**Why / fix:** LB count vs region quota (default 50); ALB targets default 1000, NLB 3000 (500/AZ). Split across LBs/Ingress or raise the quota via Service Quotas. Link: [Known Limits & Service Quotas](https://docs.aws.amazon.com/eks/latest/best-practices/known_limits_and_service_quotas.html).

### ScM2 — CAS sharding for very large clusters
**Why / fix:** Beyond ~1000 nodes, shard Cluster Autoscaler across node groups so scaling stays responsive. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### ScM3 — API server throttling (429s)
**Why / fix:** APF/429 analysis lives in the **Control Plane Health** pillar (`pillars/control-plane.md`, backed by the `control-plane-health/` component) and control-plane metrics — review there for the upstream SLO view. Link: [Scale Control Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-control-plane.html).

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
