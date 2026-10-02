# Networking remediations — shard 01

Canonical IDs: `N1,N2,N3,N4,N5,N6,N7,N8`

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

