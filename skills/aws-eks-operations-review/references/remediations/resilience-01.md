# Resilience remediations — shard 01

Canonical IDs: `R1,R2,R3,R4,R5,R6,R7,R8`

### R1 — Multi-AZ node distribution
**Why it matters:** If all nodes sit in one AZ, an AZ impairment takes the whole data plane down. The resilient baseline is worker nodes across 2+ AZs.
**Steps:**
1. Confirm spread: `kubectl get nodes -o custom-columns=NAME:.metadata.name,ZONE:.metadata.labels.'topology\.kubernetes\.io/zone'`
2. Ensure node groups / Karpenter NodePools span ≥2 (ideally 3) AZs by providing subnets in multiple AZs.
**Snippet (Karpenter NodePool — allow multiple zones):**
```yaml
spec:
  template:
    spec:
      requirements:
        - key: topology.kubernetes.io/zone
          operator: In
          values: ["${AZ_A}", "${AZ_B}", "${AZ_C}"]
```
**References:**
- [EKS Best Practices — Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html)
- [EKS Best Practices — Reliability](https://docs.aws.amazon.com/eks/latest/best-practices/reliability.html)

### R2 — Multiple replicas for prod Deployments
**Why it matters:** A single-replica Deployment has no redundancy — any node drain, crash, or rollout causes downtime.
**Steps:** Set `replicas: 2`+ on non-batch prod Deployments; pair with a PDB (R6) and topology spread (R4) so the replicas actually land on different nodes/AZs.
**Snippet:**
```yaml
spec:
  replicas: 3
```
**References:**
- [EKS Best Practices — Running highly-available applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)

### R3 — No singleton pods
**Why it matters:** A bare Pod (no controller) is never rescheduled if its node dies — it just disappears.
**Steps:** Wrap app pods in a Deployment (stateless) or StatefulSet (stateful); never run bare Pods for workloads.
**References:**
- [Kubernetes — Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)

### R4 — Topology spread or anti-affinity
**Why it matters:** Without spread, all replicas can pack onto one node/AZ — defeating the point of multiple replicas when that domain fails.
**Steps:** Add `topologySpreadConstraints` across `topology.kubernetes.io/zone` and `kubernetes.io/hostname` for multi-replica workloads (preferred over pod anti-affinity on modern EKS).
**Snippet:**
```yaml
spec:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: ScheduleAnyway
      labelSelector: { matchLabels: { app: ${APP} } }
```
**References:**
- [EKS Best Practices — Running highly-available applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Pod Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)

### R5 — topologySpread minDomains + whenUnsatisfiable
**Why it matters:** A zone spread without `minDomains` can't tell the scheduler about zones that have no nodes yet, and `DoNotSchedule` can make pods unschedulable during capacity events.
**Steps:** Set `minDomains` to the expected zone count; use `ScheduleAnyway` unless hard placement is truly required.
**Snippet:**
```yaml
topologySpreadConstraints:
  - maxSkew: 1
    minDomains: 3
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: ScheduleAnyway
    labelSelector: { matchLabels: { app: ${APP} } }
```
**References:**
- [Kubernetes — Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)

### R6 — PodDisruptionBudget coverage
**Why it matters:** Without PDBs, a node drain during an upgrade, Karpenter consolidation, or Auto Mode maintenance can evict all replicas of a workload at once → outage. EKS Auto Mode, Karpenter, Cluster Autoscaler, and managed node groups all honor PDBs during voluntary disruptions.
**Steps:**
1. List multi-replica workloads with no PDB:
   ```bash
   kubectl get deploy -A -o json | jq -r '.items[] | select(.spec.replicas>1) | "\(.metadata.namespace)/\(.metadata.name)"'
   kubectl get pdb -A
   ```
2. Add a PDB per workload (prefer `minAvailable` for small fleets, a percentage for large).
3. Avoid blocking values (`maxUnavailable: 0` / `minAvailable: 100%`) — they stall drains entirely (see R7).
**Snippet:**
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: ${APP}-pdb
  namespace: ${NAMESPACE}
spec:
  minAvailable: 1            # or "50%"
  selector:
    matchLabels:
      app: ${APP}
```
**References:**
- [EKS Best Practices — Running highly-available applications](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Specifying a Disruption Budget](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)

### R7 — No blocking PDBs
**Why it matters:** A PDB with `maxUnavailable: 0` or `minAvailable: 100%` permits zero voluntary disruption, which **stalls node drains, autoscaler consolidation, and node rotation indefinitely** — blocking upgrades and cost optimization.
**Steps:**
1. Find blocking PDBs:
   ```bash
   kubectl get pdb -A -o json | jq -r '.items[] | select((.spec.maxUnavailable==0) or (.spec.minAvailable=="100%")) | "\(.metadata.namespace)/\(.metadata.name)"'
   ```
2. Change to a value that protects availability but still allows one pod to move (e.g. `minAvailable: 1` for replicas ≥ 2, or `maxUnavailable: 1`).
**Snippet:**
```yaml
spec:
  maxUnavailable: 1          # was 0 — allows controlled disruption
```
**References:**
- [EKS Best Practices — Application HA (PDBs)](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Unhealthy Pod eviction policy](https://kubernetes.io/docs/tasks/run-application/configure-pdb/)

### R8 — Liveness + readiness probes
**Why it matters:** Without a readiness probe, traffic is sent to pods that aren't ready (failed rollouts, 5xx during scale-up). Without a liveness probe, hung pods are never restarted. Both are the self-healing baseline.
**Steps:**
1. Find containers missing probes (excluding system namespaces):
   ```bash
   kubectl get pods -A -o json | jq -r '.items[] | select(.metadata.namespace|test("^kube-")|not) | .metadata as $m | .spec.containers[] | select(.readinessProbe==null or .livenessProbe==null) | "\($m.namespace)/\($m.name)/\(.name)"'
   ```
2. Add readiness (gate traffic) and liveness (restart hung) probes; use a startup probe for slow-init apps so liveness doesn't kill them early.
**Snippet:**
```yaml
readinessProbe:
  httpGet: { path: /healthz, port: 8080 }
  initialDelaySeconds: 5
  periodSeconds: 10
livenessProbe:
  httpGet: { path: /livez, port: 8080 }
  initialDelaySeconds: 15
  periodSeconds: 20
```
**References:**
- [EKS Best Practices — Health checks and self-healing](https://docs.aws.amazon.com/eks/latest/best-practices/application.html)
- [Kubernetes — Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

