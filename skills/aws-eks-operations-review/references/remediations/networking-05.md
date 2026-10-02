# Networking remediations — shard 05

Canonical IDs: `NM6,NM7,N25,N26`

### NM6 — ENA network performance allowances
**Why / fix:** Watch `*_allowance_exceeded` (conntrack, pps, bandwidth, linklocal/DNS) on instances under load. Node-level metrics. Link: [Network performance monitoring](https://docs.aws.amazon.com/eks/latest/best-practices/monitoring_eks_workloads_for_network_performance_issues.html).

### NM7 — Subnet reservations for prefix mode
**Why / fix:** Reserve contiguous `/28` blocks to avoid fragmentation when using prefix delegation. Configure subnet CIDR reservations. Link: [Prefix Mode (Linux)](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html).

### N25 — hostNetwork port-conflict risk
**Why it matters:** `hostNetwork` pods bind directly to the node's network namespace — two wanting the same port can't co-schedule and one fails to bind (silent bind errors / CrashLoop) where the port is taken; they also bypass NetworkPolicy and SG-for-pods.
**Steps:** Limit `hostNetwork` to genuine host agents; give them unique host ports + node anti-affinity. Cross-ref S2 (host namespaces).
**References:**
- [Kubernetes — Pod networking (hostNetwork)](https://kubernetes.io/docs/concepts/workloads/pods/)

### N26 — Gateway API resource health
**Why it matters:** The AWS Gateway API Controller (VPC Lattice) or Istio/Envoy gateways provision real infrastructure from these CRDs. A `GatewayClass` not `Accepted`, or routes not `Attached`, means traffic isn't served even though the objects exist.
**Steps:** Check `status.conditions`: `GatewayClass` `Accepted=True`, `Gateway` listeners `Programmed`, `HTTPRoute`s `Accepted`+`ResolvedRefs`; fix the referenced controller / backend refs. **N/A** if Gateway API CRDs aren't installed.
**References:**
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/)
