# Aiml remediations — shard 01

Canonical IDs: `M1,M2,M3,M4,M5,M6,M7,M8`

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

