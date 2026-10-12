# Operations remediations — shard 02
Canonical IDs: `Op17,Op18,Op19,Op20,Op21,Op22,Op23,Op24,OpM1,OpM2,OpM3,OpM4,OpM5,OpM6,OpM7,OpM8,OpM9,Op25,Op26,Op27,Op28`

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

### OpM1 — Karpenter Spot interruption handling
**Why / fix:** If Spot NodePools exist, confirm Karpenter native interruption handling is active (it watches the EC2 rebalance/interruption signal) or an `--interruption-queue` → SQS is wired, so pods drain gracefully on a 2-minute Spot notice. Verify via the Karpenter controller args/config. Link: [Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html).

### OpM2 — CAS auto-discovery
**Why / fix:** Confirm `--node-group-auto-discovery` is set on the CAS deployment (also Op24 when args are readable). Link: [Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html).

### OpM3 — Control-plane logging enabled
**Why / fix:** API/audit/authenticator/controllerManager/scheduler logs are essential for incident forensics and upgrade debugging. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.logging`. Enable the needed types. Link: [Auditing and Logging](https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html).

### OpM4 — Cluster auth mode
**Why / fix:** Standard is `API` (or `API_AND_CONFIG_MAP` during migration) with Access Entries, not the deprecated aws-auth ConfigMap. Verify: `aws eks describe-cluster --name ${CLUSTER} --query cluster.accessConfig.authenticationMode`. Link: [Cluster Access Management](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-access-management.html).

### OpM5 — CAS IAM least privilege
**Why / fix:** The CAS IRSA role should scope `autoscaling:SetDesiredCapacity` + `TerminateInstanceInAutoScalingGroup` to cluster ASGs via `aws:ResourceTag` conditions. Review the role policy in IAM. Link: [Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/best-practices/cas.html).

### OpM6 — CAS sharding for large clusters
**Why / fix:** CAS runs one active replica; beyond ~1000 nodes shard it across node groups to keep scaling decisions timely. Assess against node count. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### OpM7 — CoreDNS tuning under Karpenter
**Why / fix:** Fast node churn stresses DNS; ensure CoreDNS has enough replicas/autoscaling, `lameduck`, and topology spread. Inspect the CoreDNS deployment/Corefile. Link: [Scale Cluster Services](https://docs.aws.amazon.com/eks/latest/best-practices/scale-cluster-services.html).

### OpM8 — do-not-disrupt on critical pods
**Why / fix:** Critical/stateful pods should carry `karpenter.sh/do-not-disrupt: "true"` so consolidation/expiry won't evict them mid-work. Audit pod annotations. Link: [Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html).

### OpM9 — AWS Health integration
**Why / fix:** EventBridge rules matching `aws.health` (EKS filter) surface AWS-side maintenance/issues for the cluster. Confirm a rule + target exists. Link: [AWS Health docs](https://docs.aws.amazon.com/health/latest/ug/what-is-aws-health.html).

# Node health & runtime (Op25)

### Op25 — Node conditions healthy (Disk/Memory/PID pressure, NotReady)
**Why it matters:** A node reporting `DiskPressure`, `MemoryPressure`, or `PIDPressure` has crossed a kubelet eviction threshold — the kubelet starts evicting pods, which reschedule onto neighbors and can cascade pressure across the fleet. A `NotReady` node removes its capacity entirely and, if it holds singleton or stateful pods, takes those workloads down until it recovers or is replaced.
**Steps:**
1. Identify the affected nodes and condition: `kubectl get nodes -o json` → read `.status.conditions` for `Ready`, `DiskPressure`, `MemoryPressure`, `PIDPressure`.
2. **DiskPressure:** find what's filling the disk (image cache, ephemeral volumes, logs). Drain the node, expand the root/ephemeral EBS volume or raise `ephemeral-storage` requests, and enable image garbage collection. `kubectl describe node ${NODE}` shows the eviction signal and threshold.
3. **MemoryPressure:** size the instance up, or fix memory-leaking/over-committed pods (set/lower memory limits, add VPC/HPA). Cross-reference Observability O7 (OOMKilled).
4. **PIDPressure:** raise the kubelet `--pod-max-pids` / `--system-reserved=pid=…` or reduce pod density on the node.
5. **NotReady:** `kubectl describe node ${NODE}` + node/system logs; common causes are kubelet/CNI/runtime failure or lost API-server connectivity. Replace the node (MNG/Karpenter) if it doesn't recover.
**Snippet (find pressured nodes):**
```bash
kubectl get nodes -o json | jq -r '.items[] | {n:.metadata.name, c:[.status.conditions[]|select(.status=="True" and (.type=="DiskPressure" or .type=="MemoryPressure" or .type=="PIDPressure"))|.type], ready:([.status.conditions[]|select(.type=="Ready")][0].status)} | select(.c!=[] or .ready!="True")'
```
**References:**
- [Kubernetes — Node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)

### Op26 — Node Auto Repair enabled *(AWS-API)*
**Why it matters:** Independently configurable from the Monitoring Agent (Op8) — a cluster can run the agent yet never replace the nodes it flags. With auto-repair on, unhealthy nodes are cordoned and replaced automatically.
**How to verify / fix:** `aws eks describe-nodegroup --cluster-name ${CLUSTER} --nodegroup-name ${NG} --query nodegroup.nodeRepairConfig`; enable Node Auto Repair on managed nodegroups (or rely on Karpenter's built-in repair). Requires Op8. **N/A** in kubectl-only mode.
**References:**
- [EKS User Guide — Node health and auto repair](https://docs.aws.amazon.com/eks/latest/userguide/node-health.html)

### Op27 — Karpenter NodePool exclusivity / weighting
**Why it matters:** When multiple NodePools match a pod and none is weighted, Karpenter picks one **randomly** → inconsistent, unpredictable scheduling.
**Steps:** Make NodePools mutually exclusive (distinct instance sets / taints) or set `spec.weight` so the intended pool wins on overlap.
**Snippet:**
```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata: { name: general }
spec:
  weight: 10   # higher weight wins when multiple NodePools match
```
**References:**
- [EKS Best Practices — Karpenter (NodePools mutually exclusive or weighted)](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)

### Op28 — Karpenter Spot-to-Spot consolidation
**Why it matters:** Without the `SpotToSpotConsolidation` feature gate, Karpenter won't consolidate Spot→Spot, leaving Spot-heavy clusters on more (or pricier) Spot capacity than needed.
**Steps:** Enable `SpotToSpotConsolidation` in the Karpenter controller settings (Helm `settings.featureGates.spotToSpotConsolidation=true`) for Spot-heavy clusters. **N/A** if there are no Spot NodePools.
**References:**
- [EKS Best Practices — Karpenter](https://docs.aws.amazon.com/eks/latest/best-practices/karpenter.html)
