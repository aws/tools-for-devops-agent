# Performance remediations — shard 01
Canonical IDs: `P1,P2,P3,P4,P5,P6,P7,P8,P9,P10,P11,P12,P13,PM1,PM2,PM3,P14,P15,P16`

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

### P9 — Graviton adoption
**Why it matters:** arm64 (Graviton) typically gives better price-performance than equivalent x86 — leaving it unused is money and efficiency left on the table.
**Steps:** Build multi-arch images; add arm64 to Karpenter NodePool `kubernetes.io/arch` requirements; migrate compatible workloads.
**Snippet:**
```yaml
requirements:
  - key: kubernetes.io/arch
    operator: In
    values: ["arm64", "amd64"]
```
**References:**
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### P10 — Instance selection fit
**Why it matters:** Mismatched instance families (e.g. memory-bound workloads on compute-optimized nodes) waste one dimension while bottlenecking another.
**Steps:** Match instance families to workload profile (C for CPU-bound, R for memory-bound, M general); let Karpenter pick from a fitting set rather than over-provisioning.
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### P11 — Prefix delegation (pod density / startup)
**Why it matters:** Default secondary-IP mode caps pod density and slows IP assignment; prefix delegation raises both. (Also N4.)
**Steps:** Set `ENABLE_PREFIX_DELEGATION=true` on vpc-cni; tune `WARM_PREFIX_TARGET`.
**References:**
- [EKS Best Practices — Prefix Mode for Linux](https://docs.aws.amazon.com/eks/latest/best-practices/prefix-mode-linux.html)

### P12 — Compute Optimizer recommendations reviewed *(AWS-API)*
**Why it matters:** Compute Optimizer analyzes real CloudWatch utilization and flags worker instances as `OVER_PROVISIONED` (paying for unused capacity) or `UNDER_PROVISIONED` (throttling / saturation risk). It cross-checks instance right-sizing from data, not config.
**How to verify / fix:** `computeoptimizer.getEC2InstanceRecommendations` for the worker instances; for each non-`OPTIMIZED` finding, adopt the recommended instance type (downsize over-provisioned, upsize under-provisioned) in the MNG/Karpenter requirements. Enable Compute Optimizer in the account if not active.
**N/A** in kubectl-only mode — flag for AWS-API follow-up.
**References:**
- [AWS Compute Optimizer — EC2 recommendations](https://docs.aws.amazon.com/compute-optimizer/latest/ug/view-ec2-recommendations.html)
- [EKS Best Practices — Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html)

### P13 — EBS volume performance headroom *(AWS-API)*
**Why it matters:** A gp2/st1/sc1 volume that exhausts its `BurstBalance` is throttled to its low baseline — a sudden latency cliff for stateful pods. IOPS or throughput saturation on any EBS type stalls I/O. These show up only in `AWS/EBS` CloudWatch metrics, not in kubectl.
**How to verify / fix:**
1. For each EBS-backed PV's volume, check `BurstBalance` (Minimum), `VolumeReadOps`+`VolumeWriteOps` vs provisioned IOPS, and throughput vs provisioned (thresholds in [`../runtime/metrics-thresholds.md`](../runtime/metrics-thresholds.md)).
2. Migrate gp2→gp3 (no burst model; independently provisioned IOPS/throughput) and raise gp3 IOPS/throughput to observed peak; split very hot volumes.
**N/A** without CloudWatch access.
**References:**
- [EBS — Volume performance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)
- [EBS — Monitoring volumes with CloudWatch](https://docs.aws.amazon.com/ebs/latest/userguide/using_cloudwatch_ebs.html)

## Performance — manual / metrics-dependent (PM)

### PM1 — Actual usage vs requests
**Why / fix:** Compare `kubectl top pods/nodes` to configured requests to find over/under-provisioning. Needs metrics-server. Link: [Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html).

### PM2 — Node utilization / bin-packing
**Why / fix:** Persistently low-utilization nodes indicate poor bin-packing → enable Karpenter consolidation or right-size. Use `kubectl top nodes`. Link: [Cost Optimization: Compute](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-compute.html).

### PM3 — VPA recommendations applied
**Why / fix:** Review VPA `status.recommendation` vs configured requests and apply the deltas. Link: [Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html).

### P14 — Init container resource footprint
**Why it matters:** A pod's effective request is `max(sum(app containers), max(any init container))` — a large init request reserves capacity for the pod's whole life and skews autoscaler node sizing.
**Steps:** Right-size `initContainers[].resources.requests` to what init actually needs (usually far less than the app containers).
**References:**
- [EKS Best Practices — Data Plane (resource requests/limits)](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### P15 — EBS IOPS/throughput headroom per volume
**Why it matters:** A volume saturated on IOPS or throughput causes latency spikes and stalled I/O for stateful pods (databases, message queues). P13 checks aggregate; this verifies per-volume headroom for critical StatefulSet PVs.
**Steps:**
1. Identify critical EBS volumes: PVs backing StatefulSets with high I/O (databases, queues).
2. Check per-volume metrics: `aws cloudwatch get-metric-data` for `VolumeReadOps`, `VolumeWriteOps`, `VolumeThroughputPercentage`, `BurstBalance` (gp2).
3. If any volume sustains > 80% IOPS or throughput: increase provisioned IOPS/throughput (gp3) or migrate from gp2→gp3.
4. If BurstBalance < 20% on gp2: migrate to gp3 immediately (eliminates burst dependency).
**References:**
- [EKS Best Practices — Storage](https://docs.aws.amazon.com/eks/latest/best-practices/storage.html)
- [EBS Volume performance](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html)

### P16 — CPU throttling percentage
**Why it matters:** CPU throttling silently degrades performance (increased latency, slower processing) even when node CPU is available — it means the container's CFS quota is being exhausted within each scheduling period.
**Steps:**
1. Check Container Insights (enhanced observability) or Prometheus: `container_cpu_cfs_throttled_periods_total / container_cpu_cfs_periods_total`.
2. If > 25% throttled sustained over 7 days for production workloads: the CPU limit is too restrictive.
3. On single-tenant clusters: consider removing CPU limits entirely (per EKS data-plane guidance — P2).
4. On multi-tenant clusters: raise the CPU limit, or isolate the workload on a dedicated node pool with a taint.
5. Alternatively: use VPA in recommendation mode to right-size limits.
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [Kubernetes — CPU CFS quota](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#how-pods-with-resource-limits-are-run)
