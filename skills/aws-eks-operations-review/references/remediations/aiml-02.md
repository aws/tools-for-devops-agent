# Aiml remediations — shard 02

Canonical IDs: `M9,M10,M11,M12,M13,M14,M15,M16`

### M9 — Job cleanup (ttlSecondsAfterFinished)
**Why it matters:** Finished training/batch Jobs and their pods accumulate in etcd — a scale and clutter concern.
**Steps:** Set `ttlSecondsAfterFinished` on Jobs so completed ones are garbage-collected.
**Snippet:**
```yaml
spec: { ttlSecondsAfterFinished: 3600 }
```
**References:**
- [Kubernetes — TTL for finished Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/)

### M10 — PriorityClass + preemption for job tiers
**Why it matters:** On scarce accelerators, critical jobs should preempt lower-priority ones.
**Steps:** Define PriorityClasses for job tiers and assign them so higher-priority jobs get GPUs under contention.
**References:**
- [Kubernetes — Pod Priority and Preemption](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/)

### M11 — EFA for distributed training
**Why it matters:** Multi-node training is network-bound; without EFA, bandwidth bottlenecks GPU utilization.
**Steps:** Use EFA-enabled instances, request `vpc.amazonaws.com/efa`, and include MPI/NCCL in the image.
**Snippet:**
```yaml
resources:
  limits: { vpc.amazonaws.com/efa: 1 }
```
**References:**
- [EKS Best Practices — AI/ML Networking](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-networking.html)

### M12 — IP consumption on large GPU nodes
**Why it matters:** Big GPU nodes running few pods over-reserve IPs by default → subnet exhaustion at scale.
**Steps:** Tune `WARM_IP_TARGET`/`MINIMUM_IP_TARGET` low for low-pod-density GPU nodes.
**References:**
- [EKS Best Practices — AI/ML Networking](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-networking.html)

### M13 — Model storage via CSI (not in image)
**Why it matters:** Baking large model artifacts into images bloats them and slows pod start.
**Steps:** Serve models from S3/FSx-Lustre/FSx-OpenZFS/EFS via CSI; keep images small.
**References:**
- [EKS Best Practices — AI/ML Storage](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-storage.html)

### M14 — Right storage class for the access pattern
**Why it matters:** Storage throughput directly gates training/inference performance.
**Steps:** FSx for Lustre for high-throughput training; EFS/S3 for shared caches — matched to the workload.
**References:**
- [EKS Best Practices — AI/ML Storage](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-storage.html)

### M15 — GPU metrics (DCGM / Container Insights)
**Why it matters:** Without GPU telemetry you can't see utilization/cost waste — and accelerators are the dominant cost. (Also O11.)
**Steps:** Deploy the DCGM exporter or CloudWatch GPU metrics; dashboard utilization.
**References:**
- [EKS Best Practices — AI/ML Observability](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-observability.html)

### M16 — Track GPU power/SM, not just utilization
**Why it matters:** "GPU busy %" hides under-use; power draw / SM activity vs TDP reveals stranded compute.
**Steps:** Add GPU power/SM-activity panels to dashboards, not just utilization %.
**References:**
- [EKS Best Practices — AI/ML Observability](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-observability.html)
- [EKS Best Practices — AI/ML Performance](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-performance.html)
