# Cross-cutting checklist: AI/ML workloads

Not a pillar — a **conditional** checklist that applies **only when the cluster runs accelerated (GPU / AWS Neuron) workloads**. Gate on `gpu_nodes > 0 OR neuron_nodes > 0` from discovery area 38. If no accelerators, mark N/A. When present, run alongside the normal pillars — accelerated ML workloads have cost, scheduling, storage, networking, and observability concerns the general pillars don't cover (and accelerators are the dominant cost driver, so getting this right matters).

Grade **PASS / FAIL / N/A** with evidence, severity, recommendation. Node-config / AWS-API items stay N/A in kubectl-only mode.

Anchor: [AI/ML Best Practices](https://docs.aws.amazon.com/eks/latest/best-practices/aiml.html) (compute, CPU inference, networking, security, storage, observability, performance).

Reads discovery areas: 2 NODES, 4/5 workloads, 7 PODS, 15/16 jobs, 20 STORAGE, 38 AI_ML_WORKLOADS, 44 SCHEDULING.

## Gate

Run only if discovery found accelerator nodes — `nvidia.com/gpu` capacity (`gpu_nodes`), `aws.amazon.com/neuron[core]` (`neuron_nodes`), or EFA (`efa_nodes`). Otherwise N/A — "no accelerated workloads detected."

## Currency framing (read first)

- **Accelerators dominate cost.** A GPU/Trainium node is many times the price of a general node — idle or fractionally-used accelerators are the biggest ML cost leak. Right-sizing, sharing (time-slicing/MIG/MPS), and not stranding them is the priority.
- **Device plugin is mandatory** to expose accelerators. Bottlerocket accelerated AMI ships the NVIDIA driver + device plugin; AL2023 accelerated AMI needs the device plugin installed (DaemonSet or GPU Operator). No plugin → `nvidia.com/gpu` never appears and pods can't request GPUs.
- **Schedule with well-known labels + isolation.** Use GPU/instance labels in nodeSelector/affinity, and **taint accelerator nodes** so non-accelerated pods don't strand expensive capacity.
- **Distributed training is network-bound.** Multi-node training wants high-bandwidth instances + **EFA** (with MPI/NCCL); inference usually doesn't.
- **Training jobs are interruption-sensitive.** Checkpointing + disabling Karpenter consolidation on training nodes + capacity assurance (ML Capacity Blocks / ODCR) prevent lost work.

## Accelerator exposure & scheduling (M1–M6)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| M1 | Device plugin present | area 38 | NVIDIA device plugin / GPU Operator (or Neuron device plugin) running; `nvidia.com/gpu` (or neuron) in node allocatable | High | Without it accelerators aren't schedulable. AL2023 AMI needs it installed; Bottlerocket ships it. |
| M2 | GPU/Neuron requests+limits set | area 4/5/7 container resources | accelerated pods request `nvidia.com/gpu` / `aws.amazon.com/neuron` explicitly | High | Unrequested accelerator pods misschedule or share unintentionally. |
| M3 | Accelerator nodes tainted | area 2 node taints | GPU/Neuron nodes carry a taint (e.g. `nvidia.com/gpu:NoSchedule`) with matching tolerations | High | Keeps non-accelerated pods off expensive nodes (capacity stranding). |
| M4 | GPU-aware scheduling labels | area 4/5 pod spec | accelerated pods use GPU/instance-type nodeSelector/affinity (e.g. `karpenter.k8s.aws/instance-gpu-name`) | Medium | Prevents landing on wrong/insufficient GPU types. |
| M5 | GPU sharing where appropriate | area 38 / node config | time-slicing / MIG / MPS / DRA used for low-utilization inference | Medium | Fractional allocation reclaims stranded GPU capacity. |
| M6 | Spot/ODCR/Capacity Blocks strategy | area 2 capacity types | training on Spot+checkpointing or Capacity Blocks; inference on On-Demand/ODCR | Low | Match capacity type to interruption tolerance and assurance needs. |

## Training job management & resilience (M7–M10)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| M7 | Checkpointing for long training | workload config | long-running training jobs checkpoint to durable storage | High | Recover from node/Spot interruption without restarting from zero. |
| M8 | Consolidation disabled on training nodes | area 28 NodePool / `do-not-disrupt` | interruption-sensitive training uses `karpenter.sh/do-not-disrupt` or a no-consolidation NodePool | Medium | Prevents Karpenter from reclaiming a node mid-training. |
| M9 | Job cleanup (ttlSecondsAfterFinished) | area 15/16 Jobs | training/batch Jobs set `ttlSecondsAfterFinished` | Medium | Finished Jobs/Pods accumulate in etcd otherwise (also a scale concern). |
| M10 | PriorityClass + preemption for job tiers | area 44 / pod spec | higher-priority jobs preempt lower ones on scarce accelerators | Low | Ensures critical jobs get GPUs under contention. |

## Networking & storage (M11–M14)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| M11 | EFA for distributed training | area 38 (`efa_nodes`) + pod `vpc.amazonaws.com/efa` | multi-node training uses EFA-enabled instances + requests EFA | Medium | Network bandwidth bottlenecks multi-GPU training; needs MPI/NCCL in image. |
| M12 | IP consumption on large GPU nodes | area 25/26 WARM_* + Sc/N checks | `WARM_IP_TARGET`/`MINIMUM_IP_TARGET` tuned for low pod-density GPU nodes | Medium | Big GPU nodes with few pods over-reserve IPs → subnet exhaustion at scale. |
| M13 | Model storage via CSI (not in image) | area 20 + 38 | large model artifacts served from S3/FSx-Lustre/FSx-OpenZFS/EFS via CSI, not baked into images | Medium | Keeps images small, speeds pod start, enables shared caches. |
| M14 | Right storage class for the access pattern | area 20 CSI drivers | FSx for Lustre for high-throughput training; EFS/S3 for shared caches; matched to workload | Low | Storage perf directly gates training/inference throughput. |

## Observability (M15–M16)

| ID | Check | Source | Pass criteria | Severity | Recommendation |
|----|-------|--------|---------------|----------|----------------|
| M15 | GPU metrics (DCGM / Container Insights) | `features.observability.dcgm_exporter` + area 29 | DCGM exporter or CloudWatch GPU metrics present | High | Without GPU telemetry you can't see utilization/cost waste. |
| M16 | Track GPU power/SM, not just utilization | observability backend | dashboards track GPU power draw / SM activity vs TDP, not only "GPU busy %" | Medium | Utilization % hides under-use; power vs TDP reveals stranded compute. |

## How to run

Gate on accelerator nodes. Lead the report with M1 (device plugin — nothing works without it), M3 (taint isolation — stops cost stranding), M7 (checkpointing), and M15 (GPU observability — you can't optimize blind). Most checks are gradable from in-cluster data; node-config items (sharing mode, capacity blocks, kubelet) are N/A in kubectl-only mode. Note that accelerators are the cluster's dominant cost, so feed M-series findings into the Cost pillar narrative.
