# Resilience remediations — shard 02

Canonical IDs: `R9,R10,R11,R12,R13,R14,R15,R16`

### R9 — Startup probe for slow starters
**Why it matters:** Slow-initializing apps (JVM warmup, large caches) get killed by an aggressive liveness probe before they're ready. A startup probe gives them a grace window.
**Steps:** Add a `startupProbe` with a generous `failureThreshold × periodSeconds` budget; liveness only begins after it passes.
**Snippet:**
```yaml
startupProbe:
  httpGet: { path: /healthz, port: 8080 }
  failureThreshold: 30
  periodSeconds: 10        # up to 5 min to start
```
**References:**
- [Kubernetes — Configure Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

### R10 — Rollout sizing / no Recreate for HA apps
**Why it matters:** `Recreate` strategy tears down all pods before starting new ones → downtime. A `RollingUpdate` with too-high `maxUnavailable` can drop below the app's required minimum mid-rollout.
**Steps:**
1. Find `Recreate` deployments: `kubectl get deploy -A -o json | jq -r '.items[] | select(.spec.strategy.type=="Recreate") | "\(.metadata.namespace)/\(.metadata.name)"'`
2. Switch HA workloads to `RollingUpdate` and size `maxUnavailable`/`maxSurge` so the active count never drops below the minimum the app needs.
**Snippet:**
```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 25%
      maxSurge: 25%
```
**References:**
- [EKS Best Practices — Updating applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Rolling update Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)

### R11 — terminationGracePeriod > 0
**Why it matters:** A very short grace period (or 0) kills pods before in-flight requests drain → dropped connections during rollouts and scale-down.
**Steps:** Keep the default 30s (or longer for slow-draining apps); add a `preStop` hook for connection draining where needed.
**Snippet:**
```yaml
spec:
  terminationGracePeriodSeconds: 30
  containers:
    - name: ${APP}
      lifecycle: { preStop: { exec: { command: ["sleep","10"] } } }
```
**References:**
- [Kubernetes — Pod termination](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)

### R12 — Node version consistency
**Why it matters:** Mixed kubelet minors across nodes signal a stalled rollout and risk unsupported skew. (Same as Op2 from the resilience angle.)
**Steps:** Finish the node rollout so all nodes share one kubelet minor within 1 of the control plane.
**References:**
- [EKS Best Practices — Cluster Upgrades](https://docs.aws.amazon.com/eks/latest/best-practices/cluster-upgrades.html)

### R13 — EBS PVC AZ alignment
**Why it matters:** EBS volumes are AZ-bound. If a pod with an EBS PVC can only be scheduled in an AZ that has no nodes, it gets stuck Pending — a silent HA gap that surfaces only during failover.
**Steps:**
1. Identify the AZs of EBS-backed PVs and confirm node groups / NodePools can launch nodes in each of those AZs.
2. Use `volumeBindingMode: WaitForFirstConsumer` so the volume is created in an AZ that has a schedulable node.
**Snippet:**
```yaml
volumeBindingMode: WaitForFirstConsumer
```
**References:**
- [EKS Best Practices — Reliability](https://docs.aws.amazon.com/eks/latest/best-practices/reliability.html)
- [EKS — EBS CSI driver](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)

### R14 — Metrics Server present
**Why it matters:** Required for HPA/VPA-driven self-healing and scaling. (Same as Op19.)
**Steps:** Install metrics-server and confirm Ready.
**References:**
- [EKS User Guide — metrics-server](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html)

### R15 — Kubelet reserved resources
**Why it matters:** Without `kube-reserved`/`system-reserved`, the kubelet and system daemons (containerd, sshd, logging) compete with pods for CPU and memory. Under pressure the node can go `NotReady` and evict pods cluster-wide instead of shedding a single workload. A node whose `allocatable` nearly equals `capacity` has no reservation.
**Steps:**
1. Compare per node: `kubectl get nodes -o custom-columns=NAME:.metadata.name,CPU_CAP:.status.capacity.cpu,CPU_ALLOC:.status.allocatable.cpu,MEM_CAP:.status.capacity.memory,MEM_ALLOC:.status.allocatable.memory` — a near-zero gap means no reservation.
2. Set reservations via the nodegroup launch template / Karpenter `kubelet` config (EKS-optimized AMIs auto-reserve based on instance size; custom AMIs often don't).
**Snippet:**
```yaml
# Karpenter NodePool / EC2NodeClass kubelet block
spec:
  template:
    spec:
      kubelet:
        systemReserved: { cpu: 100m, memory: 200Mi }
        kubeReserved:   { cpu: 100m, memory: 200Mi }
```
**N/A** on Auto Mode / Fargate (AWS-managed kubelet).
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [Kubernetes — Reserve Compute Resources for System Daemons](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/)

### R16 — PV storage class appropriate
**Why it matters:** A stateful workload that binds the wrong StorageClass (or falls back to the default by accident) gets the wrong volume type for its perf/cost profile — and a class with `reclaimPolicy: Delete` silently destroys the volume when the PVC is removed, losing data.
**Steps:**
1. Review PVC `storageClassName` (empty = default class) and the bound class's `reclaimPolicy`.
2. Set an explicit class per stateful workload; use `reclaimPolicy: Retain` for data that must survive PVC deletion, and gp3 for general use (cost A3).
**Snippet:**
```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata: { name: gp3-retain }
provisioner: ebs.csi.aws.com
parameters: { type: gp3 }
reclaimPolicy: Retain
```
**References:**
- [Kubernetes — Storage Classes](https://kubernetes.io/docs/concepts/storage/storage-classes/)
- [EKS Best Practices — Cost Optimization: Storage](https://docs.aws.amazon.com/eks/latest/best-practices/cost-opt-storage.html)

