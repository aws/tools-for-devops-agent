# Pillar: Resilience & HA

Workload and data-plane resilience. Grade every canonical row PASS / FAIL / N/A with evidence and severity; use [`../remediations/index.md`](../remediations/index.md) only after FAIL IDs are known. N/A requires an explicit applicability or evidence reason.

> **Apply [`../runtime/grading-guards.md`](../runtime/grading-guards.md) during grading** — do not conclude beyond what the required evidence supports.

Best-practice anchors: [Application HA](https://docs.aws.amazon.com/eks/latest/best-practices/application.html) · [Data Plane](https://docs.aws.amazon.com/eks/latest/best-practices/data-plane.html) · [Reliability](https://docs.aws.amazon.com/eks/latest/best-practices/reliability.html)

Reads discovery areas: 4 DEPLOYMENTS, 5 STATEFULSETS, 7 PODS, 14 PDB, 35 RELIABILITY, 36 DATA_PLANE.

## Currency framing (read first)

- **Control plane is AWS-managed** — EKS runs API servers + etcd across 3 AZs with auto-replacement. Don't grade control-plane HA as a customer finding. Control-plane *saturation* (etcd size, APF, API latency) belongs to the **Control Plane Health** pillar ([`control-plane.md`](control-plane.md)).
- **Data-plane baseline:** 2+ worker nodes across 2+ AZs.
- **Topology spread constraints** are the preferred AZ-spread mechanism — Auto Mode / Karpenter honor them and launch nodes in the right AZs. Pod anti-affinity is the older fallback.
- **PDBs gate update safety** — Auto Mode, Karpenter, CAS, and MNG all honor PDBs during scale-down and node updates.

## Checks (R-series)

| ID | Check | Source | Pass criteria | Severity |
|----|-------|--------|---------------|----------|
| R1 | Multi-AZ node distribution | nodes `topology.kubernetes.io/zone` (`single_az_nodes`) | nodes span 2+ AZs | Critical |
| R2 | Multiple replicas for prod Deployments | Deployment `spec.replicas` | non-batch Deployments have replicas ≥ 2 | High |
| R3 | No singleton pods | pods `ownerReferences` | no app pods running outside a controller | High |
| R4 | Topology spread or anti-affinity | Deployment pod spec | replicas > 1 have topologySpreadConstraints or podAntiAffinity | High |
| R5 | topologySpread minDomains + whenUnsatisfiable | Deployment topologySpreadConstraints | zone spreads set `minDomains`; avoid `DoNotSchedule` unless intended | Medium |
| R6 | PDB coverage | PDBs vs workloads (`workloads_without_pdb`) | multi-replica Deployments/StatefulSets have a matching PDB | High |
| R7 | No blocking PDBs | PDB spec (`pdb_blocking`) | no PDB with `maxUnavailable:0` or `minAvailable:100%` | High |
| R8 | Liveness + readiness probes | container probes (`containers_*_liveness/readiness`) | all serving containers have both | High |
| R9 | Startup probe for slow starters | container `startupProbe` | slow-init containers have a startupProbe | Medium |
| R10 | Rollout sizing | Deployment `spec.strategy` (`rollout_maxunavail_risky`) | RollingUpdate `maxUnavailable` keeps app above its minimum; not `Recreate` for HA apps | Medium |
| R11 | terminationGracePeriod > 0 | pod `terminationGracePeriodSeconds` | > 0 (default 30 OK); flag very short (<10s) | Medium |
| R12 | Node version consistency | nodes kubeletVersion | all nodes same kubelet minor | High |
| R13 | EBS PVC AZ alignment | PVs (ebs csi) + node AZs | nodes launchable in each AZ that has EBS PVCs | High |
| R14 | Metrics Server present | `features.observability.metrics_server` | metrics-server Ready | High |
| R15 | Kubelet reserved resources | nodes `.status.capacity` vs `.status.allocatable` | a `kube-reserved`/`system-reserved` gap exists (allocatable < capacity); N/A on Auto Mode/Fargate; cross-check Op25. | High |
| R16 | PV storage class appropriate | PVCs/PVs `storageClassName` + StorageClass `reclaimPolicy` | stateful workloads bind a deliberate StorageClass (not `""`/default by accident); `reclaimPolicy: Retain` for data that must survive PVC deletion | Medium |
| R17 | Immutable Secrets/ConfigMaps for static data | Secrets/ConfigMaps `immutable` field | rarely-changed Secrets/ConfigMaps set `immutable: true` | Low |
| R18 | preStop hook for LB-fronted workloads | pod `lifecycle.preStop` + whether the workload is behind a Service `type: LoadBalancer` or Ingress (`target-type: ip`) | LB-fronted pods define a `preStop` hook (e.g. `sleep`) that meets or exceeds the target-group **deregistration delay** so in-flight traffic drains before SIGTERM→SIGKILL `terminationGracePeriodSeconds` must exceed the hook/deregistration delay; cross-check R11. | High |
| R19 | StorageClass volumeBindingMode = WaitForFirstConsumer | EBS-backed StorageClass `volumeBindingMode` (classes used by stateful workloads) | EBS (`ebs.csi.aws.com`) StorageClasses backing stateful workloads use `WaitForFirstConsumer`, not `Immediate`; Cross-check R13 and R16. | High |
| R20 | Snapshot coverage for stateful workloads | VolumeSnapshots / VolumeSnapshotSchedule / AWS Backup protected resources | stateful workloads (StatefulSets with PVCs) have a backup mechanism: VolumeSnapshots exist with recent timestamps (< 24h for critical data), or AWS Backup protects the underlying EBS volumes; EFS-backed data requires EFS automatic backups; N/A without stateful workloads. | Medium |
| R21 | Restore testing / RTO-RPO alignment | operational evidence (manual) | the team has tested restore from snapshots within the last 90 days; documented RTO and RPO targets exist and are met by the backup frequency/retention; RPO must be no greater than snapshot frequency and RTO must be achievable for the data size/procedure; N/A when R20 is N/A. | Low |
| R22 | External dependency mapping | pod egress (NetworkPolicies, ServiceEntries, ExternalName services) + application docs | critical external dependencies (databases, S3, SQS, third-party APIs) are identified; their failure modes are understood and mitigated (retries, circuit breakers, fallbacks); Evidence includes dependency documentation plus health checks/synthetic canaries; N/A without external dependencies. | Low |

## Manual / process checks (RM)

| ID | Check | Why not from kubectl | How to verify |
|----|-------|----------------------|---------------|
| RM1 | Rollback mechanism | CI/CD process | Confirm `kubectl rollout undo` path or GitOps revert is tested. |
| RM2 | Blue-green / canary strategy | deployment process | Confirm progressive-delivery tooling (Flux/Argo Rollouts/LBC) for risky changes. |
| RM3 | Chaos engineering | external tooling | FIS / Litmus / Chaos Mesh used to validate resilience. |
| RM4 | Auto Mode disruption controls | AWS-API / NodePool | Auto Mode NodePool `disruption` budgets tuned for the workload. |
