# Networking remediations — shard 03

Canonical IDs: `N17,N18,N19,N20,N21,N22,N23,N24`

### N17 — No NodePort services for ingress
**Why it matters:** NodePort as the ingress path is hard to secure (wide port range), hard to manage, and bypasses L7 features.
**Steps:** Use LoadBalancer Services / Ingress (via LBC) instead of NodePort for external traffic.
**References:**
- [EKS Best Practices — Load Balancing](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html)

### N18 — NodeLocal DNSCache
**Why it matters:** Cuts DNS latency, CoreDNS load, and conntrack races on larger clusters. (Same as Sc7.)
**Steps:** Deploy NodeLocal DNSCache as a DaemonSet.
**References:**
- [Kubernetes — NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)

### N19 — CoreDNS scaling
**Why it matters:** Under-scaled CoreDNS throttles cluster-wide DNS. (Same as Sc6.)
**Steps:** Scale replicas with cluster size + autoscaling (CPA/HPA).
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### N20 — ndots tuning for external-heavy DNS
**Why it matters:** High `ndots` multiplies failed search-domain lookups for external names. (Same as Sc12.)
**Steps:** Lower `ndots` via pod `dnsConfig` for external-heavy workloads.
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

## Networking — manual / AWS-API (NM)

### N21 — VPC DNS PPS / ENA allowance headroom
**Why it matters:** Each instance has a **1024 packets-per-second limit to the VPC DNS resolver**. When exceeded, the ENA driver silently drops packets (`linklocal_allowance_exceeded`) — pods get intermittent `UnknownHostException`/resolution timeouts while CoreDNS itself reports perfectly healthy. This is one of the most common and hardest-to-diagnose EKS DNS outages. `conntrack_allowance_exceeded` (full connection-tracking table) and `pps_allowance_exceeded` (general PPS cap) cause similar silent drops.
**Steps:**
1. Confirm telemetry: `linklocal_allowance_exceeded` in CloudWatch (needs ethtool metrics — see O20). On-node check: `ethtool -S eth0 | grep allowance`.
2. If breaches exist, deploy **NodeLocal DNSCache** (N18) so most lookups are served on-node and never hit the VPC resolver — the primary fix for `linklocal` drops.
3. Tune `ndots` (N20) to cut lookup amplification; for conntrack/pps pressure, use larger instances / more ENIs or reduce per-node connection churn.
**N/A** if ENA metrics aren't collected — but flag the observability gap (O20).
**References:**
- [EKS Best Practices — Monitoring network performance](https://docs.aws.amazon.com/eks/latest/best-practices/monitoring_eks_workloads_for_network_performance_issues.html)
- [NodeLocal DNSCache on EKS](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)

### N22 — NAT Gateway health & redundancy
**Why it matters:** `ErrorPortAllocation` means the NAT gateway has run out of SNAT ports — new outbound connections fail cluster-wide (image pulls, API calls, external deps). A single-AZ NAT is also an egress SPOF. Sustained `PacketsDropCount` indicates NAT overload.
**Steps:**
1. Check `AWS/NATGateway` `ErrorPortAllocation` (>0 → act) and `PacketsDropCount`; confirm a NAT gateway per AZ.
2. For SNAT port exhaustion: distribute egress (NAT-per-AZ so each AZ uses its local NAT), reduce long-lived idle connections, and cut NAT volume with VPC endpoints (NM5 / cost AM1) for AWS-service traffic.
**N/A** when egress is via Transit Gateway (no NAT) — see NM1.
**References:**
- [VPC — NAT gateway CloudWatch metrics](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway-cloudwatch.html)
- [Troubleshooting — NAT gateway ErrorPortAllocation](https://repost.aws/knowledge-center/vpc-resolve-port-allocation-errors)

### N23 — Load balancer health checks configured
**Why it matters:** A target group with a loose health check (plain TCP, or HTTP `/` returning 200 while the app is unhealthy) keeps broken pods receiving traffic — failures the LB should have removed from rotation.
**Steps:**
1. For each LB-fronted Service/Ingress, check the target-group health check (`alb.describeTargetGroups`) — path, port, success codes, interval.
2. Align it to a real readiness path (the same endpoint the pod's readiness probe uses), not `/` or TCP-only.
**Snippet:**
```yaml
# Ingress annotations (AWS LB Controller)
alb.ingress.kubernetes.io/healthcheck-path: /healthz
alb.ingress.kubernetes.io/success-codes: "200"
```
**N/A** in kubectl-only mode (target-group config is AWS-API) — infer from annotations.
**References:**
- [AWS Load Balancer Controller — health checks](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/#health-check)

### N24 — Cross-zone load balancing
**Why it matters:** NLB cross-zone load balancing is **off by default** — if AZs have uneven pod counts, traffic distributes unevenly (some pods hot, others idle). ALB is always cross-zone, so this applies to NLB. Enabling it evens distribution at the cost of cross-AZ data transfer.
**Steps:** For NLBs fronting multi-AZ workloads where even distribution matters, enable cross-zone (`load_balancing.cross_zone.enabled=true`); check via `alb.describeLoadBalancerAttributes`. Weigh against cross-AZ transfer cost (cost A19).
**N/A** in kubectl-only mode (LB attribute is AWS-API).
**References:**
- [ELB — Cross-zone load balancing](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/how-elastic-load-balancing-works.html#cross-zone-load-balancing)

