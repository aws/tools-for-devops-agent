# Pillar: Networking

VPC/subnet design, VPC CNI, IP efficiency, load balancing, and network performance. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Networking](https://docs.aws.amazon.com/eks/latest/best-practices/networking.html) · [Subnets/VPC](https://docs.aws.amazon.com/eks/latest/best-practices/subnets.html) · [VPC CNI](https://docs.aws.amazon.com/eks/latest/best-practices/vpc-cni.html) · [IP Optimization](https://docs.aws.amazon.com/eks/latest/best-practices/ip-opt.html) · [IPv6](https://docs.aws.amazon.com/eks/latest/best-practices/ipv6.html) · [Custom Networking](https://docs.aws.amazon.com/eks/latest/best-practices/custom-networking.html) · [Prefix Mode (Linux)](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html) · [Prefix Mode (Windows)](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-win.html) · [Security Groups for Pods](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html) · [Load Balancing](https://docs.aws.amazon.com/eks/latest/best-practices/load-balancing.html) · [Network Performance](https://docs.aws.amazon.com/eks/latest/best-practices/monitoring_eks_workloads_for_network_performance_issues.html) · [IPVS](https://docs.aws.amazon.com/eks/latest/best-practices/ipvs.html)

Reads discovery areas: 8 SERVICES, 10 INGRESS, 25 CNI, 26 NETWORKING_ADVANCED, 41 DNS_CONFIG. (Network *policy* / default-deny is graded under Security S15; this pillar covers the data-path and IP layer.)

> **AWS-side networking facts** (per-subnet IP availability, LB controller IAM, subnet/VPC layout) are graded by the **AWS-API component** ([`../aws-api-checks.md`](../aws-api-checks.md), AX7/AX9) — they quantify the IP-exhaustion (N3) and LBC-health (N13/N14) findings the in-cluster checks can only infer. In kubectl-only mode the NM-series stays N/A.

## Currency framing (read first)

- **VPC CNI assigns pod IPs from VPC CIDRs** — pod IP consumption is a first-class capacity concern, not just a node count.
- **IPv6 is the recommended way** to avoid RFC1918 IP exhaustion on new clusters; prefix delegation is mandatory (and default) on IPv6.
- For IPv4 clusters under IP pressure, the standard mitigations are **prefix delegation**, **custom networking** (secondary non-routable CIDRs), and **WARM_* tuning** — in that rough order.
- **AWS Load Balancer Controller** is the recommended way to provision LBs (over the legacy in-tree controller); **IP target-type** is preferred over instance target-type (lower latency, no extra NodePort hop).
- Subnet sizing, VPC CIDRs, NAT-per-AZ, and endpoint exposure are **AWS-API facts** — pull from DevOps Agent topology / mark N/A for AWS follow-up.
- **Detect the CNI type FIRST.** N1–N8 assume the **Amazon VPC CNI** (`aws-node` DaemonSet). If discovery finds a third-party CNI instead — Cilium (`cilium` DaemonSet) or Calico (`calico-node`), no `aws-node`, different IPAM/overlay — grading the VPC-CNI-specific checks against it produces false findings. When a non-VPC-CNI is detected: mark **N1–N8 N/A** ("cluster uses `<CNI>`, not VPC CNI") and instead assess the equivalents in that CNI's own terms (Cilium/Calico IPAM mode, overlay vs ENI, `CiliumNetworkPolicy`/`GlobalNetworkPolicy` for Security S15, Hubble/Calico observability). NetworkPolicy semantics differ per CNI — S15 must use the installed CNI's policy CRDs, not assume VPC CNI NetworkPolicy.

## CNI & IP management (N1–N8)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| N1 | VPC CNI present & healthy | area 25 (`features.cni.vpc_cni`) | `aws-node` DaemonSet present and Ready | High |
| N2 | VPC CNI version current | area 25 (CNI image tag) | not significantly behind latest | Medium |
| N3 | IP exhaustion risk | area 25/26 (pods-per-node, subnet signals) + `pods` | nodes not near IP/ENI limits; subnets have headroom | High |
| N4 | Prefix delegation for density | area 25 (`features.cni_config.prefix_delegation`) | enabled where high pod density / fast startup needed | Medium |
| N5 | Custom networking (secondary CIDR) | area 25 (`features.cni_config.custom_networking`, ENIConfigs) | used when pod IP space is constrained on the primary CIDR | Medium |
| N6 | WARM pool tuning | area 25 (`WARM_ENI_TARGET`/`WARM_IP_TARGET`/`MINIMUM_IP_TARGET`) | warm-pool targets set deliberately for the workload, not left at defaults on large clusters | Low |
| N7 | IPv6 consideration | area 25 (`features.cni_config.ipv6_cluster`) | IPv6 used or a conscious IPv4 decision documented | Low |
| N8 | CNI metrics helper (IP visibility) | `features.observability.cni_metrics_helper` | present on IPv4 clusters at scale | Low |

## Connectivity & isolation (N9–N12)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| N9 | kube-proxy mode | area 26 (`features.networking.kube_proxy_mode`) | iptables for typical clusters; IPVS considered at >1000 services | Medium |
| N10 | CoreDNS reachability/config | area 41 | CoreDNS healthy; forward/cache configured | High |
| N11 | Security Groups for Pods (SGP) | area 25 (`features.cni_config.security_groups_for_pods`) | used where pod-level SG isolation is required; `POD_SECURITY_GROUP_ENFORCING_MODE` understood | Low |
| N12 | External SNAT setting | area 25 (`AWS_VPC_K8S_CNI_EXTERNALSNAT`) | matches the routing design (external SNAT only when pods reach internet via NAT/TGW) | Low |

## Load balancing & ingress (N13–N17)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| N13 | AWS Load Balancer Controller present | area 26/33 (`features.third_party_controllers.aws_lb_controller`) | installed (not relying on legacy in-tree controller) | Medium |
| N14 | LB target-type = IP | area 26 (Service/Ingress annotations) | LoadBalancer/Ingress use `target-type: ip` | Medium |
| N15 | Correct LB type per workload | area 8/26 | HTTP(S) → ALB/Ingress; TCP/UDP or source-IP/static-IP → NLB | Low |
| N16 | Pod readiness gates for LB | area 35 (readiness gates) + LBC webhook | LB-fronted workloads use readiness gates | Medium |
| N17 | No NodePort services for ingress | area 8 (`svcType`) | no NodePort used as the ingress path | Medium |

## Network performance & DNS scaling (N18–N26)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| N18 | NodeLocal DNSCache | `features.dns.nodelocaldns` | present on larger clusters | Medium |
| N19 | CoreDNS scaling | area 41 (replicas/autoscaling) | replicas scale with cluster; autoscaling configured | High |
| N20 | ndots tuning for external-heavy DNS | area 41 (pod dnsConfig) | external-heavy workloads lower `ndots` (default 5) | Low |
| N21 | VPC DNS PPS / ENA allowance headroom | node `*_allowance_exceeded` metrics (CWAgent) | no `linklocal_allowance_exceeded` breaches (1024 PPS VPC DNS limit); no `conntrack_/pps_allowance_exceeded`; N/A when ethtool metrics are not collected; cross-check O20. | High |
| N22 | NAT Gateway health & redundancy | `AWS/NATGateway` metrics + topology | a NAT per AZ; no `ErrorPortAllocation` (SNAT port exhaustion) or sustained `PacketsDropCount`; N/A when egress uses Transit Gateway; apply the NM1 outbound-path branch. | High |
| N23 | Load balancer health checks configured | area 8/10 + `alb.describeTargetGroups` (AWS-API) | LB-fronted Services/Ingress have health checks aligned to a real readiness path (not just TCP/`/`); AWS-API confirms target-group configuration; in kubectl-only mode infer from annotations or mark N/A. | Medium |
| N24 | Cross-zone load balancing | `alb.describeLoadBalancerAttributes` (AWS-API) | NLBs front-ending multi-AZ workloads have cross-zone enabled where even distribution matters; AWS-API only; N/A in kubectl-only mode. Cross-check cross-AZ transfer cost A19. | Low |
| N25 | hostNetwork port-conflict risk | pods `spec.hostNetwork: true` + `containers[].ports.hostPort` | few/no workloads use `hostNetwork: true`; those that do use unique host ports and node anti-affinity to avoid collisions; Cross-check S2. | Medium |
| N26 | Gateway API resource health (if used) | Gateway API CRDs (`gateways`/`httproutes.gateway.networking.k8s.io`) `status.conditions` | if Gateway API is in use, every `GatewayClass` is `Accepted=True`, `Gateway` listeners are `Programmed`, and `HTTPRoute`s report `Accepted` + `ResolvedRefs`; N/A when Gateway API CRDs are absent. | Low |

## Manual / AWS-API checks (NM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| NM1 | Multi-AZ subnets + NAT per AZ | AWS-API / topology | cluster subnets span ≥2 AZs; a NAT gateway per AZ for resilient egress. **Branch on outbound path:** NAT gateways present → assess multi-AZ redundancy (N22); no NAT but a Transit Gateway VPC attachment on the cluster VPC → outbound via TGW, mark NAT/N22 **N/A** ("egress via Transit Gateway"); no NAT and no TGW → observation only ("verify outbound path with customer"), do **not** recommend adding NAT. |
| NM2 | Nodes in private subnets | AWS-API | worker subnets have `MapPublicIpOnLaunch=false`. |
| NM3 | Cluster endpoint exposure | AWS-API | public/private endpoint config; `publicAccessCidrs` not `0.0.0.0/0`. |
| NM4 | Subnet IP headroom / sizing | AWS-API | cluster + pod subnets sized for growth; secondary CIDRs if needed. |
| NM5 | VPC endpoints for AWS services | AWS-API | ECR/S3/STS/EC2/logs endpoints (also a cost item — see cost-architecture AM1). |
| NM6 | ENA network performance allowances | node metrics | watch `*_allowance_exceeded` (conntrack, pps, bw, linklocal/DNS) on instances. |
| NM7 | Subnet reservations for prefix mode | AWS-API | reserve contiguous /28 blocks to avoid fragmentation when using prefix delegation. |
