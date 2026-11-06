# Aiml remediations — shard 01
Canonical IDs: `M1,M2,M3,M4,M5,M6,M7,M8,M9,M10,M11,M12,M13,M14,M15,M16`

### M1 — Device plugin present
**Why it matters:** Without the NVIDIA/Neuron device plugin, accelerators never appear in node allocatable and pods can't request GPUs — nothing schedules.
**Steps:** Ensure the device plugin / GPU Operator (or Neuron device plugin) is running; AL2023 accelerated AMI needs it installed, Bottlerocket ships it. Confirm `nvidia.com/gpu` (or neuron) in `kubectl get nodes -o json` allocatable.
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M2 — GPU/Neuron requests+limits set
**Why it matters:** Accelerated pods that don't explicitly request `nvidia.com/gpu` / `aws.amazon.com/neuron` misschedule or share accelerators unintentionally.
**Steps:** Set the accelerator resource request/limit on every accelerated pod.
**Snippet:**
```yaml
resources:
  limits: { nvidia.com/gpu: 1 }
```
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M3 — Accelerator nodes tainted
**Why it matters:** Without a taint, non-accelerated pods land on expensive GPU/Neuron nodes and strand capacity.
**Steps:** Taint accelerator nodes (e.g. `nvidia.com/gpu:NoSchedule`) and add matching tolerations only to accelerated pods.
**Snippet:**
```yaml
tolerations:
  - { key: nvidia.com/gpu, operator: Exists, effect: NoSchedule }
```
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M4 — GPU-aware scheduling labels
**Why it matters:** Without GPU/instance-type selectors, pods can land on the wrong or insufficient GPU type.
**Steps:** Use nodeSelector/affinity on GPU labels (e.g. `karpenter.k8s.aws/instance-gpu-name`).
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M5 — GPU sharing where appropriate
**Why it matters:** Low-utilization inference on a whole GPU strands expensive capacity; time-slicing/MIG/MPS/DRA reclaim it.
**Steps:** Enable GPU sharing (time-slicing/MIG/MPS) for suitable inference workloads.
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M6 — Spot/ODCR/Capacity Blocks strategy
**Why it matters:** Matching capacity type to interruption tolerance avoids both lost training work and capacity shortfalls.
**Steps:** Training on Spot+checkpointing or ML Capacity Blocks; inference on On-Demand/ODCR.
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M7 — Checkpointing for long training
**Why it matters:** Without checkpointing, a node/Spot interruption restarts training from zero — huge wasted GPU spend.
**Steps:** Checkpoint to durable storage (S3/FSx) at intervals so jobs resume after interruption.
**References:**
- [EKS Best Practices — AI/ML Compute](https://docs.aws.amazon.com/eks/latest/best-practices/aiml-compute.html)

### M8 — Consolidation disabled on training nodes
**Why it matters:** Karpenter consolidation can reclaim a node mid-training, losing work.
**Steps:** Use `karpenter.sh/do-not-disrupt: "true"` on training pods or a no-consolidation NodePool for training.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

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
