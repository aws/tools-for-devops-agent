# Networking remediations — shard 02

Canonical IDs: `N9,N10,N11,N12,N13,N14,N15,N16`

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

