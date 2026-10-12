# Networking remediations — shard 01
Canonical IDs: `N1,N2,N3,N4,N5,N6,N7,N8,N9,N10,N11,N12,N13,N14,N15,N16`

### N1 — VPC CNI present & healthy
**Why it matters:** `aws-node` (VPC CNI) is the default EKS dataplane — if it's degraded, pods can't get IPs and networking breaks cluster-wide.
**Steps:** Confirm the `aws-node` DaemonSet is present and all pods Ready (`kubectl get ds aws-node -n kube-system`); repair/reinstall the vpc-cni managed addon if degraded.
**References:**
- [EKS Best Practices — VPC CNI](https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html)

### N2 — VPC CNI version current
**Why it matters:** An old CNI misses bug/security fixes and features (prefix delegation, network policy) and may be incompatible with newer cluster minors.
**Steps:** Update the vpc-cni managed addon; confirm version via `aws eks describe-addon`.
**References:**
- [EKS Best Practices — VPC CNI](https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html)

### N3 — IP exhaustion risk
**Why it matters:** Pods consume VPC IPs; when subnets/ENIs run out, pods stick Pending and scale-ups fail — a cluster-wide outage that's hard to diagnose live.
**Steps:** Adopt IPv6 (best), or prefix delegation (N4) / custom networking (N5) on IPv4; size subnets for growth; monitor with the CNI metrics helper (O10).
**References:**
- [EKS Best Practices — IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html)
- [EKS Best Practices — Custom Networking](https://docs.aws.amazon.com/eks/latest/best-practices/custom-networking.html)

### N4 — Prefix delegation for density
**Why it matters:** Default secondary-IP mode limits pods/node and assigns IPs more slowly. Prefix delegation assigns `/28` prefixes (×16 IPs), raising density and speeding pod startup.
**Steps:** Set `ENABLE_PREFIX_DELEGATION=true` on the vpc-cni addon and tune `WARM_PREFIX_TARGET`; ensure subnets have contiguous `/28` blocks. Replace nodes to pick up the change.
**Snippet (vpc-cni addon env):**
```
ENABLE_PREFIX_DELEGATION=true
WARM_PREFIX_TARGET=1
```
**References:**
- [EKS Best Practices — Prefix Mode for Linux](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html)
- [EKS User Guide — Increase available IP addresses (prefix delegation)](https://docs.aws.amazon.com/eks/latest/userguide/cni-increase-ip-addresses.html)

### N5 — Custom networking (secondary CIDR)
**Why it matters:** When the primary VPC CIDR is too small for pod IPs, custom networking moves pods onto secondary (non-routable) CIDRs, relieving IPv4 pressure.
**Steps:** Add a secondary CIDR to the VPC, define `ENIConfig` per AZ, and set `AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true`. Replace nodes to apply.
**References:**
- [EKS Best Practices — Custom Networking](https://docs.aws.amazon.com/eks/latest/best-practices/custom-networking.html)

### N6 — WARM pool tuning
**Why it matters:** On large clusters, default WARM targets either over-reserve IPs (exhaustion) or under-provision (slow pod start). Deliberate tuning balances the two.
**Steps:** Set `WARM_IP_TARGET`/`MINIMUM_IP_TARGET` (or `WARM_PREFIX_TARGET` with prefix mode) to match pod-launch patterns.
**References:**
- [EKS Best Practices — IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html)

### N7 — IPv6 consideration
**Why it matters:** IPv6 removes RFC1918 exhaustion entirely and is recommended for new clusters expected to grow.
**Steps:** Use IPv6 cluster mode for new large clusters (prefix delegation is automatic); for existing IPv4, document the decision and mitigate with N4/N5.
**References:**
- [EKS Best Practices — IPv6](https://docs.aws.amazon.com/eks/latest/best-practices/ipv6.html)

### N8 — CNI metrics helper (IP visibility)
**Why it matters:** Surfaces ENI/IP allocation so you can alert before exhaustion on IPv4 clusters at scale. (Same as O10.)
**Steps:** Deploy the CNI metrics helper; alert on low available IPs.
**References:**
- [EKS — CNI metrics helper](https://docs.aws.amazon.com/eks/latest/userguide/cni-metrics-helper.html)

### N9 — kube-proxy mode
**Why it matters:** iptables mode rebuilds large rule sets as services change — at thousands of services this adds latency; IPVS uses hash tables that scale better.
**Steps:** Keep iptables for typical clusters; evaluate IPVS mode beyond ~1000 services.
**References:**
- [EKS Best Practices — IPVS](https://docs.aws.amazon.com/eks/latest/best-practices/ipvs.html)

### N10 — CoreDNS reachability/config
**Why it matters:** DNS is on the hot path for most workloads — unhealthy or misconfigured CoreDNS causes broad, intermittent failures.
**Steps:** Confirm CoreDNS pods healthy and the Corefile has sane forward/cache; scale and cache per Sc6/Sc7.
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### N11 — Security Groups for Pods (SGP)
**Why it matters:** Where pod-level network isolation to AWS resources is required (e.g. RDS SG rules), SGP attaches EC2 security groups directly to pods.
**Steps:** Enable `ENABLE_POD_ENI=true`, deploy SecurityGroupPolicy resources, and understand `POD_SECURITY_GROUP_ENFORCING_MODE`.
**References:**
- [EKS Best Practices — Security Groups for Pods](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html)

### N12 — External SNAT setting
**Why it matters:** A mismatched `AWS_VPC_K8S_CNI_EXTERNALSNAT` breaks pod egress or double-NATs traffic when pods reach the internet via NAT/Transit Gateway.
**Steps:** Set external SNAT only when pods egress via NAT/TGW; align with the VPC routing design.
**References:**
- [EKS Best Practices — VPC CNI](https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html)

### N13 — AWS Load Balancer Controller present
**Why it matters:** The LBC is the recommended provisioner for ALB/NLB and enables IP target-type, readiness gates, and rich annotations the legacy in-tree controller can't.
**Steps:** Install the AWS Load Balancer Controller (Helm/addon); migrate Services/Ingress off the in-tree controller.
**References:**
- [EKS Best Practices — Load Balancing](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html)
- [AWS Load Balancer Controller documentation](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/)

### N14 — Load balancer target-type = IP
**Why it matters:** `instance` target-type routes through a NodePort and an extra hop (kube-proxy) → higher latency and uneven load. `ip` target-type registers pods directly.
**Steps:** Install the AWS Load Balancer Controller and set the target-type annotation to `ip` on Services/Ingress.
**Snippet (Service):**
```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
    service.beta.kubernetes.io/aws-load-balancer-type: external
```
**References:**
- [EKS Best Practices — Load Balancing](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html)
- [AWS Load Balancer Controller documentation](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/)

### N15 — Correct LB type per workload
**Why it matters:** Using the wrong layer (ALB for raw TCP, or NLB for HTTP routing) means missing features (L7 routing/WAF) or unnecessary cost/complexity.
**Steps:** HTTP(S) → ALB/Ingress; TCP/UDP or static-IP/source-IP-preservation → NLB.
**References:**
- [EKS Best Practices — Load Balancing](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html)

### N16 — Pod readiness gates for LB
**Why it matters:** Without LBC readiness gates, traffic can hit pods before they're registered healthy in the target group → 5xx during rollouts/scale-up.
**Steps:** Label namespaces for LBC pod readiness gate injection so rollouts wait for target-group registration.
**References:**
- [AWS Load Balancer Controller — Pod readiness gate](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/pod_readiness_gate/)
