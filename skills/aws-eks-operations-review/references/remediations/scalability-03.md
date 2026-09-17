# Scalability remediations — shard 03

Canonical IDs: `Sc17,Sc18,Sc19,Sc20,Sc21,ScM1,ScM2,ScM3`

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

