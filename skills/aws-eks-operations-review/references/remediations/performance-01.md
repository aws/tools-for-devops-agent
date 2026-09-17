# Performance remediations — shard 01

Canonical IDs: `P1,P2,P3,P4,P5,P6,P7,P8`

### P1 — Resource requests set
**Why it matters:** Without CPU/memory requests the scheduler can't bin-pack or make sound placement decisions, autoscalers can't size correctly, and cost attribution breaks.
**Steps:** Set requests (and memory limits) on every container; use VPA in recommendation mode to right-size; enforce defaults with LimitRanges per namespace.
**Snippet:**
```yaml
resources:
  requests: { cpu: "250m", memory: "256Mi" }
  limits:   { memory: "256Mi" }     # set memory limit; avoid CPU limits (throttling)
```
**References:**
- [EKS Best Practices — Data Plane (requests/limits)](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [Kubernetes — Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

### P2 — No CPU limits (best practice)
**Why it matters:** CPU limits cause CFS throttling — pods are throttled even when the node has spare CPU, hurting latency for no benefit. Requests already guarantee a floor.
**Steps:** Remove CPU `limits`; keep CPU `requests`. Keep memory limits (memory is incompressible). Profile latency-sensitive apps to confirm.
**Snippet:**
```yaml
resources:
  requests: { cpu: "500m", memory: "512Mi" }
  limits:   { memory: "512Mi" }   # no cpu limit
```
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### P3 — Memory requests = limits
**Why it matters:** When memory `requests` < `limits`, a pod can be scheduled where it later can't get the memory it bursts to → OOM kills and eviction under pressure.
**Steps:** Set memory `requests == limits` for predictable (Guaranteed-class) workloads.
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### P4 — QoS distribution
**Why it matters:** BestEffort pods (no requests/limits) are the first evicted under node pressure — fine for throwaway jobs, dangerous for prod services.
**Steps:** Give prod workloads Guaranteed or Burstable QoS by setting requests (and limits); avoid BestEffort for anything that matters.
**References:**
- [Kubernetes — Pod QoS Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)

### P5 — HPA coverage for stateless workloads
**Why it matters:** Fixed replica counts either waste capacity at idle or can't absorb spikes. HPA (or KEDA for event-driven) scales replicas to demand.
**Steps:** Add an HPA per scalable Deployment (requires metrics-server); use KEDA for queue/event-driven scaling.
**Snippet:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: { name: ${APP}, namespace: ${NAMESPACE} }
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: ${APP} }
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```
**References:**
- [EKS Best Practices — Running highly-available applications (HPA)](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)

### P6 — VPA present (right-sizing)
**Why it matters:** Without VPA you have no data-driven signal for whether requests are too high (waste) or too low (eviction) — right-sizing becomes guesswork.
**Steps:** Run VPA in `Off`/recommendation mode to surface right-sizing guidance; apply updates carefully (VPA `Auto` recreates pods).
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [VPA — GitHub](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)

### P7 — ResourceQuota per namespace
**Why it matters:** Without a ResourceQuota, one namespace can consume the whole cluster's CPU/memory and starve others.
**Steps:** Set ResourceQuotas on workload namespaces bounding CPU/memory requests+limits (and object counts where useful).
**Snippet:**
```yaml
apiVersion: v1
kind: ResourceQuota
metadata: { name: ns-quota, namespace: ${NAMESPACE} }
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.memory: 60Gi
```
**References:**
- [Kubernetes — Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/)

### P8 — LimitRange per namespace
**Why it matters:** Without a LimitRange, pods submitted with no requests/limits get none — breaking scheduling, bin-packing, and QoS.
**Steps:** Add a LimitRange per namespace setting default requests/limits so unset pods inherit sane values.
**Snippet:**
```yaml
apiVersion: v1
kind: LimitRange
metadata: { name: defaults, namespace: ${NAMESPACE} }
spec:
  limits:
    - type: Container
      default: { cpu: "500m", memory: "512Mi" }
      defaultRequest: { cpu: "250m", memory: "256Mi" }
```
**References:**
- [Kubernetes — Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/)

