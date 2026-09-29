# Scalability remediations — shard 01

Canonical IDs: `Sc1,Sc2,Sc3,Sc4,Sc5,Sc6,Sc7,Sc8`

### Sc1 — Cluster size vs Kubernetes thresholds
**Why it matters:** Approaching the tested ceilings (≤5000 nodes, ≤150k pods, ≤10k services, ≤10k namespaces) degrades API latency and scheduling well before the hard limit.
**Steps:** Track counts vs thresholds; for very large needs, split into multiple clusters or plan control-plane scaling and review the upstream SLOs.
**References:**
- [EKS Best Practices — Scalability](https://docs.aws.amazon.com/eks/latest/best-practices/scalability.html)
- [EKS Best Practices — Known Limits & Service Quotas](https://docs.aws.amazon.com/eks/latest/best-practices/known_limits_and_service_quotas.html)

### Sc2 — Services per namespace < 500
**Why it matters:** kube-proxy generates iptables rules per service across the cluster; thousands of services add latency and risk the 5,000/namespace limit.
**Steps:** Split large namespaces; consider IPVS mode for clusters with many services; use separate clusters for separate environments rather than packing namespaces.
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)
- [EKS Best Practices — IPVS](https://docs.aws.amazon.com/eks/latest/best-practices/ipvs.html)

### Sc3 — Secrets count vs limit
**Why it matters:** Kubernetes has a ~10,000 secrets ceiling and high secret counts inflate kubelet watch load and etcd size.
**Steps:** Move sensitive data to an external store (AWS Secrets Manager via Secrets Store CSI / External Secrets Operator); clean up orphaned secrets; warn at 5,000, treat 10,000 as critical.
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)
- [EKS Best Practices — Data encryption and secrets management](https://docs.aws.amazon.com/eks/latest/best-practices/data-encryption-and-secrets-management.html)

### Sc4 — Instance type diversity
**Why it matters:** A node fleet of a single instance type is exposed to regional capacity exhaustion of that type — scale-ups fail when that one type is unavailable.
**Steps:** Allow 2+ instance types/families (Karpenter NodePool `requirements` or multiple MNGs); the autoscaler then falls back across pools.
**References:**
- [EKS Best Practices — Scale Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-data-plane.html)
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Sc5 — No burstable (T-series) for steady workloads
**Why it matters:** T-series CPU credits throttle sustained workloads unpredictably once credits exhaust — bad for steady production services.
**Steps:** Use M/C/R families for steady workloads; reserve T-series for genuinely bursty/dev workloads (or enable unlimited mode knowingly).
**References:**
- [EKS Best Practices — Scale Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-data-plane.html)

### Sc6 — CoreDNS scaling
**Why it matters:** Under-scaled CoreDNS becomes a cluster-wide bottleneck — DNS timeouts manifest as random app failures and latency.
**Steps:** Scale CoreDNS with cluster size and enable autoscaling (Cluster Proportional Autoscaler or HPA on metrics); pair with NodeLocal DNSCache (Sc7) on large clusters.
**Snippet (CPA target):**
```yaml
# cluster-proportional-autoscaler config
linear:
  coresPerReplica: 256
  nodesPerReplica: 16
  min: 2
```
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### Sc7 — NodeLocal DNSCache
**Why it matters:** A per-node DNS cache cuts CoreDNS load, DNS latency, and conntrack-race failures on busy clusters.
**Steps:** Deploy NodeLocal DNSCache as a DaemonSet; point pods at the local cache IP.
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)
- [Kubernetes — NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)

### Sc8 — CoreDNS lameduck + readiness
**Why it matters:** Without `lameduck` and a `/ready` probe, CoreDNS pods can drop queries during rollout/termination → transient DNS failures during churn.
**Steps:** Ensure the Corefile has the `health`/`ready` plugins and a `lameduck` duration so CoreDNS keeps serving briefly while shutting down.
**Snippet (Corefile excerpt):**
```
health { lameduck 5s }
ready
```
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

