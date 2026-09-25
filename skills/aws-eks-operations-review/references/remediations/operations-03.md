# Operations remediations — shard 03

Canonical IDs: `Op17,Op18,Op19,Op20,Op21,Op22,Op23,Op24`

### Op17 — Auto Mode component dedup
**Why it matters:** On EKS Auto Mode, Karpenter / AWS Load Balancer Controller / EBS CSI are AWS-managed. Running self-managed copies alongside them causes duplicate controllers fighting over the same resources.
**Steps:** On Auto Mode clusters, remove self-managed Karpenter/LBC/EBS-CSI installs; keep only host-level agents that must be DaemonSets.
**References:**
- [EKS Best Practices — Auto Mode](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html)

### Op18 — Single node autoscaler
**Why it matters:** Running Cluster Autoscaler and Karpenter (or self-managed Karpenter on Auto Mode) simultaneously causes them to fight over the same nodes — thrashing, double-provisioning, stuck scale-down.
**Steps:** Pick one. For most clusters migrate fully to Karpenter (or use Auto Mode's managed Karpenter and remove self-managed CAS/Karpenter). Verify only one controller is Running.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)
- [EKS Best Practices — Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html)

### Op19 — metrics-server present
**Why it matters:** metrics-server is required for HPA, VPA, and `kubectl top`. Without it, HPAs can't scale and you're blind to live resource usage.
**Steps:** Install metrics-server (managed addon or upstream manifest) and confirm it's Ready; on Auto Mode it's the expected default data-plane pod.
**References:**
- [Kubernetes — Resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)
- [EKS User Guide — Install metrics-server](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html)

### Op20 — Karpenter controller placement
**Why it matters:** Running the Karpenter controller on a node Karpenter itself manages risks self-disruption — Karpenter can consolidate/expire the node it runs on, briefly losing the controller.
**Steps:** Run the Karpenter controller on a small managed node group or a Fargate profile for the `karpenter` namespace — never on a Karpenter-managed node.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op21 — Consolidation requires memory requests = limits
**Why it matters:** When consolidation is enabled but workloads have memory `requests` < `limits`, Karpenter can misjudge real utilization and consolidate nodes whose pods then get evicted/OOM.
**Steps:** For consolidation-eligible workloads set memory `requests == limits`; use LimitRanges to default this per namespace.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op22 — Spot NodePool instance diversity
**Why it matters:** A Spot NodePool narrowed to a few instance types has fewer capacity pools to draw from → higher interruption rate and provisioning failures.
**Steps:** Broaden Spot NodePool `requirements` to many instance families/sizes; exclude only types that genuinely don't fit the workload.
**Snippet:**
```yaml
requirements:
  - key: karpenter.k8s.aws/instance-category
    operator: In
    values: ["c", "m", "r"]
  - key: karpenter.sh/capacity-type
    operator: In
    values: ["spot"]
```
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op23 — Auto Mode managed-component expectations
**Why it matters:** On Auto Mode, Karpenter/LBC/EBS-CSI are AWS-managed and won't appear as in-cluster pods — flagging them "missing" is a false finding. The real check is no leftover self-managed duplicates.
**Steps:** Treat managed components as present-by-design; only flag leftover self-managed copies (see Op17). Host agents must still be DaemonSets.
**References:**
- [EKS Best Practices — Auto Mode](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html)

### Op24 — CAS auto-discovery + version coupling
**Why it matters:** Without `--node-group-auto-discovery`, CAS needs per-ASG wiring (brittle); and a CAS minor mismatched to the cluster is unsupported.
**Steps:** Set `--node-group-auto-discovery` (tag-based) on CAS and keep its minor matched to the cluster. For spiky capacity, consider Karpenter instead.
**References:**
- [EKS Best Practices — Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html)

## Operations — manual / AWS-API (OpM)

