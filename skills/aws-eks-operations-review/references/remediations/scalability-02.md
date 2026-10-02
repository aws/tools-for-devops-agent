# Scalability remediations — shard 02

Canonical IDs: `Sc9,Sc10,Sc11,Sc12,Sc13,Sc14,Sc15,Sc16`

### Sc9 — DaemonSet rolling-update safety
**Why it matters:** A DaemonSet that updates all pods at once causes a cluster-wide thundering herd (image pulls, restarts) on large clusters.
**Steps:** Set `updateStrategy.rollingUpdate.maxUnavailable` to a small number/percentage and `minReadySeconds` so updates roll gradually.
**Snippet:**
```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate: { maxUnavailable: 10% }
  minReadySeconds: 10
```
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### Sc10 — PriorityClass for critical workloads
**Why it matters:** Under node contention, critical pods without a PriorityClass can be evicted/preempted before less important ones.
**Steps:** Define PriorityClasses and assign them to critical Deployments/StatefulSets so they schedule first and preempt lower-priority pods.
**Snippet:**
```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata: { name: critical-app }
value: 1000000
globalDefault: false
```
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)
- [Kubernetes — Pod Priority and Preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/)

### Sc11 — Pods-per-node headroom
**Why it matters:** Nodes near the 110-pod (or prefix-delegation) ceiling can't absorb rescheduled pods during a node loss, and IP/ENI limits compound it.
**Steps:** Track pods/node vs allocatable; adopt prefix delegation (N4) for higher density, or add nodes/instance types with more capacity.
**References:**
- [EKS Best Practices — Scale Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/scale-data-plane.html)

### Sc12 — ndots tuning
**Why it matters:** Default `ndots:5` makes external DNS names go through multiple failed search-domain lookups first — extra latency and CoreDNS load for external-heavy workloads.
**Steps:** Lower `ndots` (e.g. 2) via pod `dnsConfig` for workloads that mostly resolve external names, or use FQDNs with a trailing dot.
**Snippet:**
```yaml
spec:
  dnsConfig:
    options: [{ name: ndots, value: "2" }]
```
**References:**
- [EKS Best Practices — Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html)

### Sc13 — Version skew
**Why it matters:** Nodes more than 2 minors behind the API server (or ahead) are outside the supported skew → undefined behavior at upgrade.
**Steps:** Bring nodes within supported skew before upgrading the control plane further.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [Kubernetes — Version skew policy](https://kubernetes.io/releases/version-skew-policy/)

### Sc14 — No removed/deprecated APIs (PSP etc.)
**Why it matters:** Manifests using removed APIs (PodSecurityPolicy removed in 1.25, old Ingress, in-tree storage) fail outright after the upgrade that removes them — a hard outage.
**Steps:** Run EKS Cluster Insights + pluto/kube-no-trouble; migrate PSP→PSA/policy engine, `extensions/v1beta1` Ingress→`networking.k8s.io/v1`, in-tree volumes→CSI. Use `kubectl-convert` for manifests.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)
- [Kubernetes — Deprecated API migration guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/)

### Sc15 — No deprecated Ingress API
**Why it matters:** `extensions/v1beta1` / `networking.k8s.io/v1beta1` Ingress is removed — those resources vanish after upgrade.
**Steps:** Convert all Ingress to `networking.k8s.io/v1` (note the spec shape changed: `pathType`, `backend.service`).
**References:**
- [Kubernetes — Ingress v1](https://kubernetes.io/docs/concepts/services-networking/ingress/)

### Sc16 — EndpointSlices over Endpoints
**Why it matters:** Legacy Endpoints objects don't scale for large/changing services; EndpointSlices shard endpoint data and reduce watch/update load.
**Steps:** EndpointSlices are default on modern EKS — ensure controllers/tools consume them and nothing relies on the legacy Endpoints object at scale.
**References:**
- [EKS Best Practices — Scale Workloads](https://docs.aws.amazon.com/eks/latest/best-practices/scale-workloads.html)
- [Kubernetes — EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/)

