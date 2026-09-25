# Performance remediations — shard 03

Canonical IDs: `PM3,P14,P15,P16`

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
